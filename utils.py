# Standard library imports
import logging
import os
import json
import re
import asyncio
import random

# Third party imports
import discord
import aiohttp
from bs4 import BeautifulSoup
import feedparser
import yt_dlp
import tts_manager as tts

# Local imports
import frasiconteggio as frasiconteggio
import generatoreblasfemie
import constants

import voice_manager as vm
import queue_manager as qm

import traceback

# import speech_recognition as sr
vc_lock = asyncio.Lock()
stop_event = asyncio.Event()  # Evento per fermare le operazioni asincrone
CONNECT_MAX_RETRIES = 5
CONNECT_BASE_DELAY = 2  # secondi

_FRASI_ADDIO_FILE = "json/frasiaddio.json"
_FRASE_ADDIO_FALLBACK = "Aòòh! Io ho finito, ME NE VADO, BELLA REGÀ!!"


def _get_frase_addio() -> str:
    """Restituisce una frase di saluto finale casuale letta da frasiaddio.json.

    Il formato reale di ogni entry in "frasi" e' un oggetto
    {"text": "...", "count": 0} (non una stringa semplice), quindi il testo
    va estratto dal campo "text". Manteniamo comunque il supporto alle
    stringhe dirette per retrocompatibilita' con formati piu' vecchi del file.
    """
    try:
        with open(_FRASI_ADDIO_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        frasi = []
        for entry in data.get("frasi", []):
            if isinstance(entry, str):
                testo = entry
            elif isinstance(entry, dict):
                testo = entry.get("text")
            else:
                testo = None
            if isinstance(testo, str) and testo.strip():
                frasi.append(testo)

        if frasi:
            return random.choice(frasi)
        logging.warning(
            f"[ADDIO] {_FRASI_ADDIO_FILE} non contiene frasi valide (campo text mancante o vuoto)."
        )
    except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
        logging.warning(f"[ADDIO] Impossibile caricare {_FRASI_ADDIO_FILE}: {e}")
    return _FRASE_ADDIO_FALLBACK


# Debounce per make_audio: evita audio duplicati se un utente entra/esce velocemente
_make_audio_pending: dict = {}  # member_id -> asyncio.Task


def _drain_stale_tasks(channel: discord.VoiceChannel):
    """
    Svuota dalla coda i task relativi a un canale che potrebbe essere cambiato o vuoto.
    Chiamata dopo un errore vocale per evitare retry su sessioni ormai inutili.
    """
    drained = 0
    temp = []
    while not qm.audio_queue.empty():
        try:
            item = qm.audio_queue.get_nowait()
            qm.audio_queue.task_done()
            if item.get("channel") != channel:
                temp.append(item)  # mantieni i task per altri canali
            else:
                drained += 1
        except Exception:
            break
    for item in temp:
        qm.audio_queue.put_nowait(item)
    if drained:
        logging.info(
            f"[AUDIO_PLAYER] Rimossi {drained} task stale per canale {channel.name}"
        )


logging.basicConfig(
    level=logging.INFO,
    format="[{levelname}] {message}",
    style="{",
    datefmt="%d/%m/%Y %H:%M:%S",
)

# Lista di parole chiave e comandi associati
keyword_commands = {
    "vongola": "disconnect",
    "ciao bot": "greet",
    "riproduci": "play_audio",
}

chats = [
    constants.chats_database["chat_vocale_privato"],
    constants.chats_database["chat_vocale_privato2"],
    constants.chats_database["chat_vocale_privato3"],
]
id_users = {
    "alexssio": "190745296500686857",
    "BLAcK_Knight": "366952021045280779",
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


async def audio_player(botDiscord, guild):
    while True:
        if stop_event.is_set():
            break

        try:
            # Restiamo in attesa di un task per 15 secondi (Grace Period)
            task = await asyncio.wait_for(qm.audio_queue.get(), timeout=15.0)
        except asyncio.TimeoutError:
            # Se la coda è vuota per 15s, salutiamo e disconnettiamo
            vc = vm.current_vc
            if vc and vc.is_connected() and not vc.is_playing():
                logging.info(
                    "[AUDIO_PLAYER] Coda vuota da 15s. Riproduco saluto finale e disconnetto."
                )
                try:
                    file_saluto = "audio_saluto_finale.mp3"
                    frase_addio = _get_frase_addio()
                    success = await tts.text_to_speech_async(frase_addio, file_saluto)

                    if not success:
                        logging.error(
                            "[AUDIO_PLAYER] Errore nella generazione del saluto finale"
                        )
                        continue

                    vc.play(discord.FFmpegPCMAudio(file_saluto))
                    while vc.is_playing():
                        await asyncio.sleep(1)

                except Exception as e:
                    # exc_info=True: senza il traceback completo non si capisce MAI
                    # da quale chiamata (TTS, FFmpeg, encoder Opus, voice_recv/DAVE)
                    # arriva davvero l'errore. Prima veniva loggato solo str(e).
                    logging.error(
                        f"[AUDIO_PLAYER] Errore nel saluto finale: {e}", exc_info=True
                    )
                finally:
                    # Disconnetti e pulisci SEMPRE, anche se il saluto fallisce.
                    # Prima, in caso di eccezione, il bot restava agganciato al
                    # canale vocale e ritentava il saluto ogni 15s all'infinito
                    # (l'unico ramo che disconnetteva era quello "success").
                    await vm.disconnect(guild)
                    delete_temp_file()
            continue

        try:
            channel = task["channel"]
            file_name = task["file"]

            vc = await vm.connect_to_channel(channel)

            # Verifichiamo se siamo connessi prima di riprodurre
            if vc and vc.is_connected():
                vc.play(discord.FFmpegPCMAudio(file_name))

                while vc.is_playing():
                    await asyncio.sleep(2)

                delete_temp_file()
            else:
                logging.error(
                    "[AUDIO_PLAYER] Impossibile stabilire una connessione valida, rimetto in coda (backoff 15s)..."
                )
                await vm.disconnect()
                await asyncio.sleep(10)
                await qm.audio_queue.put(task)

        except discord.errors.ConnectionClosed as e:
            logging.error(
                f"[AUDIO_PLAYER] WebSocket chiuso (codice {e.code}). Reset e backoff 20s..."
            )
            await vm.disconnect(guild)
            await asyncio.sleep(20)
            _drain_stale_tasks(channel)

        except asyncio.TimeoutError:
            logging.error(
                "[AUDIO_PLAYER] Timeout handshake vocale. Reset e backoff 15s..."
            )
            await vm.disconnect(guild)
            await asyncio.sleep(15)
            _drain_stale_tasks(channel)

        except Exception as e:
            logging.error(f"[AUDIO_PLAYER] Errore critico nel player: {e}")
            await vm.disconnect(guild)
            await asyncio.sleep(10)
            _drain_stale_tasks(channel)
        finally:
            qm.audio_queue.task_done()
    # logging.info("[AUDIO_PLAYER] Audio player started")
    # while True:
    #     try:
    #         task = await audio_queue.get()
    #         channel = task["channel"]
    #         file_name = task["file"]
    #         if not os.path.exists(file_name):
    #             logging.warning(f"[AUDIO_PLAYER] File non trovato: {file_name}")
    #             audio_queue.task_done()
    #             continue

    #         vc = discord.utils.get(
    #             botDiscord.voice_clients, guild=guild, channel=channel
    #         )
    #         if not vc or not vc.is_connected():
    #             try:
    #                 vc = await channel.connect()
    #             except discord.ClientException:
    #                 if vc and vc.is_connected():
    #                     try:
    #                         await vc.disconnect(force=True)
    #                         vc = None
    #                     except Exception:
    #                         pass
    #                 await asyncio.sleep(2)
    #         else:
    #             logging.warning("VC non connesso, metto in pausa la riproduzione.")
    #             await asyncio.sleep(3)
    #         if vc and vc.is_connected():
    #             vc.play(discord.FFmpegPCMAudio(file_name))
    #         logging.info(f"Riproduzione audio: {file_name}")
    #         # Riproduzione audio
    #         while vc and vc.is_playing():
    #             await asyncio.sleep(1)

    #         if audio_queue.empty():
    #             audio_queue.task_done()
    #             # delete_temp_file()
    #             if vc:
    #                 await vc.disconnect(force=True)
    #             logging.warning(f"[AUDIO_PLAYER] Disconnesso.")
    #     except discord.errors.ConnectionClosed as e:
    #         logging.error(f"Connessione WebSocket chiusa: {e.code}")
    #         if e.code == 4006:
    #             logging.warning("Sessione invalidata, tento la riconnessione...")
    #             try:
    #                 await botDiscord.close()
    #             except:
    #                 pass
    #             await asyncio.sleep(5)
    #     except Exception as e:
    #         logging.error(f"[AUDIO_PLAYER] Errore: {e}")
    #         await asyncio.sleep(3)


async def text_to_speech(custom_message, another_text_message, channel):
    allowed_channels = [
        constants.chats_database["chat_vocale_privato"],
        constants.chats_database["chat_vocale_privato2"],
        constants.chats_database["chat_vocale_privato3"],
        constants.chats_database["chat_testing"],
    ]
    if str(channel.id) not in allowed_channels:
        return

    try:
        filename = f"audio_{another_text_message}.mp3"
        success = await tts.text_to_speech_async(custom_message, filename)

        if not success:
            logging.error(f"[TTS] Errore nella generazione dell'audio: {filename}")
            return
        logging.info(f"Message/command received by channel: {channel}")
        await qm.audio_queue.put(
            {"channel": channel, "file": f"audio_{another_text_message}.mp3"}
        )
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


async def make_audio(botDiscord, member, channelKey):
    # FIX DEBOUNCE: se c'è già un task pendente per questo utente, cancellalo.
    # Evita che entrate/uscite rapide accodino più audio per la stessa persona.
    existing = _make_audio_pending.get(member.id)
    if existing and not existing.done():
        existing.cancel()
        logging.info(
            f"[MAKE_AUDIO] Cancellato task pendente per {member.name} (debounce)"
        )

    async def _run():
        # Piccola attesa per assorbire eventi in rapida successione (es. cambio canale)
        await asyncio.sleep(1.5)
        _make_audio_pending.pop(member.id, None)
        await _make_audio_inner(botDiscord, member, channelKey)

    task = asyncio.create_task(_run())
    _make_audio_pending[member.id] = task


async def _make_audio_inner(botDiscord, member, channelKey):
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
                    constants.chats_database["chat_vocale_privato"],
                    constants.chats_database["chat_vocale_privato2"],
                    constants.chats_database["chat_vocale_privato3"],
                    constants.chats_database["chat_testing"],
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
                    elif str(member.id) == id_users["BLAcK_Knight"]:
                        custom_message = f"BLAcK Knight {frasedeffetto}"
                    await text_to_speech(
                        custom_message,
                        f"benvenuto_{member.name}",
                        channel,
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
    # Connetti il bot al canale vocale tramite il manager unificato
    await vm.connect_to_channel(channel)

    def download_complete(d):
        if stop_event.is_set():  # Verifica se il comando di stop è stato dato
            return  # Esce immediatamente se lo stop è attivo
        if d["status"] == "finished":
            logging.info(f"Download completato: {d['filename']}")
            # Nota: Non possiamo usare interaction.response qui perché è già stata differita o usata.
            # Inoltre, download_complete corre in un thread separato, quindi usiamo run_coroutine_threadsafe
            # ma l'invio di messaggi da qui potrebbe non essere ottimale.

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
    with yt_dlp.YoutubeDL(ydl_opts_audio) as ydl:
        # Uso run_in_executor per non bloccare il loop asincrono durante il download
        info = await loop.run_in_executor(
            None, lambda: ydl.extract_info(url, download=True)
        )
        title = info.get("title", "Audio")
        file = f"audio.{ydl_opts_audio['postprocessors'][0]['preferredcodec']}"

    def after_playing(error):
        if error:
            logging.error(f"Errore durante la riproduzione: {error}")
        else:
            vm.current_vc = None
        # Elimina il file dopo la riproduzione
        if os.path.exists(file):
            try:
                os.remove(file)
                logging.info(f"Eliminato: {file}")
            except Exception as e:
                logging.error(f"Errore eliminando il file temporaneo: {e}")

    # Riproduci l'audio
    if not os.path.exists(file):
        await interaction.followup.send(
            "Impossibile trovare il file audio scaricato.", ephemeral=True
        )
        return

    volume_filter = "volume=0" if volume == 0 else f"volume={volume / 100.0}"
    ffmpeg_options = f"-af '{volume_filter}'"
    try:
        vm.current_vc.play(
            discord.FFmpegPCMAudio(file, options=ffmpeg_options), after=after_playing
        )
        if not interaction.is_expired():
            await interaction.followup.send(
                f"Inizio a riprodurre l'audio **{title}** con volume al {volume}%"
            )
    except discord.ClientException as e:
        logging.error("Errore di connessione al canale vocale.", exc_info=e)
        await interaction.followup.send(
            "Errore durante l'avvio della riproduzione vocale.", ephemeral=True
        )
    except Exception as e:
        logging.error(f"Errore generico in play_youtube_video: {e}")
        await interaction.followup.send(
            f"Si è verificato un errore: {e}", ephemeral=True
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
    folder = "."
    for filename in os.listdir(folder):
        if filename.endswith(".mp3"):
            file_path = os.path.join(folder, filename)
            try:
                os.remove(file_path)
                logging.debug(f"Eliminato: {file_path}")
            except Exception as e:
                logging.error(f"Errore eliminando {file_path}: {e}")


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
        logging.error(f"Error reading file: {READ_NEWS_FILE}")
        return []  # Se il file non esiste o è vuoto, restituisci un array vuoto


def save_read_news(news_url):
    data = load_read_news()
    if news_url not in data:
        data.append(news_url)
        with open(READ_NEWS_FILE, "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=4)


async def save_news_and_speech(
    interaction: discord.Interaction, message, index, type_news
):
    news = {"userId": interaction.user.id, "news": message}
    # data = load_read_news()
    # data.append(news)
    save_read_news(news)
    await text_to_speech(
        message,
        f"news_by_channel_{type_news}_{index}",
        interaction.channel,
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


async def prendi_notizia(
    botDiscord, interaction: discord.Interaction, countnews, type_news
):
    index = 0
    url = f"https://news.google.com/rss/search?q={type_news}&hl=it&gl=IT&ceid=IT:it"
    feed = feedparser.parse(url)
    notizie = feed.entries
    for index, entry in enumerate(notizie):
        if index == countnews:
            break
        titolo = entry.title
        link = entry.link
        descrizione_html = entry.summary

        soup = BeautifulSoup(descrizione_html, "html.parser")
        # prendi solo il testo dentro il primo <a>
        testo_link = soup.find("a").get_text() if soup.find("a") else ""
        fonte = titolo.split("-")[-1]
        message = f"{testo_link}. Fonte della notizia: {fonte}"
        logging.info(f"Notizia: {testo_link} - Fonte: {fonte}")
        data = load_read_news() or []

        news_founded = any(entry["news"] == message for entry in data)

        logging.info(f"Notizia:\n {news_founded}")
        already_read = any(
            entry["userId"] == interaction.user.id and entry["news"] == message
            for entry in data
        )
        if not already_read:
            await save_news_and_speech(interaction, message, index, type_news)


async def prendi_notizia_testo(type_news, countnews=1):
    """Cerca notizie e le restituisce come testo invece di riprodurle."""
    url = f"https://news.google.com/rss/search?q={type_news}&hl=it&gl=IT&ceid=IT:it"
    feed = feedparser.parse(url)
    notizie = feed.entries
    results = []
    for index, entry in enumerate(notizie):
        if index == countnews:
            break
        titolo = entry.title
        soup = BeautifulSoup(entry.summary, "html.parser")
        testo_link = soup.find("a").get_text() if soup.find("a") else ""
        fonte = titolo.split("-")[-1]
        results.append(f"- {testo_link} (Fonte: {fonte})")

    return "\n".join(results)


async def leggi_giochi_gratis(interaction, channel_news):
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


# Codici WMO → descrizione leggibile + emoji
# Fonte: https://open-meteo.com/en/docs (Weather interpretation codes)
_WMO_CODES: dict[int, tuple[str, str]] = {
    0: ("Cielo sereno", "☀️"),
    1: ("Prevalentemente sereno", "🌤️"),
    2: ("Parzialmente nuvoloso", "⛅"),
    3: ("Nuvoloso", "☁️"),
    45: ("Nebbia", "🌫️"),
    48: ("Nebbia con brina", "🌫️"),
    51: ("Pioggerella leggera", "🌦️"),
    53: ("Pioggerella moderata", "🌦️"),
    55: ("Pioggerella intensa", "🌧️"),
    61: ("Pioggia leggera", "🌧️"),
    63: ("Pioggia moderata", "🌧️"),
    65: ("Pioggia intensa", "🌧️"),
    71: ("Neve leggera", "❄️"),
    73: ("Neve moderata", "❄️"),
    75: ("Neve intensa", "❄️"),
    80: ("Acquazzone leggero", "🌦️"),
    81: ("Acquazzone moderato", "🌧️"),
    82: ("Acquazzone violento", "⛈️"),
    95: ("Temporale", "⛈️"),
    96: ("Temporale con grandine", "⛈️"),
    99: ("Temporale forte con grandine", "⛈️"),
}


async def leggi_meteo(interaction, nome_citta: str):
    """
    Recupera e mostra le previsioni meteo tramite Open-Meteo (gratuito, no API key).
    Pipeline: geocoding Open-Meteo → coordinate → dati meteo → risposta formattata.
    """
    await interaction.response.defer()

    try:
        dati = await get_weather_data(nome_citta)
    except Exception as e:
        logging.error(f"[METEO] Errore imprevisto per '{nome_citta}': {e}")
        dati = None

    if not dati:
        if not interaction.is_expired():
            await interaction.followup.send(
                f"❌ Non ho trovato dati meteo per **{nome_citta}**. "
                f"Controlla il nome della città e riprova."
            )
        return

    wmo_code = dati.get("weathercode", -1)
    desc, emoji = _WMO_CODES.get(wmo_code, ("Condizioni sconosciute", "🌡️"))
    temp_now = dati.get("temperature_2m", "N/D")
    temp_max = dati.get("temperature_2m_max", "N/D")
    temp_min = dati.get("temperature_2m_min", "N/D")
    wind = dati.get("windspeed_10m", "N/D")
    humidity = dati.get("relativehumidity_2m", "N/D")
    city_label = dati.get("city_label", nome_citta.title())

    lines = [
        f"## {emoji} Meteo per **{city_label}**",
        f"**Condizioni:** {desc}",
        f"**Temperatura attuale:** {temp_now}°C",
        f"**Min / Max oggi:** {temp_min}°C / {temp_max}°C",
        f"**Vento:** {wind} km/h",
        f"**Umidità:** {humidity}%",
        f"-# Dati: Open-Meteo.com · aggiornati in tempo reale",
    ]

    if not interaction.is_expired():
        await interaction.followup.send("\n".join(lines))


async def get_weather_data(nome_citta: str) -> dict | None:
    """
    Recupera i dati meteo per la città tramite Open-Meteo (gratuito, no API key).

    Step 1 — Geocoding: Open-Meteo Geocoding API → lat/lon/nome reale
    Step 2 — Meteo:     Open-Meteo Forecast API  → current + daily

    Returns:
        dict con i campi meteo, oppure None se la città non è trovata o c'è errore.
    """
    geo_url = (
        f"https://geocoding-api.open-meteo.com/v1/search"
        f"?name={nome_citta}&count=1&language=it&format=json"
    )

    try:
        async with aiohttp.ClientSession() as session:
            # ── Step 1: geocoding ─────────────────────────────────────────
            async with session.get(
                geo_url, timeout=aiohttp.ClientTimeout(total=8)
            ) as geo_resp:
                if geo_resp.status != 200:
                    logging.error(
                        f"[METEO] Geocoding HTTP {geo_resp.status} per '{nome_citta}'"
                    )
                    return None
                geo_data = await geo_resp.json()

            results = geo_data.get("results")
            if not results:
                logging.warning(
                    f"[METEO] Città '{nome_citta}' non trovata nel geocoding."
                )
                return None

            hit = results[0]
            lat = hit["latitude"]
            lon = hit["longitude"]
            city_label = hit.get("name", nome_citta.title())
            country = hit.get("country", "")
            if country:
                city_label = f"{city_label}, {country}"

            logging.info(f"[METEO] Geocoding OK: {city_label} → lat={lat}, lon={lon}")

            # ── Step 2: dati meteo ────────────────────────────────────────
            wx_url = (
                f"https://api.open-meteo.com/v1/forecast"
                f"?latitude={lat}&longitude={lon}"
                f"&current=temperature_2m,relativehumidity_2m,weathercode,windspeed_10m"
                f"&daily=temperature_2m_max,temperature_2m_min"
                f"&timezone=auto&forecast_days=1"
            )

            async with session.get(
                wx_url, timeout=aiohttp.ClientTimeout(total=8)
            ) as wx_resp:
                if wx_resp.status != 200:
                    logging.error(f"[METEO] Forecast HTTP {wx_resp.status}")
                    return None
                wx_data = await wx_resp.json()

            current = wx_data.get("current", {})
            daily = wx_data.get("daily", {})

            return {
                "city_label": city_label,
                "temperature_2m": current.get("temperature_2m"),
                "relativehumidity_2m": current.get("relativehumidity_2m"),
                "weathercode": current.get("weathercode"),
                "windspeed_10m": current.get("windspeed_10m"),
                "temperature_2m_max": (daily.get("temperature_2m_max") or [None])[0],
                "temperature_2m_min": (daily.get("temperature_2m_min") or [None])[0],
            }

    except asyncio.TimeoutError:
        logging.error(f"[METEO] Timeout durante il recupero dati per '{nome_citta}'.")
        return None
    except aiohttp.ClientError as e:
        logging.error(f"[METEO] Errore rete: {e}")
        return None
    except Exception as e:
        logging.error(f"[METEO] Errore imprevisto: {e}")
        return None


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


# Funzione per generare la lista dei file audio disponibili
def get_command_audio_files():
    audio_files = {}
    for i, file in enumerate(os.listdir(AUDIO_FOLDER)):
        if file.endswith((".mp3", ".wav")):
            audio_files[i + 1] = file
    return audio_files


import discord.ext.voice_recv as voice_recv
import wave


class WaveSink(voice_recv.AudioSink):
    def __init__(self, filename):
        self.filename = filename
        self.file = wave.open(filename, "wb")
        self.file.setsampwidth(2)
        self.file.setnchannels(2)
        self.file.setframerate(48000)

    def wants_opus(self):
        return False

    def write(self, user, data):
        self.file.writeframes(data.pcm)

    def cleanup(self):
        self.file.close()


async def stop_playback(interaction: discord.Interaction):
    """Ferma la riproduzione audio senza disconnettere il bot."""
    if vm.current_vc and vm.current_vc.is_playing():
        vm.current_vc.stop()
        await interaction.response.send_message("Riproduzione interrotta.")
    else:
        await interaction.response.send_message(
            "Non c'è nulla in riproduzione.", ephemeral=True
        )


async def disconnect_bot(interaction: discord.Interaction):
    """Disconnette il bot dal canale vocale."""
    if vm.current_vc and vm.current_vc.is_connected():
        await vm.disconnect()
        await interaction.response.send_message("Bot disconnesso dal canale vocale.")
    else:
        await interaction.response.send_message(
            "Il bot non è connesso a nessun canale vocale.", ephemeral=True
        )


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


async def lancio_bestemmia_commands(
    interaction: discord.Interaction,
    numerobestemmie: str,
    idChatBlasfemie: str,
    idChatTest: str,
    idSNC: str,
    idSupremo: str,
    botDiscord,
):
    voice_state = interaction.user.voice
    channel_id = interaction.channel.id
    user_role_ids = [role.id for role in interaction.user.roles]
    if (
        str(channel_id) in [idChatBlasfemie, idChatTest] and int(idSNC) in user_role_ids
    ) or int(idSupremo) in user_role_ids:
        if numerobestemmie == "":
            numerobestemmie = 1
        else:
            numerobestemmie = int(numerobestemmie)
        await interaction.response.send_message(
            f"Sto generando {numerobestemmie} bestemmie, eccole..."
        )
        with open("json/blasfemia.json", "r", encoding="utf-8") as file:
            data = json.load(file)
            startCounter = 1
            for startCounter in range(int(numerobestemmie)):
                custom_message = generatoreblasfemie.GeneratoreBlasfemie(
                    data
                ).frase_random()
                if (voice_state) and (voice_state.channel):
                    await text_to_speech(
                        custom_message,
                        f"bestemmie_{startCounter}",
                        voice_state.channel,
                    )
                    return custom_message
    else:
        await interaction.response.send_message(
            "Non sei nel canale giusto oppure non hai il ruolo per poter lanciare questo comando."
        )


async def lancia_bestemmia_casual():

    with open("json/blasfemia.json", "r", encoding="utf-8") as file:
        data = json.load(file)
        custom_message = generatoreblasfemie.GeneratoreBlasfemie(data).frase_random()
        try:
            filename = "audio_blasfemia.mp3"
            success = await tts.text_to_speech_async(custom_message, filename)

            if not success:
                logging.error("[BESTEMMIA] Errore nella generazione dell'audio")
                return
            await qm.audio_queue.put(
                {"channel": vm.current_vc.channel.id, "file": f"audio_blasfemia.mp3"}
            )
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
