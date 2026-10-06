# --- Stage 1: build di produzione del frontend React (web_server/) -------
# Stage separato solo per compilare il frontend con Node: non finisce nella
# immagine finale (nessun binario Node nell'immagine di runtime), evita di
# copiare web_server/node_modules (enorme e installato per Windows sul PC
# di sviluppo, incompatibile con l'immagine Linux/arm64 finale).
FROM node:20-slim AS frontend-build
WORKDIR /frontend
COPY web_server/package.json web_server/package-lock.json ./
RUN npm ci
COPY web_server/ ./
RUN npm run build

# --- Stage 2: bot Discord + pannello web, nello stesso container ----------
# Scelta dell'utente: un solo container Docker avvia sia bot-discord.py sia
# il pannello (Flask+gunicorn, che serve anche il build React), invece di
# due servizi separati. Vedi docker-entrypoint.sh per la gestione dei due
# processi (se uno muore, l'altro viene fermato e il container esce, così
# "restart: unless-stopped" in docker-compose.yml riavvia un container
# pulito invece di lasciarne uno vivo a metà).
FROM arm64v8/python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libopus0 \
    libopus-dev \
    libsodium23 \
    libsodium-dev \
    libffi-dev \
    python3-dev \
    build-essential \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir --upgrade pip setuptools wheel

RUN pip install --no-cache-dir "discord.py[voice]==2.7.1"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN pip install --no-cache-dir --pre discord-ext-voice-recv

# Dipendenze del pannello web (Flask, gunicorn, ...): file separato dal bot,
# copiato prima del resto per sfruttare la cache dei layer Docker come si fa
# già sopra per requirements.txt del bot.
COPY web_server/api/requirements.txt web_server/api/requirements.txt
RUN pip install --no-cache-dir -r web_server/api/requirements.txt

COPY . .
RUN mkdir -p json app/json

# Sovrascrive web_server/dist con il build fatto nello stage frontend-build
# qui sopra (quello eventualmente presente sul PC di sviluppo è per
# "npm run dev" ed è comunque escluso da .dockerignore).
COPY --from=frontend-build /frontend/dist web_server/dist

RUN chmod +x docker-entrypoint.sh

CMD ["./docker-entrypoint.sh"]
