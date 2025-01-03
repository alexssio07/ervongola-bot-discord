# Dockerfile
FROM python:3.10-slim

WORKDIR /app

# Copia solo requirements.txt per usare la cache
COPY requirements.txt ./
# RUN pip install --no-cache-dir -r requirements.txt


# Copia il tuo script Python nella directory di lavoro
COPY json/ ./app/json/
COPY . /app
COPY voice_manager.py ./app
COPY utils.py ./app
COPY frasiconteggio.py ./app
COPY generatoreblasfemie.py ./app
COPY scraper.py ./app
COPY bot-discord.py ./app

# Installa le librerie necessarie
RUN apt-get update
RUN apt-get install -y ffmpeg
RUN pip install --upgrade pip
#RUN pip install --no-cache-dir -r requirements.txt
RUN pip install setuptools-rust
RUN pip install python-dotenv
RUN pip install yt-dlp
RUN pip install playwright
RUN pip install PyNaCl
RUN pip install gtts 
RUN pip install ollama
RUN pip install langchain
RUN pip install streamlit
RUN pip install nest_asyncio
RUN pip install whisper
RUN pip install SpeechRecognition
RUN pip install burr
RUN pip install scrapegraphai
RUN pip install imageio
RUN pip install discord.py 

# Installa ffmpeg
# RUN apt-get update && \
#     apt-get install -y ffmpeg && \
#     apt-get clean && rm -rf /var/lib/apt/lists/*

# Comando di default quando il container viene avviato
CMD ["python", "/app/bot-discord.py"]
