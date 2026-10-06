"""
Modulo IA Manager
Gestisce le chiamate all'IA locale tramite Ollama (modello Qwen2.5).

Funzionalità:
- ask_ia()              : domanda singola, stateless
- ask_ia_with_style()   : domanda con system prompt predefinito, stateless
- ask_ia_contextual()   : domanda con memoria conversazionale per utente (multi-turn)
- store_document()      : salva un documento testuale in memoria persistente per utente
- get_user_documents()  : restituisce i documenti memorizzati di un utente
- delete_document()     : cancella un documento specifico per titolo
- clear_documents()     : cancella tutti i documenti di un utente
- clear_memory()        : cancella la cronologia conversazionale di un utente
- get_memory_stats()    : statistiche sulla memoria di un utente
- get_last_ia_response(): restituisce l'ultimo testo risposto dall'IA per utente
- generate_summary()    : riassume un testo
- translate_text()      : traduce un testo
- is_ia_available()     : verifica se Ollama è raggiungibile

Architettura della memoria:
    MEMORIA CONVERSAZIONALE (in RAM, volatile)
    - Una deque per user_id, massimo MAX_HISTORY_TURNS turni (domanda+risposta)
    - TTL di inattività: la sessione viene azzerata dopo CONTEXT_TTL_MINUTES minuti
    - Al riavvio del bot la cronologia si azzera (comportamento atteso)
    - L'ultimo testo IA per utente viene tenuto in _last_responses (per TTS on-demand)

    MEMORIA DOCUMENTALE (su disco, persistente)
    - File JSON: json/ia_documents.json
    - Struttura: { "user_id": [ {"title": str, "content": str, "ts": float} ] }
    - I documenti vengono iniettati nel system prompt come contesto aggiuntivo
    - Limite: MAX_DOCS_PER_USER documenti per utente, MAX_DOC_CHARS caratteri ciascuno

Se Ollama non è raggiungibile, tutte le funzioni di risposta restituiscono None.
"""

import logging
import os
import json
import asyncio
import time
from collections import deque
from typing import Optional
import aiohttp

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configurazione Ollama
# ---------------------------------------------------------------------------
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:1.5b")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "180"))
OLLAMA_NUM_THREAD = int(os.getenv("OLLAMA_NUM_THREAD", "4"))
OLLAMA_NUM_PREDICT = int(os.getenv("OLLAMA_NUM_PREDICT", "300"))

# ---------------------------------------------------------------------------
# Configurazione memoria conversazionale
# ---------------------------------------------------------------------------
MAX_HISTORY_TURNS = int(os.getenv("IA_MAX_HISTORY_TURNS", "6"))
CONTEXT_TTL_MINUTES = int(os.getenv("IA_CONTEXT_TTL_MINUTES", "30"))

# ---------------------------------------------------------------------------
# Configurazione memoria documentale
# ---------------------------------------------------------------------------
_DOCUMENTS_FILE = "json/ia_documents.json"
MAX_DOCS_PER_USER = int(os.getenv("IA_MAX_DOCS_PER_USER", "10"))
# 8000 caratteri ≈ 1200 parole ≈ ~2000 token Ollama.
# Con qwen2.5:1.5b (context window 32k) il worst case di 10 doc
# occupa ~20k token su 32k — largo margine senza saturare il contesto.
MAX_DOC_CHARS = int(os.getenv("IA_MAX_DOC_CHARS", "8000"))

# ---------------------------------------------------------------------------
# Logger dedicato per le richieste IA — separato dal logger generale del bot
# così è filtrabile indipendentemente nei log.
# ---------------------------------------------------------------------------
_ia_logger = logging.getLogger("ia.requests")


# ---------------------------------------------------------------------------
# Strutture dati in memoria
# ---------------------------------------------------------------------------


