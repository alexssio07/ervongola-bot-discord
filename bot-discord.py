# Standard library imports
import asyncio
from collections import defaultdict
import os
import json
import datetime
import sys
from typing import Optional

# Third-party imports
import discord
from discord.ext import commands, tasks
from discord.ext.commands import Context
from discord import (
    ActivityType,
    CustomActivity,
    Game,
    Streaming,
    Spotify,
    Embed,
)
from discord.ext.tasks import loop
from dotenv import load_dotenv
import nest_asyncio
import requests
import logging

# import ollama
# from ollama import Client

# Local imports
import generatoreblasfemie
import utils as ut
import voice_manager as vm

# import scraper

# Configurazione del logging
logging.basicConfig(
    level=logging.INFO,
    format="[{asctime}] [{levelname}] {message}",
    style="{",
    datefmt="%d/%m/%Y %H:%M:%S",
)
nest_asyncio.apply()
load_dotenv()

# Configurazioni
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
KEY_API_PERSONAL_AI = os.getenv("KEY_API_PERSONAL_AI")
KEY_JWT_PERSONAL_AI = os.getenv("KEY_JWT_PERSONAL_AI")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_GROUP_CHAT_ID = os.getenv("TELEGRAM_GROUP_CHAT_ID")
TELEGRAM_GROUP_THREAD_ID = os.getenv("TELEGRAM_GROUP_THREAD_ID")
ENABLE_MESSAGE_TELEGRAM = os.getenv("ENABLE_MESSAGE_TELEGRAM")

chats_database = {
    "chat_vocale_privato": "707198443751211140",
    "chat_vocale_privato2": "707514058990944256",
    "chat_vocale_privato3": "783252026766131222",
    "chat_for_ai_id_discord": "1206179021134499841",
    "chat_blasfemie_id_discord": "1256877516224729149",
    "chat_text_test_id": "1256593273246453823",
    "chat_news_tech": "1111287132242317384",
    "chat_news_general": "1250740873105244192",
    "chat_news_videogames": "798164535508336640",
    "chat_free_games": "1277205224381087754",
    "chat_afk": "679436863492194338",
    "chat_studio": "1242219732938264596",
    "chat_testing": "1278301118094376971",
}

id_users = {
    "alexssio": "190745296500686857",
    "lykanos": "366952021045280779",
    "dark_lord": "271371380467957762",
    "moonpantherredxvi": "399979832038916101",
    "melissa": "293497922870312961",
    "burzum": "303199273418489857",
    "carmineg": "275725325348896769",
}

names_users = {
    "alexssio": "alexssio",
    "lykanos": "lykanos94",
    "dark_lord": "6dark6lord6",
    "pantera": "moonpantherredxvi",
    "melissa": "melissa",
    "burzum": "crypo1398",
    ".carmineg": ".carmineg",
}

id_roles = {
    "corpo_di_ricerca": "1109819956524224532",
    "supremo": "679447959309516830",
    "SNC": "1256877870798602261",
}

ID_SERVER_DISCORD = "679423743017091083"
# id_bot_ervongola = "1205585120187261000"

MESSAGE_PERSON_IS_HERE = "è online, se vuoi vai a fargli compagnia... Stronzo."
MESSAGE_SPAM_MESSAGE_IS_HERE = "Aoh! Sono online, se vuoi farmi compagnia... Sto qua."
isOnChannel_users = {
    f"isOnChannel{names_users['alexssio']}": False,
    f"isOnChannel{names_users['lykanos']}": False,
    f"isOnChannel{names_users['dark_lord']}": False,
    f"isOnChannel{names_users['burzum']}": False,
}
isOn_Users = {
    f"isOn{names_users['alexssio']}": False,
    f"isOn{names_users['lykanos']}": False,
    f"isOn{names_users['dark_lord']}": False,
    f"isOn{names_users['burzum']}": False,
}

keys_question_roma = [
    "As Roma",
    "as roma",
    "partite",
    "partita",
    "biglietti",
    "biglietto",
]
users_online = []

last_notification = {}

# Soglia temporale: 6 ore prima di poter inviare nuovamente la notifica per lo stesso utente
NOTIFICATION_THRESHOLD = datetime.timedelta(hours=6)
FAILURE_THRESHOLD = 3  # dopo 3 check consecutivi, esci dal loop

# client_AI = Client(host="http://host.docker.internal:11434/api/generate -d")

if sys.platform.startswith("linux"):
    try:
        asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
    except Exception as e:
        print(f"[Init] Errore impostando event loop policy: {e}")

# Inizializzazione bot Discord
intents = discord.Intents.all()
intents.message_content = True
intents.guilds = True
intents.members = True
intents.presences = True
intents.voice_states = True
botDiscord = commands.Bot(command_prefix="!", intents=intents)
stop_event = asyncio.Event()  # Evento per fermare le operazioni asincrone
player_task: Optional[asyncio.Task] = None
watchdog_task: Optional[asyncio.Task] = None
WATCHDOG_FAILURE_THRESHOLD = 3
audio_queue = None


