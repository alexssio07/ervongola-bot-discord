import re
import discord
import asyncio
from gtts import gTTS
import json

# import whisper
import frasiconteggio as frasiconteggio
import os
import uuid
import yt_dlp as youtube_dl
import voice_manager as vc

# import speech_recognition as sr

audio_queue = asyncio.Queue()  # Coda per le richieste audio
stop_event = asyncio.Event()  # Evento per fermare le operazioni asincrone

# model = whisper.load_model("small")

# Lista di parole chiave e comandi associati
keyword_commands = {
    "vongola": "disconnect",
    "ciao bot": "greet",
    "riproduci": "play_audio",
}

chat_vocale_privato = "707198443751211140"
chat_vocale_privato2 = "707514058990944256"
chat_vocale_privato3 = "783252026766131222"
chats = ["chat_vocale_privato", "chat_vocale_privato2", "chat_vocale_privato3"]
id_users = {
    "alexssio": "190745296500686857",
    "lykanos": "366952021045280779",
    "dark_lord": "271371380467957762",
    "moonpantherredxvi": "399979832038916101",
    "melissa": "293497922870312961",
    "burzum": "303199273418489857",
    "carmineg": "275725325348896769",
    "speransia": "262262693103140864",
}
READ_NEWS_FILE = "json/read_news.json"
AUDIO_FOLDER = "./audio_files/"

# recognizer = sr.Recognizer()


async def text_to_speech(botDiscord, custom_message, another_text_message, channelId):
    channelPrivato = botDiscord.get_channel(int(chat_vocale_privato))
    fromChannel = botDiscord.get_channel(channelId)
    tts = gTTS(custom_message, lang="it")
    # Salvo il file audio con il nome del membro associato
    tts.save(f"audio_{another_text_message}.mp3")
    print(f"Message/command received by channel: {fromChannel}", flush=True)
    try:
        if not (fromChannel and isinstance(fromChannel, discord.VoiceChannel)):
            print("Connecting to voice channel...", flush=True)
            await audio_queue.put((channelPrivato, f"audio_{another_text_message}.mp3"))
        else:
            print("Connecting to voice channel...", flush=True)
            await audio_queue.put((fromChannel, f"audio_{another_text_message}.mp3"))
    except Exception as e:
        raise Exception(f"Error: {e}", flush=True)


async def make_audio(botDiscord, member, channelKey):
    if stop_event.is_set():  # Verifica se il comando di stop è stato dato
        return  # Esce immediatamente se lo stop è attivo
    # Apro la comunicazione con il file JSON per ottenermi la lista delle frasi
    with open("json/frasieffetto.json", "r", encoding="utf-8") as file:
        data = json.load(file)
    frasi = frasiconteggio.FrasiConteggio(data)
    # Ottengo il canale tramite il channelKey
    channel = botDiscord.get_channel(int(channelKey))
    # Controllo se l'utente è entrato in quel determinato canale
    if str(channel.id) in [
        chat_vocale_privato,
        chat_vocale_privato2,
        chat_vocale_privato3,
    ]:
        # Genero una frase casuale tramite il metodo frase_random della classe FrasiConteggio
        frasedeffetto = frasi.frase_random(member.name)
        if str(member.id) == id_users["burzum"]:
            custom_message = f"Burzum {frasedeffetto}"
        elif str(member.id) == id_users["moonpantherredxvi"]:
            custom_message = f"Pantera {frasedeffetto}"
        elif str(member.id) == id_users["melissa"]:
            custom_message = f"Melissa {frasedeffetto}"
        elif str(member.id) == id_users["alexssio"]:
            custom_message = f"Alexssìo {frasedeffetto}"
        elif str(member.id) == id_users["carmineg"]:
            custom_message = f"Carmine {frasedeffetto}"
        elif str(member.id) == id_users["speransia"]:
            custom_message = f"Milla {frasedeffetto}"
        elif str(member.id) == id_users["dark_lord"]:
            custom_message = f"Dark Lord {frasedeffetto}"
        elif str(member.id) == id_users["lykanos"]:
            custom_message = f"Lykanos {frasedeffetto}"
        await text_to_speech(
            botDiscord,
            custom_message,
            f"welcome_message_{member.name}_{str(uuid.uuid4())}",
            channel.id,
        )