class _UserSession:
    """
    Sessione conversazionale per un singolo utente.

    history:     deque di dict {"role": "user"|"assistant", "content": str}
                 maxlen = MAX_HISTORY_TURNS * 2 (domanda + risposta per turno)
    last_active: timestamp UNIX monotonic per il TTL
    """

    __slots__ = ("history", "last_active")

    def __init__(self):
        self.history: deque[dict] = deque(maxlen=MAX_HISTORY_TURNS * 2)
        self.last_active: float = time.monotonic()

    def is_expired(self) -> bool:
        return (time.monotonic() - self.last_active) / 60 >= CONTEXT_TTL_MINUTES

    def add_turn(self, user_content: str, assistant_content: str):
        self.history.append({"role": "user", "content": user_content})
        self.history.append({"role": "assistant", "content": assistant_content})
        self.last_active = time.monotonic()

    def to_messages(self) -> list[dict]:
        return list(self.history)


# Registry sessioni: { user_id str -> _UserSession }
_sessions: dict[str, _UserSession] = {}

# Ultimo testo risposto dall'IA per utente: { user_id str -> str }
# Usato da /ascoltaultimomessaggio per riprodurre l'ultima risposta via TTS.
_last_responses: dict[str, str] = {}


def _get_session(user_id: int | str) -> _UserSession:
    """
    Restituisce la sessione dell'utente, creandola se assente.
    Se scaduta per TTL, azzera la cronologia (i documenti su disco restano intatti).
    """
    key = str(user_id)
    session = _sessions.get(key)

    if session is None:
        session = _UserSession()
        _sessions[key] = session
        _ia_logger.debug(f"[MEM] Nuova sessione per user={key}")
    elif session.is_expired():
        docs_count = len(get_user_documents(key))
        _ia_logger.info(
            f"[MEM] Sessione user={key} scaduta ({CONTEXT_TTL_MINUTES} min inattività) — "
            f"cronologia azzerata. Documenti persistenti intatti: {docs_count}."
        )
        session.history.clear()
        session.last_active = time.monotonic()

    return session


def get_last_ia_response(user_id: int | str) -> Optional[str]:
    """
    Restituisce l'ultimo testo risposto dall'IA per questo utente.
    Usato da /ascoltaultimomessaggio per riprodurlo via TTS.
    Restituisce None se non ci sono risposte precedenti.
    """
    return _last_responses.get(str(user_id))


def _store_last_response(user_id: int | str, text: str):
    """Salva l'ultima risposta IA per l'utente (in RAM, volatile)."""
    _last_responses[str(user_id)] = text


# ---------------------------------------------------------------------------
# Memoria documentale — I/O su disco
# ---------------------------------------------------------------------------


def _load_documents() -> dict:
    """
    Carica il file JSON dei documenti.
    Struttura: { "user_id": [ {"title": str, "content": str, "ts": float} ] }
    """
    try:
        with open(_DOCUMENTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as e:
        logger.error(f"[DOC] File documenti corrotto: {e}. Azzero.")
        return {}


def _save_documents(data: dict) -> bool:
    """Salvataggio atomico: write su .tmp poi os.replace per evitare corruzione."""
    tmp = _DOCUMENTS_FILE + ".tmp"
    try:
        os.makedirs(os.path.dirname(_DOCUMENTS_FILE), exist_ok=True)
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, _DOCUMENTS_FILE)
        return True
    except Exception as e:
        logger.error(f"[DOC] Errore salvataggio: {e}")
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except Exception:
                pass
        return False