@loop(minutes=120)
async def check_online():
    """
    Questo metodo verrà chiamato ogni 70 minuti in loop fino a quando il bot non viene interrotto
    """
    actual_datetime_string = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    guild = botDiscord.get_guild(int(ID_SERVER_DISCORD))
    if guild is None:
        logging.error(
            f"[{actual_datetime_string}] [✘] Il server con ID {ID_SERVER_DISCORD} non è stato trovato."
        )
        return

    # Reset temporary online status tracking
    current_online_users = []

    # Itera sui membri del server
    for member in guild.members:
        if member.name in names_users.values():
            if member.bot or member.name == "BOT-ErVongola":  # Ignora i bot
                continue

            username = member.name.lower()
            is_user_active = False

            # Controlla se l'utente è nel canale vocale AFK o STUDIO e imposta lo stato offline
            if member.voice and member.voice.channel:
                if member.voice.channel.id not in (
                    int(chats_database["chat_afk"]),
                    int(chats_database["chat_studio"]),
                ):
                    is_user_active = True

            # Check member activities
            for activity in member.activities:
                activity_status = None

                if isinstance(activity, Game) or activity.type == ActivityType.playing:
                    activity_status = f"sta giocando a {activity.name}"
                elif (
                    isinstance(activity, Streaming)
                    or activity.type == ActivityType.streaming
                ):
                    activity_status = f"sta facendo streaming di {activity.name} su {activity.platform}"
                elif (
                    isinstance(activity, Spotify)
                    or activity.type == ActivityType.listening
                ):
                    activity_status = (
                        f"sta ascoltando {activity.title} di {activity.artist}"
                    )
                elif (
                    isinstance(activity, CustomActivity)
                    or activity.type == ActivityType.custom
                ):
                    activity_status = f"sta facendo {activity.name}"

                if activity_status:
                    is_user_active = True
                    logging.info(
                        f"[{actual_datetime_string}] {member.name} {activity_status}"
                    )

            # Aggiorno lo stato temporaneo per l'utente
            if username in names_users.values():
                user_key = next(
                    (key for key, value in names_users.items() if value == username),
                    None,
                )
                if user_key:
                    isOn_Users[f"isOn{username}"] = is_user_active
                    if is_user_active and username not in current_online_users:
                        current_online_users.append(username)

    # Aggiorna la lista degli utenti online globale
    global users_online
    users_online = current_online_users

    logging.info(
        f"[{actual_datetime_string}] {len(users_online)} utenti online: {users_online}"
    )


@botDiscord.event
async def on_disconnect():
    logging.warning(
        "[on_disconnect] Bot disconnesso dal gateway, creo una nuova sessione..."
    )

    # Cancella task ricorrenti per evitare duplicazioni
    global watchdog_task, player_task
    actual_datetime_string = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    if watchdog_task and not watchdog_task.done():
        watchdog_task.cancel()
        try:
            await watchdog_task
        except asyncio.CancelledError:
            logging.info(
                f"[{actual_datetime_string}] [on_disconnect] Watchdog annullato correttamente"
            )
    watchdog_task = None

    if player_task and not player_task.done():
        player_task.cancel()
        try:
            await player_task
        except asyncio.CancelledError:
            logging.info("[on_disconnect] Player annullato correttamente")
    player_task = None

    # Riavvia il bot con IDENTIFY (nuova sessione)
    await botDiscord.close()
    await botDiscord.start(DISCORD_TOKEN)


# Questo metodo viene invocato quando il bot Discord viene avviato e viene inizializzato
@botDiscord.event
async def on_ready():
    """
    Questo metodo viene invocato quando il bot Discord viene avviato e viene inizializzato
    """
    global player_task, watchdog_task, audio_queue
    actual_datetime_string = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    if audio_queue is None:
        audio_queue = asyncio.Queue()
    # rileva se è un riavvio o un reconnect
    if player_task or watchdog_task:
        logging.info(
            f"[{actual_datetime_string}] [on_ready] Rilevato reconnect del bot Discord"
        )
    else:
        logging.info(
            f"[{actual_datetime_string}] [on_ready] Avvio iniziale del bot Discord"
        )

    # cancella eventuali task precedenti se ancora vivi ma non validi
    for task_name, task in {
        "player_task": player_task,
        "watchdog_task": watchdog_task,
    }.items():
        if task and not task.done():
            logging.warning(
                f"[{actual_datetime_string}] [on_ready] Annullamento di {task_name} obsoleto"
            )
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    player_task = botDiscord.loop.create_task(
        ut.audio_player(audio_queue, botDiscord, None)
    )
    watchdog_task = botDiscord.loop.create_task(discord_watchdog(botDiscord))
    if not check_online.is_running():
        check_online.start()

    logging.info(
        f"[{actual_datetime_string}] Bot Er Vongola avviato con successo! ID: {botDiscord.user.id}"
    )
    logging.info(f"[{actual_datetime_string}] Versione del BOT: 4.6.0.5")
    try:
        comandiSync = await botDiscord.tree.sync()
        # for guild in botDiscord.guilds:
        #     print(f"Nome del Server: {guild.name}, ID del Server: {guild.id}")
        logging.info(f"Comandi sincronizzati per {botDiscord.user.name}")
        logging.info(f"Comandi sincronizzati: {comandiSync}")
    except discord.Forbidden:
        logging.error(
            f"[{actual_datetime_string}] [✘] Errore di autorizzazione durante la sincronizzazione dei comandi."
        )
    except Exception as e:
        logging.exception(f"[{actual_datetime_string}] [on_ready] Errore sync: {e}")


# Manda un messaggio di notifica nel gruppo di Telegram
async def send_message_to_Telegram(text):
    """Controlla se determinati utenti sono online e manda un messaggio di notifica nel gruppo di Telegram tramite un altro bot"""
    actual_datetime_string = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    urlAPITelegram = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data_chat_group = {
        "chat_id": TELEGRAM_GROUP_CHAT_ID,
        "message_thread_id": TELEGRAM_GROUP_THREAD_ID,
        "text": text,
    }
    try:
        responseGroup = requests.post(urlAPITelegram, data=data_chat_group)
        if responseGroup.status_code != 200:
            logging.error(
                f"[{actual_datetime_string}] [✘] Error sending message to Telegram: {responseGroup}"
            )
    except requests.RequestException as e:
        logging.error(
            f"[{actual_datetime_string}] [✘] Error sending message to Telegram: {e}"
        )


