"""
Feed delle attivita' del pannello (chi ha fatto cosa e dove), distribuito
in tempo reale ai browser via Server-Sent Events, come per i log.

Ring buffer in RAM (BUFFER_SIZE eventi): chi apre la pagina vede subito gli
ultimi eventi (marcati "replay": non devono far scattare refresh automatici).
Si azzera al riavvio del backend, per questo ogni evento porta anche "boot":
il client deduplica con la coppia (boot, id).
"""

import itertools
import json
import queue
import threading
import time
from collections import deque
from datetime import datetime, timezone

from flask import Blueprint, Response, stream_with_context

from auth import require_auth

BUFFER_SIZE = 300
MAX_TEXT = 300

bp = Blueprint("activity", __name__, url_prefix="/api/activity")

_BOOT = str(int(time.time()))
_buffer: deque = deque(maxlen=BUFFER_SIZE)
_subscribers: set = set()
_counter = itertools.count(1)
_lock = threading.Lock()


def publish(user: str, action: str, scope: str, text: str = "", old_text: str = "") -> None:
    """action: add | update | delete. scope: chiave file frasi oppure 'movies'."""
    with _lock:
        event = {
            "boot": _BOOT,
            "id": next(_counter),
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "user": user,
            "action": action,
            "scope": scope,
            "text": (text or "")[:MAX_TEXT],
            "old_text": (old_text or "")[:MAX_TEXT],
            "replay": False,
        }
        _buffer.append(event)
        subscribers = list(_subscribers)
    for q in subscribers:
        try:
            q.put_nowait(event)
        except queue.Full:
            pass  # client troppo lento: meglio perdere un evento che bloccare gli altri


def _subscribe() -> "queue.Queue[dict]":
    q: "queue.Queue[dict]" = queue.Queue(maxsize=500)
    with _lock:
        _subscribers.add(q)
        history = list(_buffer)
    for event in history:
        q.put_nowait({**event, "replay": True})
    return q


def _unsubscribe(q) -> None:
    with _lock:
        _subscribers.discard(q)


@bp.get("/stream")
@require_auth
def stream_activity():
    q = _subscribe()

    @stream_with_context
    def generate():
        try:
            while True:
                try:
                    event = q.get(timeout=15)
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                except queue.Empty:
                    yield ": keep-alive\n\n"
        finally:
            _unsubscribe(q)

    response = Response(generate(), mimetype="text/event-stream")
    response.headers["Cache-Control"] = "no-cache"
    response.headers["X-Accel-Buffering"] = "no"
    return response