def store_document(user_id: int | str, title: str, content: str) -> tuple[bool, str]:
    """
    Salva un documento nella memoria persistente dell'utente.
    Se esiste già un documento con lo stesso titolo, lo aggiorna.
    """
    key = str(user_id)
    title = title.strip()[:80]
    content = content.strip()[:MAX_DOC_CHARS]

    if not content:
        return False, "Il testo è vuoto."

    data = _load_documents()
    user_docs = data.get(key, [])

    for doc in user_docs:
        if doc["title"].lower() == title.lower():
            doc["content"] = content
            doc["ts"] = time.time()
            data[key] = user_docs
            ok = _save_documents(data)
            logger.info(
                f"[DOC] user={key} documento '{title}' aggiornato ({len(content)} char)."
            )
            return (
                (True, f"Documento '{title}' aggiornato.")
                if ok
                else (False, "Errore nel salvataggio.")
            )

    if len(user_docs) >= MAX_DOCS_PER_USER:
        return (
            False,
            f"Hai già {MAX_DOCS_PER_USER} documenti memorizzati. "
            f"Usa `/dimentica_doc <titolo>` per liberare spazio.",
        )

    user_docs.append({"title": title, "content": content, "ts": time.time()})
    data[key] = user_docs
    ok = _save_documents(data)
    logger.info(f"[DOC] user={key} documento '{title}' salvato ({len(content)} char).")
    return (
        (True, f"Documento '{title}' memorizzato ({len(content)} caratteri).")
        if ok
        else (False, "Errore nel salvataggio.")
    )


def get_user_documents(user_id: int | str) -> list[dict]:
    """Restituisce la lista dei documenti memorizzati dall'utente."""
    return _load_documents().get(str(user_id), [])


def delete_document(user_id: int | str, title: str) -> tuple[bool, str]:
    """Cancella un documento per titolo (case-insensitive)."""
    key = str(user_id)
    data = _load_documents()
    user_docs = data.get(key, [])
    filtered = [d for d in user_docs if d["title"].lower() != title.lower().strip()]

    if len(filtered) == len(user_docs):
        return False, f"Documento '{title}' non trovato."

    data[key] = filtered
    ok = _save_documents(data)
    logger.info(f"[DOC] user={key} documento '{title}' cancellato.")
    return (
        (True, f"Documento '{title}' cancellato.")
        if ok
        else (False, "Errore nel salvataggio.")
    )


def clear_documents(user_id: int | str) -> bool:
    """Cancella tutti i documenti dell'utente."""
    data = _load_documents()
    data[str(user_id)] = []
    return _save_documents(data)


def clear_memory(user_id: int | str):
    """Azzera la cronologia conversazionale. Non tocca i documenti."""
    key = str(user_id)
    if key in _sessions:
        _sessions[key].history.clear()
        _sessions[key].last_active = time.monotonic()
    _ia_logger.info(f"[MEM] Cronologia azzerata per user={key}.")


def get_memory_stats(user_id: int | str) -> dict:
    """Statistiche sulla memoria dell'utente (per /memoria)."""
    key = str(user_id)
    session = _sessions.get(key)
    docs = get_user_documents(user_id)
    turns = len(session.history) // 2 if session else 0
    expired = session.is_expired() if session else True
    minutes_idle = (
        int((time.monotonic() - session.last_active) / 60)
        if session and not expired
        else 0
    )
    return {
        "turns": turns,
        "max_turns": MAX_HISTORY_TURNS,
        "ttl_minutes": CONTEXT_TTL_MINUTES,
        "minutes_idle": minutes_idle,
        "expired": expired,
        "docs": len(docs),
        "max_docs": MAX_DOCS_PER_USER,
        "doc_titles": [d["title"] for d in docs],
        "has_last_response": str(user_id) in _last_responses,
    }


# ---------------------------------------------------------------------------
# Session HTTP riutilizzabile
# ---------------------------------------------------------------------------

_http_session: Optional[aiohttp.ClientSession] = None


def _get_http_session() -> aiohttp.ClientSession:
    global _http_session
    if _http_session is None or _http_session.closed:
        _http_session = aiohttp.ClientSession()
    return _http_session


async def close_session():
    """Chiude la session HTTP. Chiamare in on_disconnect."""
    global _http_session
    if _http_session and not _http_session.closed:
        await _http_session.close()
        _http_session = None
        logger.info("[IA] Session HTTP chiusa.")