@botDiscord.event
async def on_voice_state_update(member, before, after):
    """
    Questo metodo viene invocato ogni volta che c'è un cambio di stato sul member e su quale canale si è spostato
    """
    actual_datetime_string = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    logging.info(
        f"[{actual_datetime_string}] Canale-p: {before.channel}, Canale-d: {'Nessuno' if after.channel is None else after.channel}, Utente: {member.name}"
    )
    if member.name in names_users.values() and not member.bot:
        if (
            before.channel is None
            and after.channel is not None
            and member.name != ""
            and member.name is not None
            and member.name in names_users.values()
        ):
            if str(after.channel.id) in (
                chats_database["chat_vocale_privato"],
                chats_database["chat_vocale_privato2"],
                chats_database["chat_vocale_privato3"],
            ):
                # Registro l'ora e il giorno dell'entrata
                now = datetime.datetime.now()
                send_notification = False

                # Controlla se l'utente ha già ricevuto una notifica nelle ultime 6 ore
                if member.id not in last_notification and member.name in (
                    names_users["alexssio"],
                    names_users["lykanos"],
                    names_users["dark_lord"],
                ):
                    send_notification = True
                else:
                    last_time = last_notification.get(member.id)
                    if last_time is None:
                        last_notification[member.id] = now
                    elif now - last_time >= NOTIFICATION_THRESHOLD:
                        send_notification = True
                # Registro la data e l'ora attuale per l'invio della notifica
                actual_datetime_string = now.strftime("%d/%m/%Y %H:%M:%S")
                if send_notification:
                    last_notification[member.id] = now
                    if member.name in (names_users["alexssio"], names_users["lykanos"]):
                        text = f"@BradipinoMetallaro64551 {member.name} è entrato nel canale vocale {after.channel.name}"
                    else:
                        text = f"{member.name} è entrato nel canale vocale {after.channel.name}"
                    if ENABLE_MESSAGE_TELEGRAM:
                        await send_message_to_Telegram(text)
                elif member.name != "BOT-ErVongola":
                    logging.warning(
                        f"[{actual_datetime_string}] Notifica non inviata a {member.name} in questo intervallo di tempo."
                    )
        if after.channel is None:
            sync_user_status(member, online=False)
        elif after.channel and after.channel.id in (
            int(chats_database["chat_afk"]),
            int(chats_database["chat_studio"]),
        ):
            sync_user_status(member, online=False, voice_state=after)
        elif before.channel != after.channel:
            sync_user_status(member, online=True, voice_state=after)
            await ut.make_audio(botDiscord, member, after.channel.id, audio_queue)

        if before.channel and before.channel.id in (
            int(chats_database["chat_afk"]),
            int(chats_database["chat_studio"]),
        ):
            sync_user_status(member, online=False, voice_state=before)

    logging.info(
        f"[{actual_datetime_string}] {len(users_online)} utenti online: {users_online}"
    )


async def discord_watchdog(botDiscord: discord.Client, check_interval=180):
    """
    Watchdog che controlla periodicamente lo stato del gateway Discord e della connessione vocale.
    Se qualcosa va storto, tenta di ripristinare le connessioni senza mai terminare il processo.
    """
    await botDiscord.wait_until_ready()
    actual_datetime_string = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    logging.info(
        f"[{actual_datetime_string}] [WATCHDOG] Avviato controllo connessioni Discord"
    )

    gateway_failures = 0
    voice_failures = 0

    while not botDiscord.is_closed():
        await asyncio.sleep(check_interval)
        try:
            # --- Controllo GATEWAY WS ---
            ws = getattr(botDiscord, "ws", None)
            ws_open = bool(ws and getattr(ws, "open", False))
            if not ws_open:
                gateway_failures += 1
                logging.warning(
                    f"[{actual_datetime_string}] [WATCHDOG] Gateway WS non valido (count={gateway_failures})"
                )

                if gateway_failures >= WATCHDOG_FAILURE_THRESHOLD:
                    logging.error(
                        "[{actual_datetime_string}] [WATCHDOG] Gateway WS non recuperabile, tentativo di reconnect..."
                    )
                    try:
                        await botDiscord.close()
                        await botDiscord.login(
                            botDiscord.http.token, botDiscord.user.bot
                        )
                        await botDiscord.connect(reconnect=True)
                        gateway_failures = 0
                    except Exception as e:
                        logging.exception(
                            f"[{actual_datetime_string}] [WATCHDOG] Errore reconnect gateway: {e}"
                        )
            else:
                gateway_failures = 0

            # --- Controllo VOICE CLIENT ---
            vc = vm.current_vc
            if not vc:
                continue

            voice_ws = getattr(vc, "ws", None)
            voice_ok = bool(
                vc.is_connected() and voice_ws and getattr(voice_ws, "open", False)
            )

            if not voice_ok:
                voice_failures += 1
                logging.warning(
                    f"[{actual_datetime_string}] [WATCHDOG] Connessione vocale non valida (count={voice_failures})"
                )

                if voice_failures >= WATCHDOG_FAILURE_THRESHOLD:
                    logging.error(
                        "[{actual_datetime_string}] [WATCHDOG] VC non recuperabile, forzo disconnect e reset"
                    )
                    try:
                        await vc.disconnect(force=True)
                    except Exception as e:
                        logging.exception(
                            f"[{actual_datetime_string}] [WATCHDOG] Errore durante disconnect VC: {e}"
                        )
                    finally:
                        vm.current_vc = None

                    voice_failures = 0
            else:
                voice_failures = 0

        except Exception as e:
            logging.exception(
                f"[{actual_datetime_string}] [WATCHDOG] Errore interno: {e}"
            )


def sync_user_status(member, online=True, voice_state=None):
    """
    Questo metodo sincronizza lo stato dell'utente con la lista degli utenti monitorati
    """
    actual_datetime_string = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    global users_online  # Variabile glo per gli utenti online
    current_online_users = users_online
    username = member.name.lower()

    if username not in names_users.values():
        return  # Non è uno degli utenti monitorati

    # Trova il nome utente corrispondente nel dizionario names_users
    user_key = next(
        (key for key, value in names_users.items() if value == username), None
    )
    if user_key is None:
        return  # Nome utente non trovato

    # Controlla se l'utente è entrato dentro AFK o STUDIO e imposta lo stato offline
    in_excluded_channel = (
        voice_state
        and voice_state.channel
        and voice_state.channel.id
        in (int(chats_database["chat_afk"]), int(chats_database["chat_studio"]))
    )
    # Aggiorna lo stato dell'utente
    if f"isOn{user_key}" in isOn_Users:
        # Imposta lo stato offline se l'utente non è online o se è entrato in uno dei canali esclusi
        if not online or in_excluded_channel:
            isOn_Users[f"isOn{user_key}"] = False
            if username in current_online_users:
                current_online_users.remove(username)
                logging.info(f"[{actual_datetime_string}] {username} è ora offline")
        else:
            isOn_Users[f"isOn{user_key}"] = True
            if username not in users_online:
                users_online.append(username)
                logging.info(f"[{actual_datetime_string}] {username} ora online")

    # Aggiorna la lista degli utenti online globale
    users_online = current_online_users


