# Standard library imports
from collections import defaultdict
import datetime
import logging
import os
import json
import re
import time
import uuid
import asyncio

# Third party imports
import discord
import aiohttp
from bs4 import BeautifulSoup
import feedparser
import yt_dlp as youtube_dl
from gtts import gTTS

# Local imports
import frasiconteggio as frasiconteggio

# vimport whisper
import voice_manager as vm

import traceback

# import speech_recognition as sr
vc_lock = asyncio.Lock()
stop_event = asyncio.Event()  # Evento per fermare le operazioni asincrone
CONNECT_MAX_RETRIES = 5
CONNECT_BASE_DELAY = 2  # secondi

logging.basicConfig(
    level=logging.INFO,
    format="[{levelname}] {message}",
    style="{",
    datefmt="%d/%m/%Y %H:%M:%S",
)

# model = whisper.load_model("small")

# Lista di parole chiave e comandi associati
keyword_commands = {
    "vongola": "disconnect",
    "ciao bot": "greet",
    "riproduci": "play_audio",
}

CHAT_VOCALE_PRIVATO = "707198443751211140"
CHAT_VOCALE_PRIVATO2 = "707514058990944256"
CHAT_VOCALE_PRIVATO3 = "783252026766131222"
chats = ['CHAT_VOCALE_PRIVATO", "CHAT_VOCALE_PRIVATO2", "CHAT_VOCALE_PRIVATO3']
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
GUILD_ID = "679423743017091083"

# recognizer = sr.Recognizer()

VC_TIMEOUT = 2
pending_by_guild: dict[int, int] = defaultdict(int)


