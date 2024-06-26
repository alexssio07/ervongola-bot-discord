# Dockerfile
FROM python:3.10

WORKDIR /app

# Copia il tuo script Python nella directory di lavoro
COPY bot-discord.py .
COPY frasiconteggio.py .
COPY scraper.py .
COPY frasieffetto.json .

# Installa le librerie necessarie
RUN pip install --upgrade pip
RUN apt-get update
RUN apt-get install -y ffmpeg
# RUN pip install -r requirement.txt
RUN pip install setuptools-rust
RUN pip install playwright
RUN pip install PyNaCl
RUN pip install gtts 
RUN pip install ollama
RUN pip install langchain
RUN pip install streamlit
RUN pip install nest_asyncio
RUN pip install -U openai-whisper
RUN pip install scrapegraphai
RUN pip install numpy 
RUN pip install imageio
RUN pip install discord.py 

# Comando di default quando il container viene avviato
CMD ["python", "bot-discord.py"]