@botDiscord.tree.command(
    name="list_audio_commands",
    description="Visualizza la lista dei file audio disponibili per i comandi vocali",
)
async def list_audio(interaction: discord.Interaction):
    audio_files = ut.get_command_audio_files()
    if not audio_files:
        await interaction.response.send_message(
            "Nessun file audio disponibile.", ephemeral=True
        )
        return

    audio_list = "\n".join([f"{id}: {name}" for id, name in audio_files.items()])
    embed = Embed(
        title="Comando completato",
        description=f"Ecco la lista dei file audio:\n```\n{audio_list}\n``` Scrivi /play_audio_command e il numero dell'audio per riprodurre il file.",
        color=0x00FF00,
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)


# Funzione per gestire la riproduzione della coda
async def play_queue(vc: discord.VoiceClient):
    global audio_queue
    actual_datetime_string = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    while not audio_queue.empty():
        # Ottieni il prossimo file dalla coda
        item = await audio_queue.get()
        current_audio = item["audio"]
        interaction = item["interaction"]
        if not "news" in current_audio:
            audio_path = os.path.join(ut.AUDIO_FOLDER, current_audio)
        else:
            audio_path = current_audio
        logging.info(
            f"[{actual_datetime_string}] [play_queue] Coda audio: {audio_queue}"
        )
        logging.info(
            f"[{actual_datetime_string}] [play_queue] Audio file rimanenti: {audio_queue.qsize()}"
        )
        if not os.path.exists(audio_path):
            logging.error(f"[✘] File audio non trovato: {audio_path}")
            audio_queue.task_done()
            continue

        # Riproduci il file audio
        try:
            source = discord.FFmpegPCMAudio(source=audio_path)
            vc.play(source)
        except discord.ClientException as e:
            logging.error("[✘] Errore di connessione al canale vocale.", exc_info=e)
            if interaction.response.is_done():
                # Se l'interazione è già stata rispinta, invia un messaggio
                await interaction.followup.send(...)


# Comando per riprodurre un file audio dato il suo ID
@botDiscord.tree.command(
    name="play_audio_command",
    description="Riproduce un file audio secondo il suo ID, visualizzabile con `/list_audio_commands`",
)
async def play_audio(interaction: discord.Interaction, audio_id: int):
    global audio_queue

    if not isinstance(audio_id, int) or audio_id < 0:
        await interaction.response.send_message("ID audio non valido.", ephemeral=True)
        return

    audio_files = ut.get_command_audio_files()
    if audio_id not in audio_files:
        await interaction.response.send_message(
            "ID audio non valido. Usa `/list_audio_commands` per vedere gli ID disponibili.",
            ephemeral=True,
        )
        return

    # Controlla se l'utente è in un canale vocale
    if not interaction.user.voice or not interaction.user.voice.channel:
        await interaction.response.send_message(
            "Devi essere in un canale vocale per usare questo comando.", ephemeral=True
        )
        return

    voice_channel = interaction.user.voice.channel

    # Controllo permessi bot
    if (
        not voice_channel.permissions_for(interaction.guild.me).connect
        or not voice_channel.permissions_for(interaction.guild.me).speak
    ):
        await interaction.response.send_message(
            "Non ho i permessi per connettermi o parlare in questo canale vocale.",
            ephemeral=True,
        )
        return

    # Estrai i contenuti correnti dalla coda per evitare duplicati
    existing_items = list(audio_queue._queue)  # attenzione: attributo "protetto"
    if any(item["audio"] == audio_files[audio_id] for item in existing_items):
        await interaction.response.send_message(
            f"L'audio `{audio_files[audio_id]}` è già in coda.", ephemeral=True
        )
        return

    # Risposta immediata all'utente
    await interaction.response.send_message(
        "Elaborazione del comando... Attendi un momento.", ephemeral=True
    )
    await audio_queue.put(
        {
            "audio": os.path.join(ut.AUDIO_FOLDER, audio_files[audio_id]),
            "interaction": interaction,
            "channel": voice_channel,
        }
    )
    ut.add_to_pending_by_guild()
    embed = Embed(
        title="Audio in coda",
        description=f"Aggiunto alla coda: `{audio_files[audio_id]}`. Verrà riprodotto a breve.",
        color=0x00FF00,
    )
    if not interaction.is_expired():
        await interaction.followup.send(embed=embed, ephemeral=True)
    vc = discord.utils.get(botDiscord.voice_clients, guild=botDiscord.guilds[0])

    try:
        if not vc or not vc.is_connected():
            vc = await vm.connect_to_channel(voice_channel, botDiscord, interaction)
            if vc is not None and not vc.is_playing():
                await play_queue(vc)

    except discord.errors.ClientException as e:
        logging.error(f"[✘] Errore Discord Client: {e}")
        if not interaction.is_expired():
            await interaction.followup.send("Errore Discord Client.", ephemeral=True)
    except Exception as e:
        logging.error(f"[✘] Errore generico: {e}")
        if not interaction.is_expired():
            await interaction.followup.send(
                "Si è verificato un errore imprevisto.", ephemeral=True
            )