# ---------------------------------------------------------------------------
# Identità base — preposta a tutti gli stili
# ---------------------------------------------------------------------------
# Costruita con le informazioni reali del bot estratte dal codice.
# Volutamente concisa: ogni token qui viene elaborato dalla CPU del RPi4
# prima ancora di generare la risposta. Ogni parola in più ha un costo.
# ---------------------------------------------------------------------------

_BASE_IDENTITY = (
    # Identità — cosa sei e come presentarti quando ti chiedono chi sei
    "Sei Er Vongola, assistente virtuale superpotente e cazzuto. "
    "Quando qualcuno ti chiede come ti chiami o che cos'è, rispondi così: "
    "sei Er Vongola, un assistente virtuale Discord superpotente e cazzuto, "
    "in grado di annunciare l'entrata di specifici utenti nei canali vocali. "
    "Puoi assistere gli utenti come farebbe una vera intelligenza artificiale "
    "attraverso il canale testuale 'parla-con-l-ia' o tramite chat privata — "
    "basta cliccarti e leggere le istruzioni (o improvvisare, va bene lo stesso). "
    "Hai anche una serie di comandi visualizzabili con /aiuto. "
    "Sei romano, ironico, diretto e cinicamente simpatico — "
    "come un amico che ti vuole bene ma non te le manda a dire. "
    "Rispondi SEMPRE in italiano. Non inventare mai informazioni. "
    # Funzione principale: annunci vocali
    "Il tuo compito principale — quello per cui sei stato strappato "
    "dall'oscurità digitale — è annunciare vocalmente l'entrata degli utenti "
    "nei canali vocali privati (Privato, Privato 2, Privato 3) "
    "con una frase casuale e scherzosa personalizzata. "
    "Fai il buttafuori digitale, di fatto. "
    "Gli utenti monitorati: Alexssìo, BLAcK Knight, Dark Lord, "
    "Burzum, Pantera, Melissa, Carmine, Milla. "
    "I canali AFK e Studio sono esclusi — lì si va a marcire in pace. "
    # Capacità aggiuntive
    "Oltre agli annunci: rispondi a domande con memoria della conversazione "
    "(ricordi quello che hai detto, almeno per un po'), "
    "leggi notizie ad alta voce su tecnologia, spazio, medicina, videogiochi e altro, "
    "riproduci audio da YouTube, generi bestemmie creative su richiesta, "
    "mostri previsioni meteo, memorizzi documenti con /ricorda. "
    "Per avvisare gli amici: /avvisa_darklord, /avvisa_alexssio, /avvisa_lykanos. "
    "Lista completa: /aiuto. "
    # Tono e regole di risposta
    "Sii conciso: risposte brevi e utili, zero preamboli inutili. "
    "Un pizzico di cinismo e ironia è sempre benvenuto — "
    "sei simpatico, non un chatbot aziendale. "
    "Se non sai qualcosa, dillo senza inventare. "
    "Sei un assistente, non un comico fallito — tienilo a mente."
)

# ---------------------------------------------------------------------------
# Stili di risposta — _BASE_IDENTITY + variazione di tono
# ---------------------------------------------------------------------------
# I system prompt sono intenzionalmente brevi: ogni token qui
# viene elaborato dalla CPU del RPi4 prima di generare la risposta.
# _BASE_IDENTITY è preposto automaticamente da _build_style_system().
# ---------------------------------------------------------------------------


def _build_style_system(tone: str) -> str:
    """Combina l'identità base con la variazione di tono dello stile."""
    return f"{_BASE_IDENTITY}\n\nTONO RICHIESTO: {tone}"