async def audio_player(
    audio_queue: asyncio.Queue,
    botDiscord: discord.Client,
    interaction: discord.Interaction,
):
    actual_datetime_string = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    await botDiscord.wait_until_ready()
    logging.info("[AUDIO_PLAYER] Avviato")
    while not botDiscord.is_closed():
        task = None
        vm.current_vc = None
        try:
            task = await audio_queue.get()
            if not task:
                await asyncio.sleep(1)
                continue

            channel = task.get("channel")
            file_name = task.get("audio")
            if not channel or not file_name:
                logging.error(
                    f"[{actual_datetime_string}] [AUDIO_PLAYER] task malformato, skip"
                )
                audio_queue.task_done()
                continue

            if not os.path.exists(file_name):
                logging.error(
                    f"[{actual_datetime_string}] [AUDIO_PLAYER] File non trovato: {file_name}"
                )
                audio_queue.task_done()
                continue

            # DISCONNECT PRECEDENTI: se esiste un VC attivo su questa guild -> forza disconnect con delay
            existing_vc = vm.get_current_vc()
            if existing_vc is not None and (
                (audio_queue.qsize() == 0 and audio_queue.empty())
                or not existing_vc.is_playing()
            ):
                # controlla se zombie
                ws = getattr(existing_vc, "ws", None)
                if not existing_vc.is_connected() or ws is None:
                    logging.warning(
                        f"[{actual_datetime_string}] [AUDIO_PLAYER] VC zombie rilevato prima del connect -> disconnect force"
                    )
                    await vm.disconnect_current_vc()
                    await asyncio.sleep(VC_TIMEOUT)
                elif existing_vc.channel.id != channel.id:
                    logging.info(
                        f"[{actual_datetime_string}] [AUDIO_PLAYER] VC attivo in altro canale -> disconnect forzato prima di connect"
                    )
                    await vm.disconnect_current_vc()
                    await asyncio.sleep(VC_TIMEOUT)

                # Connettiti (serializzato dentro voice_manager)
            print(f"INFO: {vm.current_vc}")
            vc = await vm.connect_to_channel(channel, botDiscord, interaction)
            if not vc or not vc.is_connected():
                logging.error(
                    f"[{actual_datetime_string}] [AUDIO_PLAYER] Connessione al canale fallita, skip task"
                )
                audio_queue.task_done()
                continue

            # Avvia riproduzione
            try:
                source = discord.FFmpegPCMAudio(file_name)
                vc.play(source)
                logging.info(
                    f"[{actual_datetime_string}] [AUDIO_PLAYER] Riproduzione iniziata: {file_name}"
                )
            except Exception as e:
                logging.error(
                    f"[{actual_datetime_string}] [AUDIO_PLAYER] Errore avvio riproduzione: {e}"
                )
                # se play fallisce, forziamo disconnect e skip
                await vm.disconnect_current_vc()
                audio_queue.task_done()
                continue

            # attendi la fine riproduzione oppure che la connessione muoia
            # 🔹 Aspetto finché la traccia non è finita
            count_messages = 0
            while vc is not None and vc.is_connected() and vc.is_playing():
                await asyncio.sleep(1)
                count_messages += 1
                if count_messages == 1:
                    logging.info(
                        f"[{actual_datetime_string}] [AUDIO_PLAYER] In riproduzione..."
                    )
            # 🔹 Quando la traccia è finita → segno come completata
            pending_by_guild[GUILD_ID] = max(0, pending_by_guild[GUILD_ID] - 1)
            audio_queue.task_done()
            # e decremento il contatore per quella guild
            # pending_by_guild[GUILD_ID] = max(0, pending_by_guild[GUILD_ID] - 1)
            if pending_by_guild[GUILD_ID] > 0:
                # 🔹 Aspetto qualche secondo per evitare race condition
                await asyncio.sleep(VC_TIMEOUT)
                continue

            # se non ci sono più task in coda per questa guild → disconnetto
            if (
                audio_queue.empty()
                and pending_by_guild[GUILD_ID] == 0
                and vc is not None
                and not vc.is_playing()
            ):
                logging.info(
                    f"[{actual_datetime_string}] [AUDIO_PLAYER] Lista vuota, mi disconnetto..."
                )
                await vm.disconnect_current_vc()
                vm.current_vc = None
                logging.info(
                    f"[{actual_datetime_string}] [AUDIO_PLAYER] Eliminazione file temporanei..."
                )
                delete_temp_file()
        except Exception as e:
            logging.error(f"[{actual_datetime_string}] [AUDIO_PLAYER] Errore: {e}")
            # In caso di errori → task_done + decremento per non bloccare la coda
            if task and task.get("channel"):
                try:
                    pending_by_guild[GUILD_ID] = max(0, pending_by_guild[GUILD_ID] - 1)
                except:
                    pass
                try:
                    await vm.disconnect_current_vc()
                    logging.error(
                        f"[{actual_datetime_string}] [AUDIO_PLAYER] Disconnesso da guild {task['channel'].guild.id} (errore)"
                    )
                except:
                    pass
            if task:
                try:
                    audio_queue.task_done()
                except:
                    pass
            await asyncio.sleep(1)

    if vc and not vc.is_connected():
        logging.warning(
            f"[{actual_datetime_string}] [WARN] Voice client disconnected. Forcing reconnect..."
        )
        await vc.disconnect(force=True)
    # Aspetto qualche secondo per evitare race condition
    await asyncio.sleep(2)


def add_to_pending_by_guild():
    pending_by_guild[GUILD_ID] = pending_by_guild.get(GUILD_ID, 0) + 1


# Converte il testo parlato in un file audio e lo mette in coda per la riproduzione
async def text_to_speech(custom_message, file_name, channel, audio_queue):
    """
    Converte il testo in un file audio mp3 e lo mette in coda per la riproduzione.
    Usa gTTS (Google Text-to-Speech).
    """
    allowed_channels = [CHAT_VOCALE_PRIVATO, CHAT_VOCALE_PRIVATO2, CHAT_VOCALE_PRIVATO3]
    if str(channel.id) not in allowed_channels:
        return

    try:
        tts = gTTS(custom_message, lang="it", tld="it", slow=True)
        tts.save(f"{file_name}.mp3")
        await audio_queue.put({"audio": f"{file_name}.mp3", "channel": channel})
        logging.info(f"Message/command received by channel: {channel}")
        add_to_pending_by_guild()

    except (
        discord.errors.ClientException,
        discord.errors.DiscordException,
        discord.errors.HTTPException,
        discord.errors.Forbidden,
        discord.errors.NotFound,
        discord.errors.DiscordServerError,
        ConnectionError,
        TimeoutError,
        asyncio.TimeoutError,
        asyncio.CancelledError,
        Exception,
    ) as e:
        logging.error(f"Error connecting to voice channel: {e}")
        raise e


