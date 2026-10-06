"""
Handler di logging "drop-in" per inviare i log del bot in diretta al
pannello web (web_server/), pagina Log live.

Design pensato per NON impattare il bot:
  - emit() è non bloccante: mette solo la riga in una coda in memoria.
  - un thread di background separato consuma la coda e fa le richieste
    HTTP, così un backend lento o irraggiungibile non rallenta mai
    l'event loop di discord.py.
  - le righe vengono inviate in micro-batch (fino a BATCH_MAX_SIZE righe o
    BATCH_INTERVAL_SECONDS, quello che avviene prima) invece che una
    request per riga, per non intasare il bot di chiamate HTTP durante i
    picchi di log.
  - qualunque errore di invio (backend giù, rete assente) viene inghiottito
    silenziosamente (stampato su stderr, MAI tramite `logging`, altrimenti
    si rientrerebbe nell'handler stesso creando un loop infinito).
  - usa `requests`, già una dipendenza esistente del bot (vedi
    requirements.txt): nessuna nuova libreria da installare.

Integrazione in bot-discord.py: aggiungere, nel blocco di configurazione
del logging già esistente in cima al file (che per policy del progetto deve
restare il primo blocco eseguito, prima di ogni import pesante):

    from panel_log_handler import PanelLogHandler

    logging.basicConfig(...)  # già presente, invariato
    logging.getLogger().addHandler(
        PanelLogHandler(
            ingest_url=os.getenv("PANEL_LOG_INGEST_URL", ""),
            token=os.getenv("PANEL_LOG_INGEST_TOKEN", ""),
        )
    )

Variabili d'ambiente da aggiungere al .env del bot (root del repo):
    PANEL_LOG_INGEST_URL=http://127.0.0.1:5000/api/logs/ingest
    PANEL_LOG_INGEST_TOKEN=<stesso valore di LOG_INGEST_TOKEN in web_server/api/.env>

Se non impostate, l'handler si disattiva da solo (stampa un avviso su
stderr) e il bot continua a funzionare esattamente come prima: zero rischio
di regressioni se il pannello non è ancora avviato.
"""

from __future__ import annotations

import datetime
import logging
import queue
import sys
import threading

import requests

BATCH_MAX_SIZE = 50
BATCH_INTERVAL_SECONDS = 1.0
REQUEST_TIMEOUT_SECONDS = 3
QUEUE_MAX_SIZE = 5000  # oltre questa soglia le righe più vecchie vengono scartate


class PanelLogHandler(logging.Handler):
    def __init__(self, ingest_url: str, token: str):
        super().__init__(level=logging.INFO)
        self._enabled = bool(ingest_url and token)
        self._ingest_url = ingest_url
        self._token = token
        self._queue: "queue.Queue[dict]" = queue.Queue(maxsize=QUEUE_MAX_SIZE)
        self._stop_event = threading.Event()

        if self._enabled:
            self._thread = threading.Thread(
                target=self._worker, name="panel-log-forwarder", daemon=True
            )
            self._thread.start()
        else:
            print(
                "[PanelLogHandler] Disattivato: PANEL_LOG_INGEST_URL/TOKEN non impostati.",
                file=sys.stderr,
            )

    def emit(self, record: logging.LogRecord) -> None:
        if not self._enabled:
            return
        try:
            line = {
                "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
                "level": record.levelname,
                "logger": record.name,
                "message": self.format(record),
            }
            self._queue.put_nowait(line)
        except queue.Full:
            pass  # meglio perdere qualche riga di log che rallentare/bloccare il bot
        except Exception:
            pass  # emit() non deve MAI sollevare eccezioni

    def close(self) -> None:
        self._stop_event.set()
        super().close()

    def _worker(self) -> None:
        session = requests.Session()
        headers = {"X-Ingest-Token": self._token, "Content-Type": "application/json"}

        while not self._stop_event.is_set():
            batch = self._collect_batch()
            if not batch:
                continue
            try:
                session.post(
                    self._ingest_url,
                    json={"lines": batch},
                    headers=headers,
                    timeout=REQUEST_TIMEOUT_SECONDS,
                )
            except requests.RequestException as e:
                print(f"[PanelLogHandler] Invio log al pannello fallito: {e}", file=sys.stderr)

    def _collect_batch(self) -> list[dict]:
        batch: list[dict] = []
        try:
            first = self._queue.get(timeout=BATCH_INTERVAL_SECONDS)
            batch.append(first)
        except queue.Empty:
            return batch

        while len(batch) < BATCH_MAX_SIZE:
            try:
                batch.append(self._queue.get_nowait())
            except queue.Empty:
                break
        return batch
