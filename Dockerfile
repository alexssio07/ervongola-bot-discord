FROM arm64v8/python:3.11-slim  # ← Base image ARM64 nativa

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

COPY . .
RUN mkdir -p json app/json

CMD ["python", "bot-discord.py"]