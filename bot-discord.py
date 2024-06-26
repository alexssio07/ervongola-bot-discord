import discord
from discord.ext import commands
from discord.ext.tasks import loop
from discord.utils import get
from gtts import gTTS
from dotenv import load_dotenv
import asyncio
import os
import numpy as np
from ollama import Client
import ollama
import json
import streamlit as st
from scrapegraphai.graphs import SmartScraperGraph
import nest_asyncio

import frasiconteggio
import scraper
next_asyncio = nest_asyncio.apply()
load_dotenv()

# Configurazioni
discord_token = os.getenv("DISCORD_TOKEN")
key_api_personal_ai = os.getenv("KEY_API_PERSONAL_AI")
key_jwt_personal_ai = os.getenv("KEY_JWT_PERSONAL_AI")

id_dark_lord = "271371380467957762"
chat_id_discord = "1206179021134499841"
chat_vocale_privato = "707198443751211140"
chat_vocale_privato2 = "707514058990944256"
chat_vocale_privato3 = "783252026766131222"

name_dark_lord = "6dark6lord6"
id_alexssio = "190745296500686857"
name_alexssio = "alexssio"
id_lykanos = "366952021045280779"
name_lykanos = "lykanos94"
id_burzum = "303199273418489857"
name_burzum = "crypo1398"
id_black_panthera = "399979832038916101"
name_black_panthera = "blackpanthera666"
id_melissa = "293497922870312961"
name_melissa = "ismerisa"

message = "Lykanos e Alexssio sono online, se vuoi vai a fargli compagnia... Stronzo."
isOnAlexssio = False
isOnLykanos = False
keysQuestionRoma = [
    "As Roma",
    "as roma",
    "partite",
    "partita",
    "biglietti",
    "biglietto",
]
client = Client(host="http://host.docker.internal:11434/api/generate -d")

audio_queue = asyncio.Queue()  # Coda per le richieste audio

# Inizializzazione bot Discord
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)


async def make_audio(member, channelKey):
    # Apro la comunicazione con il file JSON per ottenermi la lista delle frasi
    with open("frasieffetto.json", "r") as file:
        data = json.load(file)
    frasi = frasiconteggio.FrasiConteggio(data)
    # Ottengo il canale tramite il channelKey
    channel = bot.get_channel(int(channelKey))
    # Controllo se l'utente è entrato in quel determinato canale
    if str(channel.id) in [
        chat_vocale_privato,
        chat_vocale_privato2,
        chat_vocale_privato3,
    ]:
        # Genero una frase casuale tramite il metodo frase_random della classe FrasiConteggio
        frasedeffetto = frasi.frase_random(member.name)
        if str(member.name) == name_burzum:
            custom_message = f"Burzum {frasedeffetto}"
        elif str(member.id) == id_black_panthera:
            custom_message = f"Pantera {frasedeffetto}"
        elif str(member.name) == name_melissa:
            custom_message = f"Melissa {frasedeffetto}"
        else:
            custom_message = f"{member.name} {frasedeffetto}"

        # Genero il file audio contenente la frase costruita precedentemente
        tts = gTTS(custom_message, lang="it")
        # Salvo il file audio con il nome del membro associato
        tts.save(f"welcome_message_{member.name}.mp3")

        print(f"Channel: {channel}", flush=True)
        print("Connecting to voice channel...", flush=True)
        try:
            if channel and isinstance(channel, discord.VoiceChannel):
                await audio_queue.put((channel, f"welcome_message_{member.name}.mp3"))
        except Exception as e:
            print(f"Error: {e}", flush=True)


# Questo metodo connette il bot al canale vocale se il canale non è vuoto e riproduce il file audio, 
# rimane in attesa 3 secondi per permettere di aggiungersi altri file in coda da riprodurre successivamente
async def audio_player():
    while True:
        channel, file_name = await audio_queue.get()
        try:
            vc = await channel.connect()
            #elif vc.channel.id != channel.id:
            #   await vc.move_to(channel)
            vc.play(discord.FFmpegPCMAudio(file_name))
            while vc.is_playing():
                await asyncio.sleep(3)
            os.remove(file_name)
            if vc and vc.is_connected():
                await vc.disconnect()
            audio_queue.task_done()
        except Exception as e:
            print(f"Error: {e}", flush=True)


# Questo metodo viene invocato quando il bot Discord viene avviato e viene inizializzato
@bot.event
async def on_ready():
    bot.loop.create_task(audio_player())
    print(f"Logged in as {bot.user.name} ({bot.user.id})", flush=True)
    check_online.start()


# Questo metodo verrà chiamato ogni 90 minuti in loop fino a quando il bot non viene interrotto
@loop(minutes=90)
async def check_online():
    isOnAlexssio = False
    isOnLykanos = False
    isOnDarkLord = False
    dark_Lord = await bot.fetch_user(id_dark_lord)
    alexssio = await bot.fetch_user(id_alexssio)
    # lykanos = await bot.fetch_user(id_lykanos)
    # user = bot.get_all_members()
    for guild in bot.guilds:
        for member in guild.members:
            print("channel ok")
            if name_alexssio == member.name:
                if member.status == discord.Status.online:
                    isOnAlexssio = True
            if name_lykanos == member.name:
                if member.status == discord.Status.online:
                    isOnLykanos = True

    if isOnAlexssio and isOnLykanos:
        await dark_Lord.send(message)
        await alexssio.send(message)

# Questo metodo viene invocato ogni volta che c'è un cambio di stato sul member e su quale canale si è spostato
@bot.event
async def on_voice_state_update(member, before, after):
    # if after.self_stream:
    #     print(f"{member.name} sta trasmettendo uno streaming.")
    # else:
    #     print(f"{member.name} non sta trasmettendo uno streaming.")

    # if before.channel:
    #     print(f"canale prima {before.channel}", flush=True)
    # if after.channel:
    #     print(f"canale dopo {after.channel}", flush=True)

    if (
        (
            member.name == name_alexssio
            or member.name == name_lykanos
            or member.name == name_dark_lord
            or member.name == name_burzum
            or member.name == name_black_panthera
            or member.name == name_melissa
        )
        and not (after.self_stream)
        and not (after.self_video)
        and before.channel != after.channel
    ):
        if after.channel:
            await make_audio(member, after.channel.id)

# Questo metodo viene invocato ogni volta che il bot riceve un messaggio
@bot.event
async def on_message(message):
    if message.author.bot:
        return
    message_user = str(message.content)
    for value in keysQuestionRoma:
        if value in message_user:
            print("hai domandato cose riguardo la Roma")
            await scraper.checkInfoFromSite()
            return
    print(f"Messaggio ricevuto da {message.author}: {message_user}", flush=True)
    if message.channel.id == int(chat_id_discord):
        print(message_user)
    if message_user != "":
        print(
            f"Messaggio ricevuto da {message.author}: {message_user}",
            flush=True,
        )
        try:
            response = client.chat(
                model="llama3",
                messages=[
                    {
                        "role": "user",
                        "content": message_user,
                    },
                ],
            )
            responseFormatted = response["message"]["content"]
            await message.channel.send(content=responseFormatted[:1999])
            if len(responseFormatted) >= 1999:
                for i in range(0, 1999, 1999):
                    await message.channel.send(content=responseFormatted[i : i + 1999])
            print(responseFormatted, flush=True)
        except ollama.ResponseError as e:
            print(e, flush=True)
            await message.reply(
                f"Si è verificato un errore durante l'elaborazione della richiesta. {e}"
            )

# Esegui il bot Discord
bot.run(discord_token)
