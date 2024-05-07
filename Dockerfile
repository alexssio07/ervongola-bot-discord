# Dockerfile
FROM python:3.9

WORKDIR /app

# Copia il tuo script Python nella directory di lavoro
COPY bot-discord.py .
COPY frasieffetto.json .

# Installa le librerie necessarie
RUN pip install --upgrade pip
RUN apt-get update
RUN apt-get install -y ffmpeg
# RUN pip install -r requirement.txt
RUN pip install PyNaCl
RUN pip install gtts 
RUN pip install ollama
RUN pip install langchain
RUN pip install numpy 
RUN pip install imageio
RUN pip install discord.py 

# Comando di default quando il container viene avviato
CMD ["python", "bot-discord.py"]