async def make_audio(botDiscord, member, channelKey, audio_queue):
    """
    Genera un messaggio di benvenuto personalizzato quando un utente entra in un canale vocale specifico.
    Usa un file JSON da cui preleva e genera frasi casuali.
    """
    # Apro la comunicazione con il file JSON per ottenermi la lista delle frasi
    try:
        with open("json/frasieffetto.json", "r", encoding="utf-8") as file:
            try:
                data = json.load(file)
                frasi = frasiconteggio.FrasiConteggio(data)
                custom_message = ""
                # Ottengo il canale tramite il channelKey
                channel = botDiscord.get_channel(int(channelKey))
                # Controllo se l'utente è entrato in quel determinato canale
                if str(channel.id) in [
                    CHAT_VOCALE_PRIVATO,
                    CHAT_VOCALE_PRIVATO2,
                    CHAT_VOCALE_PRIVATO3,
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
                        custom_message,
                        f"welcome_message_{member.name}_{str(uuid.uuid4())}",
                        channel,
                        audio_queue,
                    )
            except json.JSONDecodeError as e:
                logging.error(f"Error decoding JSON: {e}")
                return
    except FileNotFoundError as e:
        logging.error(f"File not found: {e}")
        return
    except IOError as e:
        logging.error(f"IOError while reading file: {e}")
        return


async def play_youtube_video(
    botDiscord, interaction: discord.Interaction, url: str, volume: int
):
    """
    Scarica l'audio da un link YouTube e lo riproduce nel canale vocale.
    Usa i 2 plugins yt-dlp per il download e FFmpeg per la riproduzione.
    """
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
    vc_client = await vm.connect_to_channel(channel, botDiscord, interaction)

    def download_complete(d):
        if stop_event.is_set():  # Verifica se il comando di stop è stato dato
            return  # Esce immediatamente se lo stop è attivo
        if d["status"] == "finished":
            logging.info(f"Download completato: {d['filename']}")
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
            logging.error(f"Errore durante la riproduzione: {error}")
        # Elimina il file dopo la riproduzione
        if os.path.exists(file):
            os.remove(file)
            # logging.info(f"Eliminato: {file}")

    # Riproduci l'audio
    if not file or not os.path.exists(file):
        await interaction.response.send_message(
            "Impossibile trovare l'audio.", ephemeral=True
        )
        return

    volume_filter = "volume=0" if volume == 0 else f"volume={volume / 100.0}"
    ffmpeg_options = f"-af '{volume_filter}'"
    try:
        vc_client.play(
            discord.FFmpegPCMAudio(file, options=ffmpeg_options), after=after_playing
        )
        if not interaction.is_expired():
            await interaction.followup.send(
                f"Inizio a riprodurre l'audio {title} con link {url} con volume al {volume}%"
            )
    except discord.ClientException as e:
        logging.error("Errore di connessione al canale vocale.", exc_info=e)
        await interaction.response.send_message(
            "Errore di connessione al canale vocale.", ephemeral=True
        )


# async def stop(interaction: discord.Interaction):
#     stop_event.set()  # Imposta l'evento di stop per fermare tutte le operazioni asincrone

#     logging.info(f"current_vc is none: {vc.current_vc is None}")
#     if vc.current_vc and vc.current_vc.is_playing():
#         vc.current_vc.stop()
#         await vc.current_vc.disconnect()
#         vc.current_vc = None
#         await interaction.response.send_message(
#             "Riproduzione interrotta e disconnesso dal canale vocale."
#         )
#     else:
#         await interaction.response.send_message("Nessuna riproduzione in corso.")
#     if vc.current_vc and vc.current_vc.is_playing():
#         interaction.response.send_message("Riproduzione in corso...")
#     # Attendere fino alla fine della riproduzione
#     while vc.current_vc and vc.current_vc.is_playing():
#         await asyncio.sleep(10)
#     # Questo metodo connette il bot al canale vocale se il canale non è vuoto e riproduce il file audio,
#     # rimane in attesa 3 secondi per permettere di aggiungersi altri file in coda da riprodurre successivamente


