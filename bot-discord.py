# Standard library imports
import asyncio
import os
import json
import datetime

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
    app_commands,
)
from discord.ext.tasks import loop
import nest_asyncio
import requests
import logging

# Local imports
import constants
import utils as ut
import voice_manager as vm
import queue_manager as qm

# Configurazione del logging
logging.basicConfig(
    level=logging.INFO,
    format="[{asctime}] [{levelname}] {message}",
    style="{",
    datefmt="%d/%m/%Y %H:%M:%S",
)
logging.getLogger("discord.ext.voice_recv").setLevel(logging.WARNING)
# Silenzia OpusError "corrupted stream" — bug noto di discord-ext-voice-recv
# con il protocollo DAVE E2EE. Non è bloccante ma spamma i log.
logging.getLogger("discord.ext.voice_recv.router").setLevel(logging.ERROR)
logging.getLogger("discord.opus").setLevel(logging.CRITICAL)
nest_asyncio.apply()

# MESSAGE_PERSON_IS_HERE = "è online, se vuoi vai a fargli compagnia... Stronzo."
isOnChannel_users = {
    f"isOnChannel{constants.names_users['alexssio']}": False,
    f"isOnChannel{constants.names_users['BLAcK_Knight']}": False,
    f"isOnChannel{constants.names_users['dark_lord']}": False,
    f"isOnChannel{constants.names_users['burzum']}": False,
}
isOn_Users = {
    f"isOn{constants.names_users['alexssio']}": False,
    f"isOn{constants.names_users['BLAcK_Knight']}": False,
    f"isOn{constants.names_users['dark_lord']}": False,
    f"isOn{constants.names_users['burzum']}": False,
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
loop_task_audio = None

# Soglia temporale: 6 ore prima di poter inviare nuovamente la notifica per lo stesso utente
NOTIFICATION_THRESHOLD = datetime.timedelta(hours=6)

# Inizializzazione bot Discord
intents = discord.Intents.all()
intents.voice_states = True
intents.message_content = True
intents.guilds = True
intents.members = True
intents.presences = True
intents.voice_states = True
botDiscord = commands.Bot(command_prefix="!", intents=intents)
stop_event = asyncio.Event()  # Evento per fermare le operazioni asincrone


@loop(minutes=70)
async def check_online():
    """
    Questo metodo verrà chiamato ogni 70 minuti in loop fino a quando il bot non viene interrotto
    """
    actual_datetime_string = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    guild = botDiscord.get_guild(int(constants.ID_SERVER_DISCORD))
    if guild is None:
        logging.error(
            f"[{actual_datetime_string}] Il server con ID {constants.ID_SERVER_DISCORD} non è stato trovato."
        )
        return

    # Reset temporary online status tracking
    current_online_users = []

    # Itera sui membri del server
    for member in guild.members:
        if member.name in constants.names_users.values():
            if member.bot or member.name == "BOT-ErVongola":  # Ignora i bot
                continue

            username = member.name.lower()
            is_user_active = False

            # Controlla se l'utente è nel canale vocale AFK o STUDIO e imposta lo stato offline
            if member.voice and member.voice.channel:
                if member.voice.channel.id not in (
                    int(constants.chats_database["chat_afk"]),
                    int(constants.chats_database["chat_studio"]),
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
                    logging.debug(
                        f"[{actual_datetime_string}] {member.name} {activity_status}"
                    )

            # Aggiorno lo stato temporaneo per l'utente
            if username in constants.names_users.values():
                user_key = next(
                    (
                        key
                        for key, value in constants.names_users.items()
                        if value == username
                    ),
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
    logging.warning("[BOT] on_disconnect fired — non cancello la queue, reset VC")
    # reset locale dei vc, il player si occuperà di ricrearne uno al bisogno
    await vm.disconnect()
    # non cancellare player_task: lascia che continui a girare e gestisca retry


# Questo metodo viene invocato quando il bot Discord viene avviato e viene inizializzato
@botDiscord.event
async def on_ready():
    """
    Questo metodo viene invocato quando il bot Discord viene avviato e viene inizializzato
    """
    global player_task
    try:
        if not discord.opus.is_loaded():
            logging.info("[BOT] Caricamento manuale di libopus.so.0...")
            discord.opus.load_opus("libopus.so.0")
    except Exception as e:
        logging.warning(f"[BOT] Fallito caricamento manuale Opus: {e}")

    guild = botDiscord.get_guild(int(constants.ID_SERVER_DISCORD))
    if guild:
        try:
            logging.info("[BOT] Pulizia sessione vocale residua all'avvio...")
            await guild.change_voice_state(channel=None)
            await asyncio.sleep(2.0)
            logging.info("[BOT] Sessione vocale residua pulita.")
        except Exception as e:
            logging.warning(f"[BOT] Cleanup sessione vocale fallito (non critico): {e}")

    # Avvia il player task solo se non è già attivo
    if "player_task" not in globals() or player_task is None or player_task.done():
        player_task = asyncio.create_task(ut.audio_player(botDiscord, guild))
        logging.info("[BOT] Audio player task avviato/ripristinato.")
    actual_datetime_string = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    check_online.start()
    logging.info(
        f"[{actual_datetime_string}] Bot Er Vongola avviato con successo! ID: {botDiscord.user.id}"
    )
    logging.info(f"[{actual_datetime_string}] Versione del BOT: 5.0.0")
    try:
        comandiSync = await botDiscord.tree.sync()
        # for guild in botDiscord.guilds:
        #     print(f"Nome del Server: {guild.name}, ID del Server: {guild.id}")
        logging.info(f"Comandi sincronizzati per {botDiscord.user.name}")
        logging.info(f"Comandi sincronizzati: {comandiSync}")
    except discord.Forbidden:
        logging.error(
            f"[{actual_datetime_string}] Errore di autorizzazione durante la sincronizzazione dei comandi."
        )


async def check_and_send_message(member, before, after):
    """Controlla se determinati utenti sono online e manda un messaggio di notifica nel gruppo di Telegram tramite un altro bot"""
    if (
        before.channel is None
        and after.channel is not None
        and member.name != ""
        and member.name is not None
        and member.name in constants.names_users.values()
    ):
        if str(after.channel.id) in (
            constants.chats_database["chat_vocale_privato"],
            constants.chats_database["chat_vocale_privato2"],
            constants.chats_database["chat_vocale_privato3"],
        ):
            now = datetime.datetime.now()
            send_notification = False

            if member.id not in last_notification and member.name in (
                constants.names_users["alexssio"],
                constants.names_users["BLAcK_Knight"],
                constants.names_users["dark_lord"],
            ):
                send_notification = True
            else:
                last_time = last_notification.get(member.id)
                if last_time is None:
                    last_notification[member.id] = now
                elif now - last_time >= NOTIFICATION_THRESHOLD:
                    send_notification = True
            actual_datetime_string = now.strftime("%d/%m/%Y %H:%M:%S")
            if send_notification:
                last_notification[member.id] = now
                # @BradipinoMetallaro64551
                # @Lykanos94
                # @Alexssio
                if member.name in (
                    constants.names_users["alexssio"],
                    constants.names_users["BLAcK_Knight"],
                ):
                    text = f"@BradipinoMetallaro64551 {member.name} è entrato nel canale vocale {after.channel.name}"
                else:
                    text = f"{member.name} è entrato nel canale vocale {after.channel.name}"

                if constants.ENABLE_MESSAGE_TELEGRAM:
                    urlAPITelegram = f"https://api.telegram.org/bot{constants.TELEGRAM_TOKEN}/sendMessage"
                    data_chat_group = {
                        "chat_id": constants.TELEGRAM_GROUP_CHAT_ID,
                        "message_thread_id": constants.TELEGRAM_GROUP_THREAD_ID,
                        "text": text,
                    }
                    try:
                        responseGroup = requests.post(
                            urlAPITelegram, data=data_chat_group
                        )
                        if responseGroup.status_code != 200:
                            logging.error(
                                f"[{actual_datetime_string}] Error sending message to Telegram: {responseGroup}"
                            )
                    except requests.RequestException as e:
                        logging.error(
                            f"[{actual_datetime_string}] Error sending message to Telegram: {e}"
                        )
            elif member.name != "BOT-ErVongola":
                logging.warning(
                    f"[{actual_datetime_string}] Notifica non inviata a {member.name} in questo intervallo di tempo."
                )


@botDiscord.event
async def on_voice_state_update(member, before, after):
    """
    Questo metodo viene invocato ogni volta che c'è un cambio di stato sul member e su quale canale si è spostato
    """
    actual_datetime_string = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    logging.debug(
        f"[{actual_datetime_string}] Canale-p: {before.channel}, Canale-d: {'Nessuno' if after.channel is None else after.channel}, Utente: {member.name}"
    )
    if member.id == botDiscord.user.id:
        global loop_task_audio
        if after.channel and before.channel != after.channel:
            if loop_task_audio and not loop_task_audio.done():
                loop_task_audio.cancel()

            # Attendi un momento per assicurarsi che vc sia pronto
            await asyncio.sleep(1)
        elif after.channel is None and before.channel is not None:
            if loop_task_audio:
                loop_task_audio.cancel()
                loop_task_audio = None
                logging.info("[BOT] Fermato task di ascolto (disconnesso)")

    if member.name in constants.names_users.values() and not member.bot:
        await check_and_send_message(member, before, after)
        if after.channel is None:
            sync_user_status(member, online=False)
        elif after.channel and after.channel.id in (
            int(constants.chats_database["chat_afk"]),
            int(constants.chats_database["chat_studio"]),
        ):
            sync_user_status(member, online=False, voice_state=after)
        elif before.channel != after.channel:
            sync_user_status(member, online=True, voice_state=after)
            # FIX 4017: non triggerare make_audio se il bot sta già connettendosi.
            # Due connect_to_channel concorrenti sullo stesso canale causano
            # un secondo VOICE_SERVER_UPDATE che termina l'handshake in corso.
            if vm.voice_lock.locked():
                logging.warning(
                    f"[BOT] voice_lock occupato — skip make_audio per {member.name}"
                )
            else:
                await ut.make_audio(botDiscord, member, after.channel.id)

        if before.channel and before.channel.id in (
            int(constants.chats_database["chat_afk"]),
            int(constants.chats_database["chat_studio"]),
        ):
            sync_user_status(member, online=False, voice_state=before)

    logging.info(
        f"[{actual_datetime_string}] {len(users_online)} utenti online: {users_online}"
    )


def sync_user_status(member, online=True, voice_state=None):
    """
    Questo metodo sincronizza lo stato dell'utente con la lista degli utenti monitorati
    """
    actual_datetime_string = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    global users_online  # Variabile glo per gli utenti online
    current_online_users = users_online
    username = member.name.lower()

    if username not in constants.names_users.values():
        return  # Non è uno degli utenti monitorati

    # Trova il nome utente corrispondente nel dizionario constants.names_users
    user_key = next(
        (key for key, value in constants.names_users.items() if value == username), None
    )
    if user_key is None:
        return  # Nome utente non trovato

    # Controlla se l'utente è entrato dentro AFK o STUDIO e imposta lo stato offline
    in_excluded_channel = (
        voice_state
        and voice_state.channel
        and voice_state.channel.id
        in (
            int(constants.chats_database["chat_afk"]),
            int(constants.chats_database["chat_studio"]),
        )
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
async def play_queue(vc, interaction: discord.Interaction):
    while qm.audio_queue:
        # Ottieni il prossimo file dalla coda
        current_audio = qm.audio_queue.pop(0)
        audio_path = os.path.join(ut.AUDIO_FOLDER, current_audio)
        try:
            vc.play(
                discord.FFmpegPCMAudio(source=audio_path),
                after=lambda e: (
                    os.remove(audio_path) if os.path.exists(audio_path) else None
                ),
            )
            if not interaction.is_expired():
                await interaction.followup.send(
                    f"Sto riproducendo: `{current_audio}`", ephemeral=True
                )
        except discord.ClientException as e:
            logging.error("Errore di connessione al canale vocale.", exc_info=e)
            if interaction.response.is_done():
                # Se l'interazione è già stata rispinta, invia un messaggio
                await interaction.followup.send(...)


# Comando per riprodurre un file audio dato il suo ID
@botDiscord.tree.command(
    name="play_audio_command",
    description="Riproduce un file audio secondo il suo ID, visualizzabile con `/list_audio_commands`",
)
async def play_audio(interaction: discord.Interaction, audio_id: int):
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

    # Evita duplicati in coda
    if audio_files[audio_id] in qm.audio_queue:
        await interaction.response.send_message(
            f"L'audio `{audio_files[audio_id]}` è già in coda.", ephemeral=True
        )
        return

    # Risposta immediata all'utente
    await interaction.response.send_message(
        "Elaborazione del comando... Attendi un momento.", ephemeral=True
    )
    qm.audio_queue.append({"audio": audio_files[audio_id], "interaction": interaction})
    embed = Embed(
        title="Audio in coda",
        description=f"Aggiunto alla coda: `{audio_files[audio_id]}`. Verrà riprodotto a breve.",
        color=0x00FF00,
    )
    if not interaction.is_expired():
        await interaction.followup.send(embed=embed, ephemeral=True)
    vc = discord.utils.get(botDiscord.voice_clients, guild=interaction.guild)
    try:
        if vc is None or not vc.is_connected():
            vc = await vm.connect_to_channel(voice_channel)
        if not vc.is_playing():
            await play_queue(vc, interaction)

    except discord.errors.ClientException as e:
        logging.error(f"Errore Discord Client: {e}")
        if not interaction.is_expired():
            await interaction.followup.send("Errore Discord Client.", ephemeral=True)
    except Exception as e:
        logging.error(f"Errore generico: {e}")
        if not interaction.is_expired():
            await interaction.followup.send(
                "Si è verificato un errore imprevisto.", ephemeral=True
            )


# @tasks.loop(minutes=2)
# async def keep_voice_alive(botDiscord):
#     for vc in botDiscord.voice_clients:
#         if not vc.is_playing():
#             try:
#                 await asyncio.sleep(5)
#                 logging.debug("Keep-alive: suono silenzioso riprodotto")
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
async def sendmessage_darklord(interaction: discord.Interaction):
    """Manda un messaggio a DarkLord per comunicargli che siamo online..."""
    member_interaction = interaction.user
    dark_Lord = await botDiscord.fetch_user(constants.id_users["dark_lord"])
    if member_interaction.roles != None:
        has_role = any(
            role.id == int(constants.id_roles["corpo_di_ricerca"])
            or role.id == int(constants.id_roles["supremo"])
            for role in member_interaction.roles
        )
        # Controlla se l'utente ha il ruolo richiesto per inviare il messaggio
        if has_role:
            logging.debug(
                f"[{datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')}] Utente {member_interaction.name} ha il ruolo richiesto"
            )
            if interaction.user.name.lower() == "alexssio":
                await dark_Lord.send(
                    f"{member_interaction.name} {MESSAGE_PERSON_IS_HERE}"
                )
                await interaction.response.send_message(
                    "Messaggio inviato!", ephemeral=True
                )
            if interaction.user.name.lower() == "black_knight.94":
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
async def sendmessage_alexssio(interaction: discord.Interaction):
    """Manda un messaggio ad Alexssio e Lykanos per comunicargli che DarkLord è online..."""
    interacted_member = interaction.user
    alexssio = await botDiscord.fetch_user(constants.id_users["alexssio"])
    if interacted_member.roles != None:
        has_role = any(
            role.id == int(constants.id_roles["corpo_di_ricerca"])
            or role.id == int(constants.id_roles["supremo"])
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
async def sendmessage_lykanos(interaction: discord.Interaction):
    """Manda un messaggio a Lykanos per comunicargli che DarkLord è online..."""
    interacted_member = interaction.user
    BLAcK_Knight = await botDiscord.fetch_user(constants.id_users["BLAcK_Knight"])
    if interacted_member.roles != None:
        has_role = any(
            role.id == int(constants.id_roles["corpo_di_ricerca"])
            or role.id == int(constants.id_roles["supremo"])
            for role in interacted_member.roles
        )
        # Controlla se l'utente ha il ruolo richiesto per inviare il messaggio
        if has_role:
            await BLAcK_Knight.send(
                f"{interacted_member.name} {MESSAGE_PERSON_IS_HERE}"
            )
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
    messageToSend = await ut.lancio_bestemmia_commands(
        interaction,
        numerobestemmie,
        constants.chats_database["chat_blasfemie_id_discord"],
        constants.chats_database["chat_testing"],
        constants.id_roles["SNC"],
        constants.id_roles["supremo"],
        botDiscord,
    )
    await interaction.channel.send(messageToSend)
    # if (
    #     str(channel_id)
    #     in [constants.chats_database["chat_blasfemie_id_discord"], constants.chats_database["chat_testing"]]
    #     and int(constants.id_roles["SNC"]) in user_role_ids
    # ) or int(constants.id_roles["supremo"]) in user_role_ids:
    #     if numerobestemmie == "":
    #         numerobestemmie = 1
    #     else:
    #         numerobestemmie = int(numerobestemmie)
    #     await interaction.response.send_message(
    #         f"Sto generando {numerobestemmie} bestemmie, eccole..."
    #     )
    #     with open("json/blasfemia.json", "r", encoding="utf-8") as file:
    #         data = json.load(file)
    #         startCounter = 1
    #         for startCounter in range(int(numerobestemmie)):
    #             custom_message = generatoreblasfemie.GeneratoreBlasfemie(
    #                 data
    #             ).frase_random()
    #             await interaction.channel.send(custom_message)
    #             if (voice_state) and (voice_state.channel):
    #                 await ut.text_to_speech(
    #                     botDiscord,
    #                     custom_message,
    #                     f"bestemmie_{startCounter}",
    #                     voice_state.channel.id,
    #                     qm.audio_queue,
    #                 )
    # else:
    #     await interaction.response.send_message(
    #         "Non sei nel canale giusto oppure non hai il ruolo per poter lanciare questo comando."
    #     )


@botDiscord.tree.command(
    name="add_new_bestemmia",
    description="Aggiunge una nuova bestemmia al database se non esiste già",
)
async def add_bestemmia(interaction: discord.Interaction, testo: str):
    """Aggiunge una nuova bestemmia al file json/blasfemia.json"""
    testo = testo.lower().strip()
    file_path = "json/blasfemia.json"

    try:
        with open(file_path, "r", encoding="utf-8") as file:
            data = json.load(file)

        # Controlla se esiste già
        if any(item["text"].lower() == testo for item in data["bestemmie"]):
            await interaction.response.send_message(
                f"La bestemmia '{testo}' esiste già nel database.", ephemeral=True
            )
            return

        # Aggiungi la nuova bestemmia
        data["bestemmie"].append({"text": testo})

        with open(file_path, "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=4)

        await interaction.response.send_message(
            f"Bestemmia '{testo}' aggiunta con successo!", ephemeral=False
        )

    except Exception as e:
        logging.error(f"Errore aggiunta bestemmia: {e}")
        await interaction.response.send_message(
            f"Si è verificato un errore: {e}", ephemeral=True
        )


@botDiscord.tree.command(
    name="add_benvenuto",
    description="Aggiunge una nuova frase di benvenuto al database se non esiste già",
)
async def add_welcome_phrase(interaction: discord.Interaction, testo: str):
    """Aggiunge una nuova frase di benvenuto al file json/frasieffetto.json"""
    testo = testo.lower().strip()
    file_path = "json/frasieffetto.json"

    try:
        with open(file_path, "r", encoding="utf-8") as file:
            data = json.load(file)

        # Controlla se esiste già
        if any(item["text"].lower() == testo for item in data["frasi"]):
            await interaction.response.send_message(
                f"La frase '{testo}' esiste già nel database.", ephemeral=True
            )
            return

        # Aggiungi la nuova frase
        data["frasi"].append({"text": testo, "users": []})

        with open(file_path, "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=4)

        await interaction.response.send_message(
            f"Frase di benvenuto '{testo}' aggiunta con successo!", ephemeral=False
        )

    except Exception as e:
        logging.error(f"Errore aggiunta frase effetto: {e}")
        await interaction.response.send_message(
            f"Si è verificato un errore: {e}", ephemeral=True
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
    name="read_tech_news",
    description="Entra nel canale vocale dove ti trovi e ti legge 'n' notizie riguardo l'ambito della tecnologia",
)
async def read_tech_news(interaction: discord.Interaction, countnews: int):
    """
    Entra nel canale vocale dove ti trovi e ti legge tot -> 'countnews' notizie riguardo l'ambito della tecnologia
    """

    if countnews == "" or countnews == None:
        countnews = 1

    await interaction.response.send_message(
        f"Ti sto per leggere {countnews} notizie riguardo l'ambito della tecnologia",
        ephemeral=True,
    )
    await ut.prendi_notizia(botDiscord, interaction, countnews, "tecnologia")


@botDiscord.tree.command(
    name="read_neuroscienze_news",
    description="Entra nel canale vocale dove ti trovi e ti legge 'n' notizie riguardo l'ambito delle Neuroscienze",
)
async def read_neuroscienze_news(interaction: discord.Interaction, countnews: int):
    """
    Entra nel canale vocale dove ti trovi e ti legge tot -> 'countnews' notizie riguardo l'ambito delle Neuroscienze
    Le neuroscienze sono l'insieme degli studi scientificamente condotti sul sistema nervoso.
    """

    if countnews == "" or countnews == None:
        countnews = 1

    await interaction.response.send_message(
        f"Ti sto per leggere {countnews} notizie riguardo l'ambito delle Neuroscienze, Le neuroscienze sono l'insieme degli studi scientificamente condotti sul sistema nervoso.",
        ephemeral=True,
    )
    await ut.prendi_notizia(botDiscord, interaction, countnews, "neuroscienze")


@botDiscord.tree.command(
    name="read_ansa_news",
    description="Entra nel canale vocale dove ti trovi e ti legge 'n' notizie prese dal sito ANSA.it",
)
async def read_ansa_news(interaction: discord.Interaction, countnews: int):
    """
    Entra nel canale vocale dove ti trovi e ti legge tot -> 'countnews' notizie prese dal sito ANSA.it
    """

    if countnews == "" or countnews == None:
        countnews = 1

    await interaction.response.send_message(
        f"Ti sto per leggere {countnews} notizie prese dal sito ANSA.it",
        ephemeral=True,
    )
    await ut.prendi_notizia(botDiscord, interaction, countnews, "ansa")


@botDiscord.tree.command(
    name="read_cronaca_news",
    description="Entra nel canale vocale dove ti trovi e ti legge 'n' notizie riguardo l'ambito generale, di cronaca",
)
async def read_cronaca_news(interaction: discord.Interaction, countnews: int):
    """Entra nel canale vocale dove ti trovi e ti legge 'n' notizie riguardo l'ambito generale, di cronaca"""

    if countnews == "" or countnews == None:
        countnews = 1

    await interaction.response.send_message(
        f"Ti sto per leggere {countnews} notizie riguardo l'ambito generale, di cronaca",
        ephemeral=True,
    )
    await ut.prendi_notizia(botDiscord, interaction, countnews, "cronaca")


@botDiscord.tree.command(
    name="read_videogames_news",
    description="Entra nel canale vocale dove ti trovi e ti legge 'n' notizie riguardo l'ambito dei videogames",
)
async def read_videogames_news(interaction: discord.Interaction, countnews: int):
    """Entra nel canale vocale dove ti trovi e ti legge 'n' notizie riguardo l'ambito dei videogames"""

    if countnews == "" or countnews == None:
        countnews = 1

    await interaction.response.send_message(
        f"Ti sto per leggere {countnews} notizie riguardo l'ambito dei videogiochi",
        ephemeral=True,
    )
    await ut.prendi_notizia(botDiscord, interaction, countnews, "videogames")


@botDiscord.tree.command(
    name="read_robotica_news",
    description="Entra nel canale vocale dove ti trovi e ti legge 'n' notizie riguardo l'ambito della robotica",
)
async def read_robotica_news(interaction: discord.Interaction, countnews: int):
    """
    Entra nel canale vocale dove ti trovi e ti legge tot -> 'countnews' notizie riguardo l'ambito della robotica
    """

    if countnews == "" or countnews == None:
        countnews = 1

    await interaction.response.send_message(
        f"Ti sto per leggere {countnews} notizie riguardo l'ambito della robotica",
        ephemeral=True,
    )
    await ut.prendi_notizia(botDiscord, interaction, countnews, "robotica")


@botDiscord.tree.command(
    name="read_fresh_news",
    description="Entra nel canale vocale dove ti trovi e ti legge 'n' notizie generiche uscite poche ore fa",
)
async def read_fresh_news(interaction: discord.Interaction, countnews: int):
    """
    Entra nel canale vocale dove ti trovi e ti legge tot -> 'countnews' notizie generiche uscite poche ore fa
    """

    if countnews == "" or countnews == None:
        countnews = 1

    await interaction.response.send_message(
        f"Ti sto per leggere {countnews} notizie di natura generica uscite recentemente...",
        ephemeral=True,
    )
    await ut.prendi_notizia(botDiscord, interaction, countnews, "titoli")


@botDiscord.tree.command(
    name="read_dal_mondo_news",
    description="Entra nel canale vocale dove ti trovi e ti legge 'n' notizie riguardo tutto il mondo",
)
async def read_dal_mondo_news(interaction: discord.Interaction, countnews: int):
    """
    Entra nel canale vocale dove ti trovi e ti legge tot -> 'countnews' notizie riguardo l'ambito della robotica
    Il ranking di queste notizie è determinato da una serie di fattori, tra cui la pertinenza, l'evidenza, l'autorevolezza,
    l'attualità e l'usabilità dei contenuti, nonché, se consentito dalle tue impostazioni, dai tuoi interessi, che hai specificato
    o che abbiamo dedotto dalla tua attività passata con i prodotti Google, dalla lingua e dalla località.
    Google potrebbe avere un contratto di licenza con alcuni di questi editori, che però non incide sul ranking dei risultati.
    """

    if countnews == "" or countnews == None:
        countnews = 1

    await interaction.response.send_message(
        f"Ti sto per leggere {countnews} notizie riguardo tutto il mondo",
        ephemeral=True,
    )
    await ut.prendi_notizia(botDiscord, interaction, countnews, "dal-mondo")


@botDiscord.tree.command(
    name="read_space_news",
    description="Entra nel canale vocale dove ti trovi e ti legge 'n' notizie riguardo lo Spazio",
)
async def read_space_news(interaction: discord.Interaction, countnews: int):
    """
    Entra nel canale vocale dove ti trovi e ti legge tot -> 'countnews' notizie riguardo l'ambito della Spazio
    """

    if countnews == "" or countnews == None:
        countnews = 1

    await interaction.response.send_message(
        f"Ti sto per leggere {countnews} notizie riguardo l'ambito dello Spazio",
        ephemeral=True,
    )
    await ut.prendi_notizia(botDiscord, interaction, countnews, "spazio")


@botDiscord.tree.command(
    name="read_medicina_news",
    description="Entra nel canale vocale dove ti trovi e ti legge 'n' notizie riguardo la Medicina",
)
async def read_medicina_news(interaction: discord.Interaction, countnews: int):
    """
    Entra nel canale vocale dove ti trovi e ti legge tot -> 'countnews' notizie riguardo l'ambito della Medicina
    """

    if countnews == "" or countnews == None:
        countnews = 1

    await interaction.response.send_message(
        f"Ti sto per leggere {countnews} notizie riguardo l'ambito dello Medicina",
        ephemeral=True,
    )
    await ut.prendi_notizia(botDiscord, interaction, countnews, "medicina")


@botDiscord.tree.command(
    name="freevideogames",
    description="Ti legge l'ultimo gioco gratis del momento su Epic Games Store e/o Steam",
)
async def freevideogames(interaction: discord.Interaction):
    """Entra nel canale vocale dove ti trovi e ti legge i giochi gratuiti del momento su Epic Games Store e/o Steam"""

    channel_free_videogames = botDiscord.get_channel(
        int(constants.chats_database["chat_free_games"])
    )
    await interaction.response.send_message(
        "Ti sto per leggere il nome del gioco gratuito del momento su Epic Games Store e/o Steam",
        ephemeral=True,
    )
    name_videogame_free = await ut.leggi_giochi_gratis(
        interaction, channel_free_videogames
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

    await ut.play_youtube_video(interaction, url, volume)


@botDiscord.tree.command(
    name="stop",
    description="Ferma la riproduzione audio senza disconnettere il bot dal canale vocale",
)
async def stop(interaction: discord.Interaction):
    """Ferma la riproduzione audio senza disconnettere il bot dal canale vocale"""
    await ut.stop_playback(interaction)


@botDiscord.tree.command(
    name="exit",
    description="Disconnette il bot dal canale vocale",
)
async def exit_command(interaction: discord.Interaction):
    """Disconnette il bot dal canale vocale"""
    await ut.disconnect_bot(interaction)


@botDiscord.tree.command(
    name="meteo",
    description="Mostra le previsioni meteo per la città specificata da diverse fonti",
)
async def meteo(interaction: discord.Interaction, citta: str):
    """Mostra le previsioni meteo per la città specificata da diverse fonti"""
    await ut.leggi_meteo(interaction, citta)


@botDiscord.tree.command(
    name="lae",
    description="IN BETA TEST > Il bot inizia ad ascoltarti ed esegue specifici comandi.",
)
async def joinandlisten(interaction: discord.Interaction):
    """Il bot si unisce al canale ed inizia ad ascoltarti eseguendo specifici comandi"""
    voice_state = interaction.user.voice
    if not voice_state or not voice_state.channel:
        await interaction.response.send_message(
            "Devi essere in un canale vocale per usare questo comando.", ephemeral=True
        )
        return

    await interaction.response.send_message(
        "Mi sto connettendo per ascoltarti... Mi troverai in background.",
        ephemeral=True,
    )
    await vm.connect_to_channel(voice_state.channel)
    # Il task di ascolto viene avviato automaticamente in on_voice_state_update


@botDiscord.tree.error
async def on_app_command_error(interaction: discord.Interaction, error):
    logging.error(f"Errore nel comando: {error}")
    if interaction.response.is_done():
        await interaction.followup.send(
            "Si è verificato un errore durante l'esecuzione del comando.",
            ephemeral=True,
        )
    else:
        await interaction.response.send_message(
            "Si è verificato un errore durante l'esecuzione del comando.",
            ephemeral=True,
        )


@check_online.before_loop
async def before_monitor_members():
    logging.info(
        f"[{datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')}] - Avvio del monitoraggio dei membri..."
    )
    await botDiscord.wait_until_ready()


# Esegui il bot Discord e inizializza il monitoraggio degli utenti
users_online = []
botDiscord.run(constants.DISCORD_TOKEN)