async def play_youtube_video(interaction: discord.Interaction, url: str, volume: int):
    loop = asyncio.get_event_loop()
    user = interaction.user
    voice_state = user.voice
    if voice_state is None or voice_state.channel is None:
        await interaction.response.send_message(
            "Devi essere connesso a un canale vocale per utilizzare questo comando.",
            ephemeral=True,
        )
        return
    channel = voice_state.channel
    # Connetti il bot al canale vocale
    if vc.current_vc is None or not vc.current_vc.is_connected():
        vc.current_vc = await channel.connect()
    else:
        if vc.current_vc.channel == channel:
            vc.current_vc.stop()
        else:
            await vc.current_vc.disconnect()
            vc.current_vc = await channel.connect()

    def download_complete(d):
        if stop_event.is_set():  # Verifica se il comando di stop è stato dato
            return  # Esce immediatamente se lo stop è attivo
        if d["status"] == "finished":
            print(f"Download completato: {d['filename']}")
            asyncio.run_coroutine_threadsafe(
                interaction.response.send_message(
                    f"Download completato: {d['filename']}", ephemeral=True
                ),
                loop,
            )

    # Scarica l'audio dal link YouTube
    ydl_opts_audio = {
        "format": "bestaudio/best",
        "outtmpl": "audio.%(ext)s",
        "progress_hooks": [download_complete],
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "320",
            }
        ],
    }
    await interaction.response.defer()  # Rinvia la risposta dell'utente
    with youtube_dl.YoutubeDL(ydl_opts_audio) as ydl:
        info = ydl.extract_info(url, download=True)
        title = info.get("title", "Audio")
        file = f"audio.{ydl_opts_audio['postprocessors'][0]['preferredcodec']}"

    def after_playing(error):
        if error:
            print(f"Errore durante la riproduzione: {error}")
        # Elimina il file dopo la riproduzione
        if os.path.exists(file):
            os.remove(file)
            print(f"Eliminato: {file}")

    # Riproduci l'audio
    if file is None or file == "":
        await interaction.response.send_message(
            "Impossibile trovare l'audio.", ephemeral=True
        )
        return
    volume_filter = f"volume={volume / 100.0}"
    ffmpeg_options = f"-af '{volume_filter}'"
    vc.current_vc.play(
        discord.FFmpegPCMAudio(file, options=ffmpeg_options), after=after_playing
    )
    await interaction.followup.send(
        f"Inizio a riprodurre l'audio {title} con link {url} con volume al {volume}%"
    )


async def stop(interaction: discord.Interaction):
    stop_event.set()  # Imposta l'evento di stop per fermare tutte le operazioni asincrone

    print(f"current_vc is none: {vc.current_vc is None}")
    if vc.current_vc and vc.current_vc.is_playing():
        vc.current_vc.stop()
        await vc.current_vc.disconnect()
        vc.current_vc = None
        await interaction.response.send_message(
            "Riproduzione interrotta e disconnesso dal canale vocale."
        )
    else:
        await interaction.response.send_message("Nessuna riproduzione in corso.")
    if vc.current_vc and vc.current_vc.is_playing():
        interaction.response.send_message("Riproduzione in corso...")
    # Attendere fino alla fine della riproduzione
    while vc.current_vc and vc.current_vc.is_playing():
        await asyncio.sleep(1)
    # Questo metodo connette il bot al canale vocale se il canale non è vuoto e riproduce il file audio,
    # rimane in attesa 3 secondi per permettere di aggiungersi altri file in coda da riprodurre successivamente


async def audio_player():
    while True:
        if stop_event.is_set():  # Verifica se il comando di stop è stato dato
            break  # Esce dal loop se lo stop è attivo
        channel, file_name = await audio_queue.get()
        try:
            vc.current_vc = await channel.connect()
            # elif vc.channel.id != channel.id:
            #   await vc.move_to(channel)
            vc.current_vc.play(discord.FFmpegPCMAudio(file_name))
            while vc.current_vc.is_playing():
                await asyncio.sleep(4)
            os.remove(file_name)
            if vc.current_vc and vc.current_vc.is_connected():
                await vc.current_vc.disconnect()
            audio_queue.task_done()
        except Exception as e:
            print(f"Error: {e}", flush=True)


async def enumerate_messages(aiterator):
    index = 0
    async for item in aiterator:
        yield index, item
        index += 1


def load_read_news():
    try:
        if os.path.exists(READ_NEWS_FILE):
            with open(READ_NEWS_FILE, "r", encoding="utf-8") as file:
                return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return []  # Se il file non esiste o è vuoto, restituisci un array vuoto


def save_read_news(news_url):
    with open(READ_NEWS_FILE, "w", encoding="utf-8") as file:
        json.dump(news_url, file, ensure_ascii=False, indent=4)
        print(f"News saved: {news_url}", flush=True)


async def save_news_and_speech(
    botDiscord,
    interaction: discord.Interaction,
    message,
    index,
    channel_news,
):
    news = {"userId": interaction.user.id, "news": message.content}
    data = load_read_news()
    data.append(news)
    save_read_news(data)
    await text_to_speech(
        botDiscord,
        message.content,
        f"news_by_channel_{channel_news.id}_{index}",
        interaction.channel.id,
    )


