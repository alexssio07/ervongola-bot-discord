"""
Distribuzione dei log del bot ai client del pannello via Server-Sent Events
(SSE) invece che WebSocket: Flask (server di sviluppo o gunicorn "sync")
serve SSE nativamente con una semplice risposta a streaming — niente
flask-sock/flask-socketio da aggiungere alle dipendenze solo per un flusso
mono-direzionale (bot/backend -> browser) come questo.

Un ring buffer in RAM tiene le ultime N righe così un client che apre la
pagina Log live ora vede subito un po' di storico invece di uno schermo
vuoto, invece di aspettare la prossima riga live.
"""

import json
import queue
import threading
from collections import deque

from config import LOG_BUFFER_SIZE

_buffer: deque[dict] = deque(maxlen=LOG_BUFFER_SIZE)
_subscribers: set["queue.Queue[dict]"] = set()
_lock = threading.Lock()


def publish(line: dict) -> None:
    with _lock:
        _buffer.append(line)
        subscribers = list(_subscribers)
    for q in subscribers:
        try:
            q.put_nowait(line)
        except queue.Full:
            pass  # client troppo lento: meglio perdere una riga che bloccare gli altri


def subscribe() -> "queue.Queue[dict]":
    q: "queue.Queue[dict]" = queue.Queue(maxsize=1000)
    with _lock:
        _subscribers.add(q)
        history = list(_buffer)
    for line in history:
        q.put_nowait(line)
    return q


def unsubscribe(q: "queue.Queue[dict]") -> None:
    with _lock:
        _subscribers.discard(q)


def format_sse(line: dict) -> str:
    return f"data: {json.dumps(line, ensure_ascii=False)}\n\n"