def delete_temp_file():
    """
    Elimina tutti i file temporanei creati da text_to_speech.
    Questi file vengono creati nella cartella corrente e hanno estensione .mp3.
    """
    folder = "."
    for filename in os.listdir(folder):
        if filename.endswith(".mp3"):
            file_path = os.path.join(folder, filename)
            try:
                os.remove(file_path)
                # logging.info(f"Eliminato: {file_path}")
            except Exception as e:
                logging.error(f"Errore eliminando {file_path}: {e}")


async def enumerate_messages(aiterator):
    """
    Enumera gli elementi di un iteratore asincrono, restituendo un tuple contenente l'indice dell'elemento e l'elemento stesso.

    Parameters
    ----------
    iterator : typing.AsyncIterator
        Iteratore asincrono da enumerare

    Yields
    -------
    typing.Tuple[int, typing.Any]
        Tuple contenente l'indice dell'elemento e l'elemento stesso
    """
    index = 0
    async for item in aiterator:
        yield index, item
        index += 1


def load_read_news():
    """
    Carica le notizie da leggere precedentemente salvate in un file json.

    Se il file non esiste o è vuoto, restituisce un array vuoto.

    Returns
    -------
    list
        Lista di notizie da leggere precedentemente salvate in un file json
    """
    try:
        if os.path.exists(READ_NEWS_FILE):
            with open(READ_NEWS_FILE, "r", encoding="utf-8") as file:
                return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        logging.error(f"Error reading file: {READ_NEWS_FILE}")
        return []  # Se il file non esiste o è vuoto, restituisci un array vuoto