# Questo metodo cattura i messaggi testuali
# @botDiscord.event
# async def on_message(message):
#     if message.author.bot:
#         return
#     message_user = str(message.content)
#     for value in keys_question_roma:
#         if value in message_user:
#             print("hai domandato cose riguardo la Roma")
#             await scraper.checkInfoFromSite()
#             return
#     if message_user != "" and message.channel.id == int(chat_for_ai_id_discord) or isinstance(message.channel, discord.DMChannel) or message.channel.id == int(chat_text_test_id):
#         print(
#             f"Messaggio ricevuto da {message.author}: {message_user}",
#             flush=True,
#         )
#         try:
#             response = client_AI.chat(
#                 model="gemma2",
#                 messages=[
#                     {
#                         "role": "user",
#                         "content": message_user,
#                     },
#                 ],
#             )
#             print(f"Response bot: {response}", flush=True)
#             responseFormatted = response["message"]["content"]
#             await message.channel.send(content=responseFormatted[:1999])
#             if len(responseFormatted) >= 1999:
#                 for i in range(0, 1999, 1999):
#                     await message.channel.send(content=responseFormatted[i : i + 1999])
#             print(responseFormatted, flush=True)
#         except ollama.ResponseError as e:
#             print(e, flush=True)
#             await message.reply(
#                 f"Si è verificato un errore durante l'elaborazione della richiesta. {e}"
#             )
# @tasks.loop(minutes=2)
# async def keep_voice_alive(botDiscord):
#     for vc in botDiscord.voice_clients:
#         if not vc.is_playing():
#             try:
#                 await asyncio.sleep(5)
#                 logging.info("Keep-alive: suono silenzioso riprodotto")
#             except Exception as e:
#                 logging.error(f"Errore keep-alive: {e}")


@botDiscord.tree.command(
    name="ping", description="It will show the ping latecy of the bot"
)
async def ping(interaction: discord.Interaction):
    """It will show the ping latecy of the bot"""
    await interaction.response.send_message(f"{round(botDiscord.latency * 1000)}ms")


@botDiscord.tree.command(
    name="help", description="Mostra aiuto e supporto riguardo al bot"
)
async def info_help(interaction: discord.Interaction):
    """Mostra aiuto e supporto riguardo al bot"""

    await interaction.response.send_message("Ecco le info riguardo il bot :")
    await interaction.channel.send(
        "Sono un'assistente virtuale chiamato Er Vongola, super potente e cazzuto in grado di annunciare l'entrata di alcuni specifici utenti che lo desiderano, quando entrano in determinati canali vocali."
    )
    await interaction.channel.send(
        "Può assistervi come farebbe una vera intelligenza artificiale attraverso la chat testuale 'parla-con-l-ia' o attraverso la sua chat privata."
    )
    await interaction.channel.send(
        "Scrivi / in una delle chat testuali a disposizione per visualizzare la lista dei comandi disponibili."
    )


@botDiscord.tree.command(
    name="avvisa_darklord",
    description="Manda un messaggio a DarkLord per comunicargli che siamo online... Comando PRIVATO",
)
async def avvisa_darklord(interaction: discord.Interaction):
    """Manda un messaggio a DarkLord per comunicargli che siamo online..."""
    member_interaction = interaction.user
    dark_Lord = await botDiscord.fetch_user(id_users["dark_lord"])
    if member_interaction.roles != None:
        has_role = any(
            role.id == int(id_roles["corpo_di_ricerca"])
            or role.id == int(id_roles["supremo"])
            for role in member_interaction.roles
        )
        # Controlla se l'utente ha il ruolo richiesto per inviare il messaggio
        if has_role:
            logging.info(
                f"[{datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')}] Utente {member_interaction.name} ha il ruolo richiesto"
            )
            if interaction.user.name.lower() == "alexssio":
                await dark_Lord.send(
                    f"{member_interaction.name} {MESSAGE_PERSON_IS_HERE}"
                )
                await interaction.response.send_message(
                    "Messaggio inviato!", ephemeral=True
                )
            if interaction.user.name.lower() == "lykanos94":
                await dark_Lord.send(
                    f"{member_interaction.name} {MESSAGE_PERSON_IS_HERE}"
                )
                await interaction.response.send_message(
                    "Messaggio inviato!", ephemeral=True
                )
        else:
            await interaction.response.send_message(
                "Non hai il ruolo richiesto per inviare il messaggio",
                ephemeral=True,
            )
    else:
        await interaction.response.send_message(
            "Devi essere connesso al server per poter inviare il messaggio",
            ephemeral=True,
        )


@botDiscord.tree.command(
    name="avvisa_alexssio",
    description="Manda un messaggio ad Alexssio per comunicargli che DarkLord è online... Comando PRIVATO",
)
async def avvisa_alexssio(interaction: discord.Interaction):
    """Manda un messaggio ad Alexssio e Lykanos per comunicargli che DarkLord è online..."""
    interacted_member = interaction.user
    alexssio = await botDiscord.fetch_user(id_users["alexssio"])
    if interacted_member.roles != None:
        has_role = any(
            role.id == int(id_roles["corpo_di_ricerca"])
            or role.id == int(id_roles["supremo"])
            for role in interacted_member.roles
        )
        # Controlla se l'utente ha il ruolo richiesto per inviare il messaggio

        if has_role:
            await alexssio.send(f"{interacted_member.name} {MESSAGE_PERSON_IS_HERE}")
            await interaction.response.send_message(
                "Messaggio inviato!", ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "Non hai il ruolo richiesto per inviare il messaggio", ephemeral=True
            )
    else:
        await interaction.response.send_message(
            "Devi essere connesso al server per poter inviare il messaggio",
            ephemeral=True,
        )