async def process_news(
    botDiscord, interaction: discord.Interaction, message, index, channel_news
):
    patternUrl = r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
    patternAttachedImage = r"^~media\/.*\.(jpg|png|jpeg|gif|bmp|tiff|webp)$"
    message.content = re.sub(patternUrl, "", message.content)
    message.content = re.sub(patternAttachedImage, "", message.content)
    user_founded = any(
        entry["userId"] == interaction.user.id for entry in load_read_news()
    )
    news_founded = any(entry["news"] == message.content for entry in load_read_news())
    if not (user_founded) or not (news_founded):
        await save_news_and_speech(
            botDiscord, interaction, message, index, channel_news
        )
        return True
    return False


async def process_free_videogames(message):
    name_videogame = ""
    patternVideogame = r"^(.*?)\sfree from"
    patternGog = r"^(.*?)\sfree from GOG.com"
    patternSteam = r"^(.*?)\sfree in the Steam store"
    patternEpic = r"^(.*?)\sfrom Epic Games store"
    matchNameVideogame = re.search(patternVideogame, message)
    matchGog = re.search(patternGog, message)
    matchSteam = re.search(patternSteam, message)
    matchEpic = re.search(patternEpic, message)
    if matchNameVideogame:
        name_videogame = matchNameVideogame.group(1)
    if matchSteam:
        isFromSteam = matchSteam.group(1)
        return f"{name_videogame} e' disponibile su Steam"
    if matchGog:
        isFromGog = matchGog.group(1)
        return f"{name_videogame} e' disponibile sull app di GOG.com"
    if matchEpic:
        isFromEpic = matchEpic.group(1)
        return f"{name_videogame} e' disponibile sullo store di Epic"


async def leggi_notizie(
    botDiscord, interaction: discord.Interaction, countnews, channel_news
):
    if channel_news is not None and channel_news != "":
        news_count = 0  # Contatore news
        index = 0
        async for message in channel_news.history(limit=100):
            if news_count >= countnews:
                break  # Interrompi se raggiungi il numero richiesto di notizie

            processed = await process_news(
                botDiscord, interaction, message, index, channel_news
            )
            if processed:
                news_count += 1
            index += 1


async def leggi_giochi_gratis(botDiscord, interaction, channel_news):
    if channel_news != None and channel_news != "":
        try:
            async for message in channel_news.history(limit=1):
                # print(f"Message: {message.content}", flush=True)
                messageFormatted = await process_free_videogames(message.content)
                print(f"Videogioco: {messageFormatted}", flush=True)
                await text_to_speech(
                    botDiscord,
                    messageFormatted,
                    f"news_by_channel_{channel_news.id}",
                    interaction.channel.id,
                )
                return messageFormatted
        except Exception as e:
            print(f"Error: {e}", flush=True)
            # raise Exception(f"Error: {e}", flush=True)


# async def join_and_listen(ctx):
#     voice_channel = ctx.author.voice.channel
#     if voice_channel is not None:
#         vc = await voice_channel.connect()
#         await listen_audio(vc)


# # Funzione per generare la lista dei file audio disponibili
# def get_command_audio_files():
#     audio_files = {}
#     for i, file in enumerate(os.listdir(AUDIO_FOLDER)):
#         if file.endswith((".mp3", ".wav")):
#             audio_files[i + 1] = file
#     return audio_files


# async def listen_audio(vc):
#     """
#     Registra audio dal canale vocale e lo trascrive usando Whisper.
#     """
# TO DO DA FARE
#     try:
#         print("In ascolto dell'audio...")
#         # Percorso del file audio temporaneo
#         audio_file = "recorded_audio.wav"

#         # Registra l'audio dal canale vocale
#         ffmpeg_command = (
#             f"ffmpeg -y -i {vc.source.stream.url} -ar 16000 -ac 1 -f wav {audio_file}"
#         )
#         process = await asyncio.create_subprocess_shell(ffmpeg_command)
#         await process.communicate()

#         # Trascrivi il file audio con Whisper
#         print("Inizio trascrizione...")
#         transcription = model.transcribe(audio_file)
#         text = transcription["text"]
#         print(f"Trascrizione: {text}")

#         # Analizza la trascrizione per eventuali parole chiave
#         keywords = {"vongola": trigger_event}
#         for word in keywords:
#             if word in text.lower():
#                 print(f"Parola chiave rilevata: {word}")
#                 await keywords[word](vc)
#                 break

#     except Exception as e:
#         print(f"Errore durante l'ascolto: {e}")


async def trigger_event(vc, command):
    # Esegui un'azione in base al comando
    if command == "vongola off" or command == "disconnetti":
        await vc.disconnect()
        print("Disconnesso dal canale vocale.")
    elif command == "ciao":
        print("Ciao! Sono Er-Vongola, il tuo assistente vocale.")
    elif command == "riproduci" or command == "metti":
        print("Riproduco un file audio (da implementare).")
    else:
        print(f"Comando non riconosciuto: {command}")
