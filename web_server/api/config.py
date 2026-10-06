"""
Configurazione centrale del backend Flask, letta da variabili d'ambiente
(api/.env, caricato da python-dotenv).

Nessuna nuova dipendenza rispetto a quelle già presenti nel progetto:
Flask porta con sé sia Werkzeug (per l'hashing password, vedi auth.py) sia
itsdangerous (per firmare i token di sessione), quindi non serve aggiungere
PyJWT/bcrypt/SQLAlchemy solo per un pannello a un utente con una tabella sola.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# api/config.py -> api/ -> web_server/ -> Discord/ (root del repo del bot,
# la stessa cartella che contiene bot-discord.py e json/). Stessa identica
# logica già usata dal vecchio app.py (BASE_DIR), qui centralizzata e resa
# sovrascrivibile via env var per chi sposta la cartella.
_API_DIR = Path(__file__).resolve().parent
_REPO_ROOT_DEFAULT = _API_DIR.parent.parent

REPO_ROOT = Path(os.getenv("BOT_REPO_ROOT", str(_REPO_ROOT_DEFAULT)))
BOT_JSON_DIR = Path(os.getenv("BOT_JSON_DIR", str(REPO_ROOT / "json")))

DATA_DIR = _API_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DATABASE_PATH = Path(os.getenv("DATABASE_PATH", str(DATA_DIR / "panel.db")))

# Build di produzione del frontend (generato con "npm run build" in web_server/),
# servito da Flask stesso quando bot e pannello girano nello stesso container
# (vedi frontend.py e il Dockerfile alla root della repo). In sviluppo locale
# questa cartella non esiste: resta a Vite servire il frontend sulla 5173.
FRONTEND_DIST_DIR = Path(os.getenv("FRONTEND_DIST_DIR", str(_API_DIR.parent / "dist")))

# --- Autenticazione (un solo utente admin, niente tabella utenti) ---
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD_HASH = os.getenv("ADMIN_PASSWORD_HASH", "")

# --- Token di sessione (itsdangerous, incluso in Flask) ---
SECRET_KEY = os.getenv("SECRET_KEY", "CHANGE-ME-please-set-a-real-secret-in-.env")
TOKEN_MAX_AGE_SECONDS = int(os.getenv("TOKEN_MAX_AGE_MINUTES", "720")) * 60  # 12 ore di default

# --- Ingest log dal bot (segreto macchina-macchina, diverso dal login admin) ---
LOG_INGEST_TOKEN = os.getenv("LOG_INGEST_TOKEN", "CHANGE-ME-please-set-a-real-token-in-.env")
LOG_BUFFER_SIZE = int(os.getenv("LOG_BUFFER_SIZE", "1000"))

# --- CORS ---
# In sviluppo il proxy di Vite (vedi vite.config.ts) rende CORS superfluo;
# resta utile se il frontend viene servito da un'origine diversa in produzione.
CORS_ALLOWED_ORIGINS = [
    o.strip() for o in os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:5173").split(",") if o.strip()
]