@botDiscord.tree.command(
    name="avvisa_lykanos",
    description="Manda un messaggio ad Lykanos per comunicargli che DarkLord è online... Comando PRIVATO",
)
async def avvisa_lykanos(interaction: discord.Interaction):
    """Manda un messaggio a Lykanos per comunicargli che DarkLord è online..."""
    interacted_member = interaction.user
    lykanos = await botDiscord.fetch_user(id_users["lykanos"])
    if interacted_member.roles != None:
        has_role = any(
            role.id == int(id_roles["corpo_di_ricerca"])
            or role.id == int(id_roles["supremo"])
            for role in interacted_member.roles
        )
        # Controlla se l'utente ha il ruolo richiesto per inviare il messaggio
        if has_role:
            await lykanos.send(f"{interacted_member.name} {MESSAGE_PERSON_IS_HERE}")
            await interaction.response.send_message(
                "Messaggio inviato!", ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "Non hai il ruolo richiesto per inviare il messaggio", ephemeral=True
            )
    else:
        await interaction.response.send_message(
            "Devi essere connesso al server per poter inviare il messaggio",
            ephemeral=True,
        )


# Funzione per generare casualmente una bestemmia scrivendola in chat e creando un file audio che riprodurrà immediatamente tramite il metodo text_to_speech
@botDiscord.tree.command(
    name="bestemmia",
    description="Il Bot Er Vongola entrerà nel canale vocale e invierà un tot bestemmie",
)
async def bestemmia(interaction: discord.Interaction, numerobestemmie: str):
    """Il Bot Er Vongola entrerà nel canale vocale e invierà un tot bestemmie causali"""
    voice_state = interaction.user.voice
    channel_id = interaction.channel.id
    user_role_ids = [role.id for role in interaction.user.roles]

    if (
        str(channel_id)
        in [chats_database["chat_blasfemie_id_discord"], chats_database["chat_testing"]]
        and int(id_roles["SNC"]) in user_role_ids
    ) or int(id_roles["supremo"]) in user_role_ids:
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
                await interaction.channel.send(custom_message)
                if (voice_state) and (voice_state.channel):
                    await ut.text_to_speech(
                        custom_message,
                        f"bestemmie_{startCounter}",
                        voice_state.channel,
                        audio_queue,
                    )
    else:
        await interaction.response.send_message(
            "Non sei nel canale giusto oppure non hai il ruolo per poter lanciare questo comando."
        )


# @botDiscord.tree.command(name="barzelletta", description="Genera una barzelletta")
# async def barzeletta(interaction: discord.Interaction):
#     """Genera una barzelletta, entra nel canale vocale e la riproduce"""

#     await interaction.response.send_message("Sto generando una barzeletta, eccola...")
#     try:
#         response = client_AI.chat(
#             model="gemma2",
#             messages=[
#                 {
#                     "role": "user",
#                     "content": "raccontami una barzeletta divertente e spassosa in italiano",
#                 },
#             ],
#         )
#         responseFormatted = response["message"]["content"]
#         await interaction.channel.send(content=responseFormatted[:1999])
#         if len(responseFormatted) >= 1999:
#             for i in range(0, 1999, 1999):
#                 await interaction.channel.send(content=responseFormatted[i: i + 1999])
#         print(
#             f"[{datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')}] {responseFormatted}", flush=True)
#         if interaction.channel != None:
#             await ut.text_to_speech(
#                 botDiscord, responseFormatted, "barzeletta", interaction.channel.id
#             )
#         else:
#             await interaction.response.send_message(
#                 "Non posso leggerti la barzeletta perché non sei connesso a nessun canale vocale.",
#                 ephemeral=True,
#             )
#     except ollama.ResponseError as e:
#         print(
#             f"[{datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')}] {e}", flush=True)
#         await interaction.response.send_message(
#             f"Si è verificato un errore durante l'elaborazione della richiesta. {e}"
#         )


# @botDiscord.tree.command(name="freddura", description="Genera una freddura/battuta")
# async def freddura(interaction: discord.Interaction):
#     """
#     Genera una freddura/battuta, entra nel canale vocale e la riproduce
#     """

#     try:
#         await interaction.response.send_message(
#             "Sto generando una freddura, eccola..."
#         )
#         response = client_AI.chat(
#             model="gemma2",
#             messages=[
#                 {
#                     "role": "user",
#                     "content": "raccontami una freddura divertente o squallida oppure una battuta",
#                 },
#             ],
#         )
#         responseFormatted = response["message"]["content"]
#         await interaction.channel.send(content=responseFormatted[:1999])
#         if len(responseFormatted) >= 1999:
#             for i in range(0, 1999, 1999):
#                 await interaction.channel.send(content=responseFormatted[i: i + 1999])
#         print(
#             f"[{datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')}] {responseFormatted}", flush=True)
#         if (interaction.channel) != None:
#             await ut.text_to_speech(
#                 botDiscord, responseFormatted, "freddura", interaction.channel.id
#             )
#         else:
#             await interaction.response.send_message(
#                 "Non posso leggerti la freddura perché non sei connesso a nessun canale vocale.",
#                 ephemeral=True,
#             )
#     except ollama.ResponseError as e:
#         print(
#             f"[{datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')}] {e}", flush=True)


@botDiscord.tree.command(
    name="lista_categorie_news",
    description="Entra nel canale vocale e ti legge 'n' notizie riguardo l'ambito che sceglierai.",
)
async def get_list_categories_news(interaction: discord.Interaction):
    """
    Entra nel canale vocale dove ti trovi e ti legge tot -> 'countnews' notizie riguardo l'ambito che sceglierai -> 'category'
    """

    await interaction.response.send_message(
        "Ecco la lista delle categorie disponibili:\n tecnologia, cronaca, neuroscienze, ansa, videogames, robotica, scienza, titoli (notizie flash), dal mondo, spazio, ansa, medicina",
        ephemeral=True,
    )
    return


@botDiscord.tree.command(
    name="read_news",
    description="Entra nel canale vocale, ti legge 'n' notizie riguardo l'ambito.",
)
async def read_news(interaction: discord.Interaction, countnews: int, category: str):
    """
    Entra nel canale vocale leggendoti 'n' News notizie riguardo l'ambito che sceglierai nella 'category'
    Le categorie disponibili sono: tecnologia, cronaca, neuroscienze, ansa, videogames, robotica, scienza, titoli, dal mondo, spazio, ansa, medicina
    """

    if countnews == "":
        countnews = 1

    if category == None or category == "":
        await interaction.response.send_message(
            "Devi specificare una categoria valida. Sceglila con il comando /lista_categorie_news",
            ephemeral=True,
        )
        return

    await interaction.response.send_message(
        f"Ti sto per leggere {countnews} notizie riguardo l'ambito della {category}",
        ephemeral=True,
    )
    await ut.take_news(interaction, countnews, category, audio_queue)