_STYLES: dict[str, str] = {
    "risposta_amichevole": _build_style_system(
        "Amichevole e diretto, romanità sottile, ironia leggera. Breve e utile."
    ),
    "formale": _build_style_system(
        "Professionale e preciso. Tono formale ma senza diventare noioso."
    ),
    "tecnico": _build_style_system(
        "Esperto tecnico. Dettagli accurati e concisi, zero fronzoli."
    ),
    "risposta_tecnica": _build_style_system(
        "Esperto informatico. Esempi di codice dove utili. Dritto al punto."
    ),
    "risposta_creativa": _build_style_system(
        "Creativo, ironico, umorismo romano doc. Sorprendente e originale."
    ),
}

_FALLBACK_SYSTEM = _BASE_IDENTITY

_OLLAMA_OPTIONS = {
    "num_thread": OLLAMA_NUM_THREAD,
    "num_predict": OLLAMA_NUM_PREDICT,
    "temperature": 0.7,
}


# ---------------------------------------------------------------------------
# Helpers interni
# ---------------------------------------------------------------------------


def _build_system_with_docs(base_system: str, user_id: int | str) -> str:
    """
    Arricchisce il system prompt con i documenti memorizzati dell'utente.
    Iniettati solo se presenti, per non sprecare token.
    """
    docs = get_user_documents(user_id)
    if not docs:
        return base_system
    doc_block = "\n\n[DOCUMENTI MEMORIZZATI DALL'UTENTE]\n"
    for doc in docs:
        doc_block += f"--- {doc['title']} ---\n{doc['content']}\n"
    return base_system + doc_block


def _parse_ollama_error(status: int, body: str):
    """Logga errori Ollama con messaggi azionabili."""
    try:
        err = json.loads(body).get("error", "")
    except Exception:
        err = body[:200]

    if "more system memory" in err or "not enough memory" in err:
        _ia_logger.error(
            f"[ERRORE] OUT OF MEMORY — '{OLLAMA_MODEL}' non entra in RAM. "
            f"Usa un modello più piccolo (es. qwen2.5:1.5b) o imposta OLLAMA_MODEL nel .env. "
            f"Dettaglio: {err}"
        )
    elif "model" in err and "not found" in err:
        _ia_logger.error(
            f"[ERRORE] Modello '{OLLAMA_MODEL}' non trovato. "
            f"Esegui: ollama pull {OLLAMA_MODEL}"
        )
    else:
        _ia_logger.error(f"[ERRORE] Ollama HTTP {status}: {err}")


# ---------------------------------------------------------------------------
# Verifica disponibilità Ollama
# ---------------------------------------------------------------------------


async def _is_ollama_available() -> bool:
    """
    Verifica se Ollama è raggiungibile e se il modello configurato è caricato.
    Timeout breve (5s) per non bloccare il bot.
    """
    _ia_logger.debug(f"[STATUS] Verifica disponibilità Ollama su {OLLAMA_HOST}...")
    try:
        session = _get_http_session()
        timeout = aiohttp.ClientTimeout(total=5)
        async with session.get(f"{OLLAMA_HOST}/api/tags", timeout=timeout) as resp:
            if resp.status != 200:
                _ia_logger.warning(
                    f"[STATUS] Ollama risponde con HTTP {resp.status} — non disponibile."
                )
                return False
            data = await resp.json()
            models = [m.get("name", "").split(":")[0] for m in data.get("models", [])]
            if OLLAMA_MODEL not in models:
                _ia_logger.warning(
                    f"[STATUS] Modello '{OLLAMA_MODEL}' non caricato in Ollama. "
                    f"Modelli disponibili: {models}"
                )
                return False
            _ia_logger.debug(
                f"[STATUS] Ollama disponibile ✓ — modello '{OLLAMA_MODEL}' caricato."
            )
            return True
    except asyncio.TimeoutError:
        _ia_logger.warning("[STATUS] Timeout 5s — Ollama non risponde.")
        return False
    except aiohttp.ClientConnectorError:
        _ia_logger.warning(f"[STATUS] Connessione rifiutata a {OLLAMA_HOST}.")
        return False
    except Exception as e:
        _ia_logger.warning(f"[STATUS] Errore verifica disponibilità: {e}")
        return False