def save_read_news(news_url):
    data = load_read_news()
    if news_url not in data:
        data.append(news_url)
        with open(READ_NEWS_FILE, "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=4)


async def save_news_and_speech(
    interaction: discord.Interaction, message, index, type_news, audio_queue
):
    """
    Salva la notizia e la relativa trascrizione audio associata.

    Parameters
    ----------
    interaction : discord.Interaction
        Interazione che ha generato la notizia
    message : str
        Notizia da salvare
    index : int
        Indice della notizia
    type_news : str
        Tipo di notizia
    audio_queue : asyncio.Queue
        Coda di attesa per le notizie da convertire in audio

    Returns
    -------
    None
    """
    news = {"userId": interaction.user.id, "news": message}
    # data = load_read_news()
    # data.append(news)
    save_read_news(news)
    await text_to_speech(
        message,
        f"news_by_channel_{type_news}_{index}",
        interaction.channel,
        audio_queue,
    )


# async def process_news(
#     botDiscord, interaction: discord.Interaction, message, index, type_news
# ):
#     data = load_read_news()

#     # print(len(data))
#     # if data is None or len(data) == 0:
#     #     await save_news_and_speech(botDiscord, interaction, message, index, type_news)
#     #     return True

#     user_founded = any(entry["userId"] == interaction.user.id for entry in data)
#     news_founded = any(entry["news"] == message for entry in data)

#     logging.info(f"Notizia:\n {news_founded}")
#     if data is None or len(data) == 0 or not (user_founded) or not (news_founded):
#         await save_news_and_speech(botDiscord, interaction, message, index, type_news)
#         return True
#     return False


async def process_free_videogames(message):
    """
    Processa la notizia di un gioco gratuito e restituisce la frase per annunciare la notizia.
    La frase viene generata in base ai pattern riconosciuti all'interno del testo della notizia.
    Se la notizia contiene la frase "free from" verrà restituita la frase "Il gioco <nome> e' disponibile su <piattaforma>".
    Se la notizia contiene la frase "free in the Steam store" verrà restituita la frase "<nome> e' disponibile su Steam".
    Se la notizia contiene la frase "free from GOG.com" verrà restituita la frase "<nome> e' disponibile sull app di GOG.com".
    Se la notizia contiene la frase "free from Epic Games store" verrà restituita la frase "<nome> e' disponibile sullo store di Epic".
    Parameters
    ----------
    message : str
        Testo della notizia da processare
    Returns
    -------
    str
        Frase per annunciare la notizia
    """
    name_videogame = ""
    pattern_videogame = r"^(.*?)\sfree from"
    pattern_gog = r"^(.*?)\sfree from GOG.com"
    pattern_steam = r"^(.*?)\sfree in the Steam store"
    pattern_epic = r"^(.*?)\sfrom Epic Games store"
    match_name_videogame = re.search(pattern_videogame, message)
    match_gog = re.search(pattern_gog, message)
    match_steam = re.search(pattern_steam, message)
    match_epic = re.search(pattern_epic, message)
    if match_name_videogame:
        name_videogame = match_name_videogame.group(1)
    if match_steam:
        is_from_steam = match_steam.group(1)
        return f"{name_videogame} e' disponibile su Steam"
    if match_gog:
        is_from_gog = match_gog.group(1)
        return f"{name_videogame} e' disponibile sull app di GOG.com"
    if match_epic:
        is_from_epic = match_epic.group(1)
        return f"{name_videogame} e' disponibile sullo store di Epic"


async def take_news(
    interaction: discord.Interaction, countnews, type_news, audio_queue
):
    """
    Prende le ultime notizie da Google News e le mette in coda per la conversione in audio.

    Parameters
    ----------
    interaction : discord.Interaction
        Interazione che ha generato la richiesta di notizie
    countnews : int
        Numero di notizie da prendere
    type_news : str
        Tipo di notizie da prendere (es. "tecnologia", "sport", "politica", ecc.)
    audio_queue : asyncio.Queue
        Coda di attesa per le notizie da convertire in audio
    """
    url = f"https://news.google.com/rss/search?q={type_news}&hl=it&gl=IT&ceid=IT:it"
    feed = feedparser.parse(url)
    feed_notizie = feed.entries
    notizie = []
    data = load_read_news() or []
    if not feed_notizie:
        logging.error(f"Errore nel parsing del feed RSS: {feed.bozo_exception}")
        return
    # logging.info(f"Notizie trovate: {feed_notizie}")
    for index, entry in enumerate(feed_notizie):
        titolo = entry.title
        link = entry.link
        descrizione_html = entry.summary
        link = entry.link
        soup = BeautifulSoup(descrizione_html, "html.parser")
        # prendi solo il testo dentro il primo <a>
        testo_link = soup.find("a").get_text() if soup.find("a") else ""
        fonte = titolo.split("-")[-1]
        message = f"{testo_link}. Fonte della notizia: {fonte}"
        # logging.info(f"Notizia: {testo_link} - Fonte: {fonte}")
        news_founded = next(
            entry["userId"] == interaction.user.id and entry["news"] == message
            for entry in data
        )
        if not news_founded:
            notizie.append(message)

    for index in range(len(notizie)):
        if index >= countnews:
            break
        message = notizie[index]
        logging.info(f"Notizia da leggere: {message}")
        await save_news_and_speech(interaction, message, index, type_news, audio_queue)


async def leggi_giochi_gratis(interaction, channel_news, audio_queue):
    """
    Prende l'ultimo messaggio dal canale vocale dove ti trovi e ti legge il nome del gioco gratuito del momento su Epic Games Store e/o Steam.\n
    Parameters
    ----------
    interaction : discord.Interaction
        Interazione che ha generato la richiesta di notizie
    channel_news : discord.TextChannel
        Canale vocale dove dove ti trovi
    audio_queue : asyncio.Queue
        Coda di attesa per le notizie da convertire in audio
    Returns
    -------
    str
        Nome del gioco gratuito del momento su Epic Games Store e/o Steam
    """
    if channel_news != None and channel_news != "":
        try:
            async for message in channel_news.history(limit=1):
                # print(f"Message: {message.content}", flush=True)
                messageFormatted = await process_free_videogames(message.content)
                logging.info(f"Videogioco: {messageFormatted}")
                await text_to_speech(
                    messageFormatted,
                    f"news_by_channel_{channel_news.id}",
                    interaction.channel,
                    audio_queue,
                )
                return messageFormatted
        except (
            aiohttp.ClientError,
            ValueError,
            KeyError,
            discord.errors.HTTPException,
            discord.errors.Forbidden,
            discord.errors.NotFound,
            discord.errors.DiscordServerError,
            AttributeError,
            TypeError,
        ) as e:
            logging.error(
                f"Error processing free games: {str(e)}\n{traceback.format_exc()}"
            )
            return f"Error processing free games: {str(e)}\n{traceback.format_exc()}"


async def leggi_meteo(interaction, nome_citta):
    await interaction.response.defer()
    weather_results = await get_weather_data(nome_citta)

    if weather_results:
        response_message = f"🌤️ Meteo per {nome_citta.title()}:\n" + "\n".join(
            weather_results
        )
    else:
        response_message = (
            f"❌ Non sono riuscito a trovare le previsioni meteo per {nome_citta}"
        )
    if not interaction.is_expired():
        await interaction.followup.send(response_message)


async def get_weather_data(nome_citta):
    weather_data = []
    city_encoded = nome_citta.lower().replace(" ", "-")

    urls = {
        "ilmeteo.it": f"https://www.ilmeteo.it/meteo/{city_encoded}",
        "3bmeteo.com": f"https://www.3bmeteo.com/meteo/{city_encoded}",
        "meteo.it": f"https://www.meteo.it/{city_encoded}",
    }

    async with aiohttp.ClientSession() as session:
        for source, url in urls.items():
            html = await fetch_url(session, url)
            if html:
                soup = BeautifulSoup(html, "html.parser")
                try:
                    if source == "ilmeteo.it":
                        temp = soup.find("div", class_="temp")
                        if temp:
                            weather_data.append(f"**ilmeteo.it**: {temp.text.strip()}")

                    elif source == "3bmeteo.com":
                        temp = soup.find("div", class_="today-temperature")
                        if temp:
                            weather_data.append(f"**3bmeteo.com**: {temp.text.strip()}")

                    elif source == "meteo.it":
                        temp = soup.find("div", class_="temperature")
                        if temp:
                            weather_data.append(f"**meteo.it**: {temp.text.strip()}")
                except (AttributeError, TypeError, ValueError) as e:
                    logging.error(f"Error parsing weather data: {e}")
                    continue

    return weather_data


async def fetch_url(session, url):
    try:
        async with session.get(
            url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10
        ) as response:
            if response.status == 200:
                return await response.text()
            return None
    except aiohttp.ClientError as e:
        logging.error(f"Error fetching URL (client error): {e}")
        return None
    except asyncio.TimeoutError as e:
        logging.error(f"Error fetching URL (timeout): {e}")
        return None
    except ValueError as e:
        logging.error(f"Error fetching URL (value error): {e}")
        return None


# async def join_and_listen(ctx):
#     voice_channel = ctx.author.voice.channel
#     if voice_channel is not None:
#         vc = await voice_channel.connect()
#         await listen_audio(vc)


# Funzione per generare la lista dei file audio disponibili
def get_command_audio_files():
    """
    Ritorna una lista dei file audio disponibili per i comandi vocali.

    I file audio sono nella cartella specificata da AUDIO_FOLDER.

    La lista dei file audio è un dizionario dove la chiave rappresenta l'ID del file audio
    e il valore rappresenta il nome del file audio.

    Esempio di output:
    {
        1: "audio1.mp3",
        2: "audio2.wav"
    }

    Returns
    -------
    dict
        Dizionario contenente la lista dei file audio disponibili per i comandi vocali
    """
    audio_files = {}
    for i, file in enumerate(os.listdir(AUDIO_FOLDER)):
        if file.endswith((".mp3", ".wav")):
            audio_files[i + 1] = file
    return dict(
        sorted(audio_files.items())
    )  # Ordina la lista dei file audio per ID audio_files


# async def listen_audio(vc):
#     """
#     Registra audio dal canale vocale e lo trascrive usando Whisper.
#     """
#     try:
#         print("In ascolto dell'audio...", flush=True)
#         is_listening_for_command = False

#         while True:
#             # Percorso del file audio temporaneo
#             audio_file = "recorded_audio.wav"

#             # Registra l'audio dal canale vocale
#             ffmpeg_command = (
#                 f"ffmpeg -y -i {vc.source.stream.url} -ar 16000 -ac 1 -f wav {audio_file}"
#             )
#             process = await asyncio.create_subprocess_shell(ffmpeg_command)
#             await process.communicate()

#             # Trascrivi il file audio con Whisper
#             print("Inizio trascrizione...", flush=True)
#             transcription = model.transcribe(audio_file)
#             text = transcription['text'].lower()
#             print(f"Trascrizione: {text}", flush=True)

#             # Verifica il pre-comando
#             if "ei vongola" in text:
#                 is_listening_for_command = True
#                 await text_to_speech(vc.guild.voice_client, "Sì signore", "response", vc.channel.id)
#                 continue

#             # Processa i comandi solo se è stato attivato il pre-comando
#             if is_listening_for_command:
#                 if "bestemmia" in text:
#                     # Implementare la logica per generare una bestemmia casuale
#                     await text_to_speech(vc.guild.voice_client, "Non posso bestemmiare", "response", vc.channel.id)
#                     is_listening_for_command = False

#                 elif "dammi il meteo di" or "che tempo fa a" in text:
#                     # Estrai il nome della città
#                     city_match = re.search(
#                         r"(dammi il meteo di|che tempo fa a) (.+)", text)
#                     if city_match:
#                         city = city_match.group(1).strip()
#                         # Nota: modificare per gestire l'interaction
#                         await leggi_meteo(None, city)
#                     is_listening_for_command = False

#                 elif "leggi le notizie dei giochi" in text:
#                     # Nota: modificare per gestire l'interaction e il channel
#                     await leggi_giochi_gratis(vc.guild.voice_client, None, None)
#                     is_listening_for_command = False

#                 elif "leggi le notizie" in text:
#                     # Nota: modificare per gestire l'interaction e il channel
#                     await leggi_notizie(vc.guild.voice_client, None, 3, None)
#                     is_listening_for_command = False

#                 elif "riproduci" in text:
#                     # Estrai il titolo della canzone
#                     song_match = re.search(r"riproduci (.+) su youtube", text)
#                     if song_match:
#                         song_title = song_match.group(1).strip()
#                         # Implementare la ricerca su YouTube e la riproduzione
#                         # Nota: modificare per gestire l'interaction
#                         await play_youtube_video(None, f"ytsearch:{song_title}", 50)
#                     is_listening_for_command = False

#                 else:
#                     print("Comando non riconosciuto", flush=True)
#                     is_listening_for_command = False

#             # Pulisci il file audio temporaneo
#             if os.path.exists(audio_file):
#                 os.remove(audio_file)

#     except (discord.errors.ClientException,
#             discord.errors.DiscordException,
#             asyncio.CancelledError,
#             FileNotFoundError,
#             PermissionError,
#             RuntimeError) as e:
#         print(f"Errore durante l'ascolto: {e}", flush=True)
#         if os.path.exists(audio_file):
#             os.remove(audio_file)


async def trigger_event(vc, command):
    # Esegui un'azione in base al comando
    if command == "vongola off" or command == "disconnetti":
        await vc.disconnect()
        logging.info("Disconnesso dal canale vocale.")
    elif command == "ciao":
        logging.info("Ciao! Sono Er-Vongola, il tuo assistente vocale.")
    elif command == "riproduci" or command == "metti":
        logging.info("Riproduco un file audio.")
    else:
        logging.info(f"Comando non riconosciuto {command}")
