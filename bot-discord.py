import discord
from discord.ext import commands
from discord.ext.tasks import loop
from discord.utils import get
from gtts import gTTS
import asyncio
import os
import imageio
import random
import numpy as np
from ollama import Client
import ollama
import socket
import json

# Configurazioni
discord_token = (
    "MTIwNTU4NTEyMDE4NzI2MTAwMA.GQayKs.TrtrqBgt32wcl-9WtgQeSMjeTz0J646IfY4LD8"
)
key_api_personal_ai = "sk-d342ce6c42c241d3bf2a89a39e956033"
key_jwt_personal_ai = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6ImU5MjQ2NmI1LWY1ZjItNDBmYS1hYWFiLTNjM2U3MzRhN2E1MCJ9.Ad5WXhDevqgD47JP1uwqkRpSXZvnA5GhXxVLIfuBX9A"

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

frasideffetto = [
    "è entrato con prepotenza nel canale",
    "è scivolato per terra entrando nel buco del canale",
    "è entrato nel canale ruttando",
    "è entrato nel canale ruttando come un cinghiale inferocito",
    "è entrato nel canale portando con sè il suo gatto adorabile",
    "è entrato nel canale, porcodio!",
    "è entrato nel canale, dajee!",
    "è entrato nel canale per non farsi i cazzi suoi",
    "è entrato nel canale con il culo aperto",
    "è entrato nel canale segandosi",
    "è entrato nel canale sbattendo il mignolo del piede",
    "è entrato nel canale sbattendo la porta va là",
    "è entrato con il cazzo dritto",
    "è entrato bruciando la chiesa cattolica",
    "è entrato strafatto",
    "è entrato strafatto come na pigna",
    "è entrato nel canale dalla missione su Plutone",
    "è entrato nel canale rollando una canna",
    "è entrato nel canale rollando un cannone",
    "è entrato con le mutande smerdate",
    "è entrato con il cazzo dritto, daje!",
    "è entrato nel canale sbattendo la capoccia e si è fatto pure male...",
    "è entrato nel canale, porca madonna!",
    "è entrato nel canale a pecora",
    "è entrato prendendo a pisellate il muro",
    "è entrato nel canale prendendo il muro fratellì!",
    "è entrato nel canale sbattendo la cappella",
    "è entrato nel canale buber curwa!",
    "è entrato nel canale a caso",
    "è entrato nel canale sbattendo il mignolo sulla scrivania",
    "è entrato nel canale scureggiando",
    "è entrato nel canale, porcodio! Eh no! Non si dice!",
    "è entrato nel canale, onicchan... cazzo sto dicendo...",
    "è entrato nel canale insultando il papa",
    "è entrato nel canale con il porcodio addosso",
    "è entrato nel canale sbroccando",
    "è entrato nel canale sbroccando per la connessione",
    "è entrato nel canale sbroccando per la giornata di lavoro avuta oggi...",
    "è entrato nel canale, signora i limoni SIGNORA!!!",
    "è entrato nel canale bestemmiando per gli aggiornamenti della scheda video",
    "è entrato nel canale bestemmiando per la connessione",
    "è entrato nel canale dopo aver finito di cenare",
]


class FrasiConteggio:
    def __init__(self, data):
        self.frasi = data["frasi"]  # Carica le frasi dal JSON

    def salva_su_file(self, filename):
        with open(filename, "w") as file:
            json.dump({"frasi": self.frasi}, file)

    def incrementa_conteggio(self, frase, utente):
        for f in self.frasi:
            if f["text"] == frase:
                for u in f["user"]:
                    if u["name"] == utente:
                        u["count"] += 1
                        self.salva_su_file("frasieffetto.json")
                        break

    def frase_random(self, utente):
        frasi_disponibili = []
        probabilita = []
        for f in self.frasi:
            for u in f["user"]:
                if u["name"] == utente:
                    frasi_disponibili.append(f)
                    probabilita.append(
                        1 / (1 + u["count"])
                    )  # Modifica la probabilità in base al conteggio
                    break
                else:
                    # Se l'utente non ha frasi, aggiungilo con count 1 per ogni frase
                    f["user"].append({"count": 1, "name": utente})
                    frasi_disponibili.append(f)
                    probabilita.append(1)

        return random.choices(
            [f["text"] for f in frasi_disponibili], weights=probabilita
        )[0]


async def make_audio(member, channelKey):
    with open("frasi.json", "r") as file:
        data = json.load(file)
    frasi = FrasiConteggio(data)
    channel = bot.get_channel(int(channelKey))
    if (
        str(channel.id) == chat_vocale_privato
        or str(channel.id) == chat_vocale_privato2
        or str(channel.id) == chat_vocale_privato3
    ):
        try:
            frasedeffetto = frasi.frase_random(frasideffetto)
            custom_message = f"{'Burzum' if member.name == name_burzum or str(member.id) == id_burzum else member.name} {frasedeffetto}"
            custom_message = f"{'Pantera' if member.name == name_black_panthera else member.name} {frasedeffetto}"
            frasi.incrementa_conteggio(frasedeffetto, member.name)
            # custom_message = f"{'Melissa' if member.name == name_melissa else member.name} {np.random.choice(frasideffetto)}"
            # response = clientAI.audio.speech.create(
            #     model="tts-1", voice="fable", input=custom_message, response_format="aac"
            # )
            # response.write_to_file("welcome_message.mp3")
            tts = gTTS(custom_message, lang="it")
            tts.save("welcome_message.mp3")

            print(f"Channel: {channel}")
            print("Connecting to voice channel...", flush=True)

            if channel and isinstance(channel, discord.VoiceChannel):
                vc = await channel.connect()
                print("Connected to voice channel")
                vc.play(
                    discord.FFmpegPCMAudio("welcome_message.mp3"),
                    after=lambda e: print("Done", e),
                )
                while vc.is_playing():
                    print("Is playing...", flush=True)
                    await asyncio.sleep(1)
                await vc.disconnect()

            # Elimina il file audio dopo la riproduzione
            os.remove("welcome_message.mp3")
            print("File audio deleted", flush=True)
        except Exception as e:
            print(e)


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name} ({bot.user.id})", flush=True)
    check_online.start()


@loop(minutes=90)  # Controlla ogni 90 minuti
async def check_online():
    isOnAlexssio = False
    isOnLykanos = False
    dark_Lord = await bot.fetch_user(id_dark_lord)
    alexssio = await bot.fetch_user(id_alexssio)
    lykanos = await bot.fetch_user(id_lykanos)
    user = bot.get_all_members()
    for guild in bot.guilds:
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


@bot.event
async def on_message(message):
    if message.author.bot:
        return
    message_user = str(message.content)
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
            await message.reply(responseFormatted)
            print(responseFormatted, flush=True)
        except ollama.ResponseError as e:
            print(e, flush=True)
            await message.reply(
                f"Si è verificato un errore durante l'elaborazione della richiesta. {e}"
            )


@bot.event
async def on_voice_state_update(member, before, after):
    if after.self_stream:
        print(f"{member.name} sta trasmettendo uno streaming.")
    else:
        print(f"{member.name} non sta trasmettendo uno streaming.")

    if before.channel:
        print(f"canale prima {before.channel}", flush=True)
    if after.channel:
        print(f"canale dopo {after.channel}", flush=True)
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
        await make_audio(member, after.channel.id)
        return


client = Client(host="http://host.docker.internal:11434/api/generate -d")
# Inizializzazione bot Discord
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)
# Esegui il bot Discord
bot.run(discord_token)