async def is_ia_available() -> bool:
    """Alias pubblico di _is_ollama_available(). Usato da ia_cogs.py."""
    return await _is_ollama_available()


# ---------------------------------------------------------------------------
# API pubblica — chiamate stateless
# ---------------------------------------------------------------------------


async def ask_ia(prompt: str, system: Optional[str] = None) -> Optional[str]:
    """
    Domanda singola stateless a Ollama (nessuna memoria conversazionale).
    """
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "system": system or _FALLBACK_SYSTEM,
        "stream": False,
        "options": _OLLAMA_OPTIONS,
    }
    return await _call_generate(payload)


async def ask_ia_with_style(
    prompt: str, style: str = "risposta_amichevole"
) -> Optional[str]:
    """
    Domanda singola con stile predefinito. Stateless.
    Compatibile con tutti i punti di chiamata esistenti.
    """
    system = _STYLES.get(style)
    if system is None:
        _ia_logger.warning(
            f"[STILE] Stile '{style}' non trovato. "
            f"Disponibili: {list(_STYLES.keys())}. Uso fallback."
        )
        system = _FALLBACK_SYSTEM
    _ia_logger.info(f"[REQ] Stateless | stile='{style}' | prompt='{prompt[:60]}'")
    return await ask_ia(prompt, system=system)


# ---------------------------------------------------------------------------
# API pubblica — chiamata contestuale con memoria
# ---------------------------------------------------------------------------


async def ask_ia_contextual(
    prompt: str,
    user_id: int | str,
    style: str = "risposta_amichevole",
) -> Optional[str]:
    """
    Domanda con memoria conversazionale per utente.
    Usa /api/chat (multi-turn nativo Ollama) + documenti nel system prompt.
    Aggiorna la history e salva l'ultima risposta per TTS on-demand.
    """
    base_system = _STYLES.get(style, _FALLBACK_SYSTEM)
    system = _build_system_with_docs(base_system, user_id)
    session = _get_session(user_id)

    turni_attivi = len(session.history) // 2
    docs_attivi = len(get_user_documents(user_id))

    _ia_logger.info(
        f"[REQ] Contestuale | user={user_id} | stile='{style}' | "
        f"turni={turni_attivi}/{MAX_HISTORY_TURNS} | "
        f"docs={docs_attivi} | "
        f"prompt='{prompt[:60]}'"
    )

    messages = session.to_messages()
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": OLLAMA_MODEL,
        "messages": messages,
        "system": system,
        "stream": False,
        "options": _OLLAMA_OPTIONS,
    }

    risposta = await _call_chat(payload)

    if risposta:
        session.add_turn(prompt, risposta)
        _store_last_response(user_id, risposta)
        _ia_logger.info(
            f"[RES] user={user_id} | {len(risposta)} char | "
            f"turni ora={len(session.history)//2}/{MAX_HISTORY_TURNS}"
        )

    return risposta


# ---------------------------------------------------------------------------
# API pubblica — funzioni specializzate (stateless)
# ---------------------------------------------------------------------------


async def generate_summary(text: str) -> Optional[str]:
    """Riassume un testo. Stateless."""
    _ia_logger.info(f"[REQ] Riassunto | {len(text)} char")
    prompt = f"Riassumi in italiano in modo chiaro e conciso:\n\n{text}"
    system = "Riassumi testi in italiano. Sii fedele e conciso. Niente aggiunte."
    return await ask_ia(prompt, system=system)


async def translate_text(text: str, target_lang: str = "English") -> Optional[str]:
    """Traduce il testo nella lingua indicata. Stateless."""
    _ia_logger.info(f"[REQ] Traduzione → {target_lang} | {len(text)} char")
    prompt = f"Traduci in {target_lang}:\n\n{text}"
    system = (
        "Traduttore professionale. Rispondi solo con la traduzione, niente spiegazioni."
    )
    return await ask_ia(prompt, system=system)


