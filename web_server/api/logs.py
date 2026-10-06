"""
Due canali separati per i log, con due segreti diversi:

1. POST /api/logs/ingest — il BOT (processo separato) manda qui le righe di
   log, autenticandosi con un token condiviso (LOG_INGEST_TOKEN). Non usa il
   login admin: il bot non ha (e non deve avere) una sessione utente.

2. GET  /api/logs/stream — il FRONTEND si collega qui (Server-Sent Events)
   per ricevere i log in diretta, autenticandosi con il token di sessione
   admin passato come query param (?token=...), perché EventSource non
   permette di impostare header custom come Authorization.
"""

import queue

from flask import Blueprint, Response, jsonify, request, stream_with_context

import config
import log_broadcaster as lb
from auth import require_auth

bp = Blueprint("logs", __name__, url_prefix="/api/logs")


@bp.post("/ingest")
def ingest_logs():
    token = request.headers.get("X-Ingest-Token", "")
    if token != config.LOG_INGEST_TOKEN:
        return jsonify({"error": "Token non valido."}), 401

    payload = request.get_json(silent=True) or {}
    lines = payload.get("lines", [])
    for line in lines:
        lb.publish(
            {
                "timestamp": line.get("timestamp", ""),
                "level": line.get("level", "INFO"),
                "logger": line.get("logger", ""),
                "message": line.get("message", ""),
            }
        )

    return jsonify({"received": len(lines)}), 202


@bp.get("/stream")
@require_auth
def stream_logs():
    q = lb.subscribe()

    @stream_with_context
    def generate():
        try:
            while True:
                try:
                    line = q.get(timeout=15)
                    yield lb.format_sse(line)
                except queue.Empty:
                    yield ": keep-alive\n\n"  # commento SSE: tiene viva la connessione
        finally:
            lb.unsubscribe(q)

    response = Response(generate(), mimetype="text/event-stream")
    response.headers["Cache-Control"] = "no-cache"
    response.headers["X-Accel-Buffering"] = "no"  # disabilita il buffering di nginx, se presente
    return response
