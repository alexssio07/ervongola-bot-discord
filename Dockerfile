# Usa un'immagine Python compatibile con ARM
FROM arm64v8/python:3.11-slim

# Imposta la directory di lavoro
WORKDIR /app

# Copia il file requirements per installazioni efficienti
COPY requirements.txt ./

# Aggiorna i pacchetti e installa le dipendenze di sistema necessarie
RUN pip install --upgrade pip

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg libasound2 libnss3 libx11-xcb1 libxcb1 libxcomposite1 libxcursor1 libxi6 libxtst6 \
    libcups2 libdrm2 libgbm1 libpango-1.0-0 libpangocairo-1.0-0 libatspi2.0-0 libjpeg62-turbo libopus0 libxrandr2 libatk1.0-0 libatk-bridge2.0-0 && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Installa le librerie Python
RUN pip install --no-cache-dir -r requirements.txt


# Copia i file necessari nella directory di lavoro
COPY json/ ./json/
COPY . /app

# Comando di default quando il container viene avviato
CMD ["python", "bot-discord.py"]