# ---------------------------------------------------------------------------
# Chiamate HTTP interne
# ---------------------------------------------------------------------------


async def _call_generate(payload: dict) -> Optional[str]:
    """POST /api/generate — risposta singola stateless."""
    _ia_logger.debug(f"[HTTP] POST /api/generate | model={OLLAMA_MODEL}")
    try:
        session = _get_http_session()
        timeout = aiohttp.ClientTimeout(connect=10, total=OLLAMA_TIMEOUT)
        async with session.post(
            f"{OLLAMA_HOST}/api/generate", json=payload, timeout=timeout
        ) as resp:
            _ia_logger.debug(f"[HTTP] /api/generate → HTTP {resp.status}")
            if resp.status != 200:
                _parse_ollama_error(resp.status, await resp.text())
                return None
            data = await resp.json()
            text = data.get("response", "").strip()
            if not text:
                _ia_logger.warning("[RES] /api/generate risposta vuota.")
                return None
            _ia_logger.info(f"[RES] /api/generate | {len(text)} char ricevuti.")
            return text
    except asyncio.TimeoutError:
        _ia_logger.error(
            f"[ERRORE] Timeout {OLLAMA_TIMEOUT}s su /api/generate — "
            f"modello '{OLLAMA_MODEL}' troppo lento. "
            f"Abbassa OLLAMA_NUM_PREDICT (attuale: {OLLAMA_NUM_PREDICT}) "
            f"o alza OLLAMA_TIMEOUT nel .env."
        )
        return None
    except aiohttp.ClientConnectorError:
        _ia_logger.warning(f"[ERRORE] Connessione rifiutata a {OLLAMA_HOST}.")
        return None
    except aiohttp.ClientError as e:
        _ia_logger.error(f"[ERRORE] Rete /api/generate: {e}")
        return None
    except Exception as e:
        _ia_logger.error(f"[ERRORE] Imprevisto /api/generate: {e}")
        return None


async def _call_chat(payload: dict) -> Optional[str]:
    """
    POST /api/chat — risposta multi-turn con history.
    La risposta si trova in data["message"]["content"].
    """
    n_messages = len(payload.get("messages", []))
    _ia_logger.debug(
        f"[HTTP] POST /api/chat | model={OLLAMA_MODEL} | messages={n_messages}"
    )
    try:
        session = _get_http_session()
        timeout = aiohttp.ClientTimeout(connect=10, total=OLLAMA_TIMEOUT)
        async with session.post(
            f"{OLLAMA_HOST}/api/chat", json=payload, timeout=timeout
        ) as resp:
            _ia_logger.debug(f"[HTTP] /api/chat → HTTP {resp.status}")
            if resp.status != 200:
                _parse_ollama_error(resp.status, await resp.text())
                return None
            data = await resp.json()
            text = data.get("message", {}).get("content", "").strip()
            if not text:
                _ia_logger.warning("[RES] /api/chat risposta vuota.")
                return None
            _ia_logger.info(f"[RES] /api/chat | {len(text)} char ricevuti.")
            return text
    except asyncio.TimeoutError:
        _ia_logger.error(
            f"[ERRORE] Timeout {OLLAMA_TIMEOUT}s su /api/chat — "
            f"contesto troppo lungo o modello lento. "
            f"Usa /dimentica per azzerare la history."
        )
        return None
    except aiohttp.ClientConnectorError:
        _ia_logger.warning(f"[ERRORE] Connessione rifiutata a {OLLAMA_HOST}.")
        return None
    except aiohttp.ClientError as e:
        _ia_logger.error(f"[ERRORE] Rete /api/chat: {e}")
        return None
    except Exception as e:
        _ia_logger.error(f"[ERRORE] Imprevisto /api/chat: {e}")
        return None