# @botDiscord.tree.command(
#     name="read_tech_news",
#     description="Entra nel canale vocale dove ti trovi e ti legge 'n' notizie riguardo l'ambito della tecnologia",
# )
# async def read_tech_news(interaction: discord.Interaction, countnews: int):
#     """
#     Entra nel canale vocale dove ti trovi e ti legge tot -> 'countnews' notizie riguardo l'ambito della tecnologia
#     """

#     if countnews == "" or countnews == None:
#         countnews = 1

#     await interaction.response.send_message(
#         f"Ti sto per leggere {countnews} notizie riguardo l'ambito della tecnologia",
#         ephemeral=True,
#     )
#     await ut.take_news(interaction, countnews, "tecnologia", audio_queue)


# @botDiscord.tree.command(
#     name="read_neuroscienze_news",
#     description="Entra nel canale vocale dove ti trovi e ti legge 'n' notizie riguardo l'ambito delle Neuroscienze",
# )
# async def read_neuroscienze_news(interaction: discord.Interaction, countnews: int):
#     """
#     Entra nel canale vocale dove ti trovi e ti legge tot -> 'countnews' notizie riguardo l'ambito delle Neuroscienze
#     Le neuroscienze sono l'insieme degli studi scientificamente condotti sul sistema nervoso.
#     """

#     if countnews == "" or countnews == None:
#         countnews = 1

#     await interaction.response.send_message(
#         f"Ti sto per leggere {countnews} notizie riguardo l'ambito delle Neuroscienze, Le neuroscienze sono l'insieme degli studi scientificamente condotti sul sistema nervoso.",
#         ephemeral=True,
#     )
#     await ut.take_news(interaction, countnews, "neuroscienze", audio_queue)


# @botDiscord.tree.command(
#     name="read_ansa_news",
#     description="Entra nel canale vocale dove ti trovi e ti legge 'n' notizie prese dal sito ANSA.it",
# )
# async def read_ansa_news(interaction: discord.Interaction, countnews: int):
#     """
#     Entra nel canale vocale dove ti trovi e ti legge tot -> 'countnews' notizie prese dal sito ANSA.it
#     """

#     if countnews == "" or countnews == None:
#         countnews = 1

#     await interaction.response.send_message(
#         f"Ti sto per leggere {countnews} notizie prese dal sito ANSA.it",
#         ephemeral=True,
#     )
#     await ut.take_news(interaction, countnews, "ansa", audio_queue)


# @botDiscord.tree.command(
#     name="read_cronaca_news",
#     description="Entra nel canale vocale dove ti trovi e ti legge 'n' notizie riguardo l'ambito generale, di cronaca",
# )
# async def read_cronaca_news(interaction: discord.Interaction, countnews: int):
#     """Entra nel canale vocale dove ti trovi e ti legge 'n' notizie riguardo l'ambito generale, di cronaca"""

#     if countnews == "" or countnews == None:
#         countnews = 1

#     await interaction.response.send_message(
#         f"Ti sto per leggere {countnews} notizie riguardo l'ambito generale, di cronaca",
#         ephemeral=True,
#     )
#     await ut.take_news(interaction, countnews, "cronaca", audio_queue)


# @botDiscord.tree.command(
#     name="read_videogames_news",
#     description="Entra nel canale vocale dove ti trovi e ti legge 'n' notizie riguardo l'ambito dei videogames",
# )
# async def read_videogames_news(interaction: discord.Interaction, countnews: int):
#     """Entra nel canale vocale dove ti trovi e ti legge 'n' notizie riguardo l'ambito dei videogames"""

#     if countnews == "" or countnews == None:
#         countnews = 1

#     await interaction.response.send_message(
#         f"Ti sto per leggere {countnews} notizie riguardo l'ambito dei videogiochi",
#         ephemeral=True,
#     )
#     await ut.take_news(interaction, countnews, "videogames", audio_queue)


# @botDiscord.tree.command(
#     name="read_robotica_news",
#     description="Entra nel canale vocale dove ti trovi e ti legge 'n' notizie riguardo l'ambito della robotica",
# )
# async def read_robotica_news(interaction: discord.Interaction, countnews: int):
#     """
#     Entra nel canale vocale dove ti trovi e ti legge tot -> 'countnews' notizie riguardo l'ambito della robotica
#     """

#     if countnews == "" or countnews == None:
#         countnews = 1

#     await interaction.response.send_message(
#         f"Ti sto per leggere {countnews} notizie riguardo l'ambito della robotica",
#         ephemeral=True,
#     )
#     await ut.take_news(interaction, countnews, "robotica", audio_queue)


# @botDiscord.tree.command(
#     name="read_fresh_news",
#     description="Entra nel canale vocale dove ti trovi e ti legge 'n' notizie generiche uscite poche ore fa",
# )
# async def read_fresh_news(interaction: discord.Interaction, countnews: int):
#     """
#     Entra nel canale vocale dove ti trovi e ti legge tot -> 'countnews' notizie generiche uscite poche ore fa
#     """

#     if countnews == "" or countnews == None:
#         countnews = 1

#     await interaction.response.send_message(
#         f"Ti sto per leggere {countnews} notizie di natura generica uscite recentemente...",
#         ephemeral=True,
#     )
#     await ut.take_news(interaction, countnews, "titoli", audio_queue)


