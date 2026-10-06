import logging
import os

from flask import Flask
from flask_cors import CORS

import config
import db
from auth_routes import bp as auth_bp
from frontend import bp as frontend_bp
from logs import bp as logs_bp
from movies import bp as movies_bp
from phrases import bp as phrases_bp

logging.basicConfig(
    level=logging.INFO,
    format="[{asctime}] [{levelname}] {message}",
    style="{",
    datefmt="%d/%m/%Y %H:%M:%S",
)
logger = logging.getLogger("panel")

app = Flask(__name__)
CORS(app, origins=config.CORS_ALLOWED_ORIGINS, supports_credentials=True)

app.register_blueprint(auth_bp)
app.register_blueprint(movies_bp)
app.register_blueprint(phrases_bp)
app.register_blueprint(logs_bp)
# Ultimo apposta: espone il build del frontend con una route catch-all
# ("/", "/<path:path>"). Non ruba richieste a "/api/..." — vedi frontend.py.
app.register_blueprint(frontend_bp)


@app.get("/api/health")
def health():
    return {"status": "ok"}


def _startup_checks() -> None:
    db.init_db()
    if not config.ADMIN_PASSWORD_HASH:
        logger.warning(
            "ADMIN_PASSWORD_HASH non impostato in api/.env: il login sarà sempre rifiutato. "
            "Genera un hash con 'python hash_password.py <password>'."
        )
    if config.SECRET_KEY.startswith("CHANGE-ME") or config.LOG_INGEST_TOKEN.startswith("CHANGE-ME"):
        logger.warning(
            "SECRET_KEY e/o LOG_INGEST_TOKEN sono ancora ai valori di default in api/.env: "
            "impostali prima di esporre il pannello oltre la tua rete locale."
        )
    if not config.BOT_JSON_DIR.exists():
        logger.warning(
            "La cartella json del bot non esiste nel percorso atteso: %s", config.BOT_JSON_DIR
        )


_startup_checks()


if __name__ == "__main__":
    # threaded=True è necessario: senza, il server di sviluppo Werkzeug è
    # single-thread e un solo client connesso alla pagina Log live (SSE,
    # connessione tenuta aperta) bloccherebbe TUTTE le altre richieste
    # (login, film, frasi) finché quel client non si disconnette.
    debug_mode = os.getenv("FLASK_DEBUG", "true").strip().lower() == "true"
    app.run(port=5000, debug=debug_mode, threaded=True)
