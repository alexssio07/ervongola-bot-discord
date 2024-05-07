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


client = Client(host="http://host.docker.internal:11434/api/generate -d")


class FrasiConteggio:
    def __init__(self, data):
        self.frasi = data["frasi"]  # Carica le frasi dal JSON

    def salva_su_file(self, filename):
        with open(filename, "w") as file:
            json.dump({"frasi": self.frasi}, file)

    def frase_random(self, utente):
        # Lista dei pesi delle frasi
        pesi = []
        # Calcola il peso per ogni frase
        for frase in self.frasi:
            # Somma di count o del conteggio per tutti gli utenti di ogni frase
            count_totale = sum(user["count"] for user in frase["users"])
            # Calcola il peso basato sulla somma dei count e una costante arbitraria
            peso = 1 / (count_totale + 1)  # +1 per evitare divisione per zero
            pesi.append(peso)

        # Genera un numero casuale basato sui pesi delle frasi
        indice_frase_selezionata = random.choices(range(len(self.frasi)), weights=pesi)[
            0
        ]

        wasFound = False
        for user in self.frasi[indice_frase_selezionata]["users"]:
            # Cerca se l'utente ha già eseguito quella determinata frase corrispondente
            # all'indice generato casualmente
            if user["name"] == utente:
                # Incrementa il valore di count per la frase selezionata
                user["count"] += 1
                self.salva_su_file("frasieffetto.json")
                wasFound = True
                break
            else:
                wasFound = False
        # Se l'utente non ha frasi, aggiungilo per quella specifica frase
        if not (wasFound):
            self.frasi[indice_frase_selezionata]["users"].append(
                {"count": 1, "name": utente}
            )
            # Aggiorna il JSON
            self.salva_su_file("frasieffetto.json")

        # Restituisci la frase selezionata
        return self.frasi[indice_frase_selezionata]["text"]


# Inizializzazione bot Discord
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)


async def make_audio(member, channelKey):
    with open("frasieffetto.json", "r") as file:
        data = json.load(file)
    frasi = FrasiConteggio(data)
    # Ottengo il canale tramite il channelKey
    channel = bot.get_channel(int(channelKey))
    # Controllo se l'utente è entrato in quel determinato canale
    if (
        str(channel.id) == chat_vocale_privato
        or str(channel.id) == chat_vocale_privato2
        or str(channel.id) == chat_vocale_privato3
    ):
        try:
            # Genero una frase casuale tramite il metodo frase_random della classe FrasiConteggio
            frasedeffetto = frasi.frase_random(member.name)
            custom_message = f"{'Burzum' if str(member.id) == id_burzum else member.name} {frasedeffetto}"
            custom_message = f"{'Pantera' if member.name == name_black_panthera else member.name} {frasedeffetto}"
            # custom_message = f"{'Melissa' if member.name == name_melissa else member.name} {np.random.choice(frasideffetto)}"

            # Genero il file audio contenente la frase costruita precedentemente
            tts = gTTS(custom_message, lang="it")
            # Salvo il file audio
            tts.save("welcome_message.mp3")

            print(f"Channel: {channel}", flush=True)
            print("Connecting to voice channel...", flush=True)

            # Verifica che sia un canale vocale e creando il client per la connessione
            if channel and isinstance(channel, discord.VoiceChannel):
                # Connessione al canale
                vc = await channel.connect()
                print("Connected to voice channel")
                # Riproduzione del file audio
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
        if after.channel:
            await make_audio(member, after.channel.id)
        return


# Esegui il bot Discord
bot.run(discord_token)