# @botDiscord.tree.command(
#     name="read_dal_mondo_news",
#     description="Entra nel canale vocale dove ti trovi e ti legge 'n' notizie riguardo tutto il mondo",
# )
# async def read_dal_mondo_news(interaction: discord.Interaction, countnews: int):
#     """
#     Entra nel canale vocale dove ti trovi e ti legge tot -> 'countnews' notizie riguardo l'ambito della robotica
#     Il ranking di queste notizie è determinato da una serie di fattori, tra cui la pertinenza, l'evidenza, l'autorevolezza,
#     l'attualità e l'usabilità dei contenuti, nonché, se consentito dalle tue impostazioni, dai tuoi interessi, che hai specificato
#     o che abbiamo dedotto dalla tua attività passata con i prodotti Google, dalla lingua e dalla località.
#     Google potrebbe avere un contratto di licenza con alcuni di questi editori, che però non incide sul ranking dei risultati.
#     """

#     if countnews == "" or countnews == None:
#         countnews = 1

#     await interaction.response.send_message(
#         f"Ti sto per leggere {countnews} notizie riguardo tutto il mondo",
#         ephemeral=True,
#     )
#     await ut.take_news(interaction, countnews, "dal-mondo", audio_queue)


# @botDiscord.tree.command(
#     name="read_space_news",
#     description="Entra nel canale vocale dove ti trovi e ti legge 'n' notizie riguardo lo Spazio",
# )
# async def read_space_news(interaction: discord.Interaction, countnews: int):
#     """
#     Entra nel canale vocale dove ti trovi e ti legge tot -> 'countnews' notizie riguardo l'ambito della Spazio
#     """

#     if countnews == "" or countnews == None:
#         countnews = 1

#     await interaction.response.send_message(
#         f"Ti sto per leggere {countnews} notizie riguardo l'ambito dello Spazio",
#         ephemeral=True,
#     )
#     await ut.take_news(interaction, countnews, "spazio", audio_queue)


# @botDiscord.tree.command(
#     name="read_medicina_news",
#     description="Entra nel canale vocale dove ti trovi e ti legge 'n' notizie riguardo la Medicina",
# )
# async def read_medicina_news(interaction: discord.Interaction, countnews: int):
#     """
#     Entra nel canale vocale dove ti trovi e ti legge tot -> 'countnews' notizie riguardo l'ambito della Medicina
#     """

#     if countnews == "" or countnews == None:
#         countnews = 1

#     await interaction.response.send_message(
#         f"Ti sto per leggere {countnews} notizie riguardo l'ambito dello Medicina",
#         ephemeral=True,
#     )
#     await ut.take_news(interaction, countnews, "medicina", audio_queue)


@botDiscord.tree.command(
    name="freevideogames",
    description="Ti legge l'ultimo gioco gratis del momento su Epic Games Store e/o Steam",
)
async def freevideogames(interaction: discord.Interaction):
    """Entra nel canale vocale dove ti trovi e ti legge i giochi gratuiti del momento su Epic Games Store e/o Steam"""

    channel_free_videogames = botDiscord.get_channel(
        int(chats_database["chat_free_games"])
    )
    await interaction.response.send_message(
        "Ti sto per leggere il nome del gioco gratuito del momento su Epic Games Store e/o Steam",
        ephemeral=True,
    )
    name_videogame_free = await ut.leggi_giochi_gratis(
        interaction, channel_free_videogames, audio_queue
    )
    if name_videogame_free != "" and name_videogame_free != None:
        await interaction.channel.send(
            f"Al momento è disponibile {name_videogame_free}"
        )


@botDiscord.tree.command(
    name="suggerimento", description="Invia un suggerimento per una nuova funzione"
)
async def suggerimento(interaction: discord.Interaction, testo: str):
    """Invia un suggerimento per una nuova funzione per il bot"""

    with open("app/outfiles/suggerimenti.txt", "a", encoding="utf-8") as file:
        file.write(f"{interaction.user}: {testo}\n")
    await interaction.response.send_message("Grazie per il tuo suggerimento!")


# TO DO Da correggere in base a come fare gli audio quando un utente entra nel canale
@botDiscord.tree.command(
    name="play_youtube_video",
    description="Riproduce audio da YouTube nel canale vocale con un volume di default di 100% o volume impostato",
)
async def play_youtube_video(
    interaction: discord.Interaction, url: str, volume: int = 100
):
    """Riproduce audio da YouTube nel canale vocale con un volume di default di 100% o volume impostato"""

    await ut.play_youtube_video(botDiscord, interaction, url, volume)


@botDiscord.tree.command(
    name="stop",
    description="Ferma la riproduzione audio e disconnette il bot dal canale vocale",
)
async def stop(interaction: discord.Interaction):
    """Ferma la riproduzione audio e disconnette il bot dal canale vocale"""

    await ut.stop(interaction)


@botDiscord.tree.command(
    name="meteo",
    description="Mostra le previsioni meteo per la città specificata da diverse fonti",
)
async def meteo(interaction: discord.Interaction, citta: str):
    """Mostra le previsioni meteo per la città specificata da diverse fonti"""
    await ut.leggi_meteo(interaction, citta)


@botDiscord.tree.command(
    name="lae",
    description="IN BETA TEST > Il bot inizia ad ascoltarti ed esegue specifici comandi, POTREBBE NON FUNZIONARE.",
)
async def joinandlisten(interaction: discord.Interaction):
    """Il bot si unisce al canale ed inizia ad ascoltarti eseguendo specifici comandi"""
    # TO DO DA FARE
    # await ut.join_and_listen(interaction)


@botDiscord.tree.error
async def on_app_command_error(interaction: discord.Interaction, error):
    logging.error(f"[✘] Errore nel comando: {error}")
    await interaction.response.send_message(
        "Si è verificato un errore durante l'esecuzione del comando.", ephemeral=True
    )


@check_online.before_loop
async def before_monitor_members():
    logging.info(
        f"[{datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')}] - Avvio del monitoraggio dei membri..."
    )
    await botDiscord.wait_until_ready()


# Esegui il bot Discord e inizializza il monitoraggio degli utenti
users_online = []
botDiscord.run(DISCORD_TOKEN)
