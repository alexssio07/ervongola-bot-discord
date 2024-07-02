import discord
from discord.ext import commands
from discord import app_commands
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
import generatoreblasfemie
import utils as ut
import scraper
next_asyncio = nest_asyncio.apply()
load_dotenv()

# Configurazioni
discord_token = os.getenv("DISCORD_TOKEN")
key_api_personal_ai = os.getenv("KEY_API_PERSONAL_AI")
key_jwt_personal_ai = os.getenv("KEY_JWT_PERSONAL_AI")

id_dark_lord = "271371380467957762"
chat_for_ai_id_discord = "1206179021134499841"
chat_blasfemie_id_discord = "1256877516224729149"
chat_vocale_privato = "707198443751211140"
chat_vocale_privato2 = "707514058990944256"
chat_vocale_privato3 = "783252026766131222"
chat_text_test_id = "1256593273246453823"

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
id_bot_ervongola = "1205585120187261000"

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
clientAI = Client(host="http://host.docker.internal:11434/api/generate -d")

audio_queue = asyncio.Queue()  # Coda per le richieste audio

# Inizializzazione bot Discord
intents = discord.Intents.all()
intents.message_content = True
botDiscord = commands.Bot(command_prefix="!", intents=intents)


# Questo metodo viene invocato quando il bot Discord viene avviato e viene inizializzato
@botDiscord.event
async def on_ready():
    botDiscord.loop.create_task(ut.Utils(botDiscord).audio_player())
    print(f"Logged in as {botDiscord.user.name} ({botDiscord.user.id})", flush=True)
    check_online.start()
    try:
        await botDiscord.tree.sync()
        print("Synced")
    except discord.Forbidden:
        print("Unexpected forbidden from application scope.")
    else:
        print("You must be the owner to use this command")


# Questo metodo verrà chiamato ogni 90 minuti in loop fino a quando il bot non viene interrotto
@loop(minutes=90)
async def check_online():
    isOnAlexssio = False
    isOnLykanos = False
    isOnDarkLord = False
    dark_Lord = await botDiscord.fetch_user(id_dark_lord)
    alexssio = await botDiscord.fetch_user(id_alexssio)
    # lykanos = await bot.fetch_user(id_lykanos)
    # user = bot.get_all_members()
    for guild in botDiscord.guilds:
        for member in guild.members:
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
@botDiscord.event
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
            await ut.Utils(botDiscord).make_audio(member, after.channel.id)


# Questo metodo cattura i messaggi testuali
@botDiscord.event
async def on_message(message):
    if message.author.bot:
        return
    message_user = str(message.content)
    for value in keysQuestionRoma:
        if value in message_user:
            print("hai domandato cose riguardo la Roma")
            await scraper.checkInfoFromSite()
            return
    if message_user != "" and message.channel.id == int(chat_for_ai_id_discord) or isinstance(message.channel, discord.DMChannel) or message.channel.id == int(chat_text_test_id):
        print(
            f"Messaggio ricevuto da {message.author}: {message_user}",
            flush=True,
        )
        try:
            response = clientAI.chat(
                model="gemma2",
                messages=[
                    {
                        "role": "user",
                        "content": message_user,
                    },
                ],
            )
            print(f"Response bot: {response}", flush=True)
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


async def get_info_bot(interaction: discord.Interaction):
    await interaction.response.send_message("Ecco le info riguardo il bot :")
    await interaction.channel.send(f"Sono un'assistente virtuale chiamato Er Vongola, super potente e cazzuto in grado di annunciare l'entrata di alcuni specifici utenti che lo desiderano, quando entrano in determinati canali vocali.") 
    await interaction.channel.send(f"Può assistervi come farebbe una vera intelligenza artificiale attraverso la chat testuale 'parla-con-l-ia' o attraverso la sua chat privata.")
    await interaction.channel.send(f"Scrivi / in una delle chat testuali a disposizione per visualizzare la lista dei comandi disponibili.")

@botDiscord.tree.command(name="ping",description="It will show the ping latecy of the bot")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"{round(botDiscord.latency * 1000)}ms")

@botDiscord.tree.command(name="info",description="Mostra le informazioni riguardo al bot e al suo utilizzo")
async def info(interaction: discord.Interaction):
    await get_info_bot(interaction)

@botDiscord.tree.command(name="help",description="Mostra aiuto e supporto riguardo al bot")
async def help(interaction: discord.Interaction):
    await get_info_bot(interaction)
    await interaction.response.send_message(f"Per altro supporto contatta gli amministratori del server: Alexssio, Lykanos")


# Funzione per generare casualmente una bestemmia scrivendola in chat e creando un file audio che riprodurrà immediatamente tramite il metodo text_to_speech
@botDiscord.tree.command(name="bestemmia",description="Il Bot Er Vongola entrerà nel canale vocale e invierà un tot bestemmie")
async def bestemmia(interaction: discord.Interaction, numerobestemmie: str):
    user = interaction.user
    voice_state = user.voice  
    if numerobestemmie == "":
        numerobestemmie = 1
    else:
        numerobestemmie = int(numerobestemmie)
    await interaction.response.send_message(f"Sto generando {numerobestemmie} bestemmie, eccole...")
    with open("blasfemia.json", "r") as file:
        data = json.load(file)
        startCounter = 1
        for startCounter in range(int(numerobestemmie)):
            custom_message = generatoreblasfemie.GeneratoreBlasfemie(data).frase_random()
            await interaction.channel.send(custom_message)
            await ut.Utils(botDiscord).text_to_speech(custom_message, startCounter, voice_state.channel.id)


@botDiscord.tree.command(name="barzeletta", description="Genera una barzeletta")
async def barzeletta(interaction: discord.Interaction):
    print("porco")
    await interaction.response.send_message(f"Sto generando una barzeletta, eccola...")
    try:
        response = clientAI.chat(
            model="gemma2",
            messages=[
                {
                    "role": "user",
                    "content": "raccontami una barzeletta divertente e spassosa in italiano",
                },
            ],
        )
        responseFormatted = response["message"]["content"]
        await interaction.channel.send(content=responseFormatted[:1999])
        if len(responseFormatted) >= 1999:
            for i in range(0, 1999, 1999):
                await interaction.channel.send(content=responseFormatted[i : i + 1999])
        print(responseFormatted, flush=True)
        await ut.Utils(botDiscord).text_to_speech(responseFormatted, "barzeletta", interaction.channel.id)
    except ollama.ResponseError as e:
        print(e, flush=True)
        await message.reply(
            f"Si è verificato un errore durante l'elaborazione della richiesta. {e}"
        )

@botDiscord.tree.command(name="freddura", description="Genera una battuta")
async def freddura(interaction: discord.Interaction):
    try:
        await interaction.response.send_message(f"Sto generando una freddura, eccola...")
        response = clientAI.chat(
            model="gemma2",
            messages=[
                {
                    "role": "user",
                    "content": "raccontami una freddura divertente oppure squallida oppure una battuta",
                },
            ],
        )
        responseFormatted = response["message"]["content"]
        await interaction.channel.send(content=responseFormatted[:1999])
        if len(responseFormatted) >= 1999:
            for i in range(0, 1999, 1999):
                await interaction.channel.send(content=responseFormatted[i : i + 1999])
        print(responseFormatted, flush=True)
        await ut.Utils(botDiscord).text_to_speech(responseFormatted, "freddura", interaction.channel.id)
    except ollama.ResponseError as e:
        print(e, flush=True)
        await message.reply(
            f"Si è verificato un errore durante l'elaborazione della richiesta. {e}"
        )

# Esegui il bot Discord
botDiscord.run(discord_token)
