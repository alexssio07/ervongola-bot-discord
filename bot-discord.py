import asyncio
import datetime
import discord
from discord.ext import commands
from discord.ext.commands import Context
from discord import ActivityType, CustomActivity, Game, Streaming, Spotify
from discord.ext.tasks import loop
from dotenv import load_dotenv
import os
from ollama import Client
import ollama
import json
import nest_asyncio
import requests
import generatoreblasfemie
import utils as ut

# import scraper

nest_asyncio.apply()
load_dotenv()

# Configurazioni
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
KEY_API_PERSONAL_AI = os.getenv("KEY_API_PERSONAL_AI")
KEY_JWT_PERSONAL_AI = os.getenv("KEY_JWT_PERSONAL_AI")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
TELEGRAM_GROUP_CHAT_ID = os.getenv("TELEGRAM_GROUP_CHAT_ID")

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
    "wolfvf": "wolfvf",
    ".carmineg": ".carmineg",
}

id_roles = {
    "corpo_di_ricerca": "1109819956524224532",
    "supremo": "679447959309516830",
    "SNC": "1256877870798602261",
}

id_server_discord = "679423743017091083"
# id_bot_ervongola = "1205585120187261000"

messagePersonIsHere = "è online, se vuoi vai a fargli compagnia... Stronzo."
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

keysQuestionRoma = [
    "As Roma",
    "as roma",
    "partite",
    "partita",
    "biglietti",
    "biglietto",
]
users_online = []
audio_queue = []
last_notification = {}

# Soglia temporale: 6 ore prima di poter inviare nuovamente la notifica per lo stesso utente
NOTIFICATION_THRESHOLD = datetime.timedelta(hours=6)

clientAI = Client(host="http://host.docker.internal:11434/api/generate -d")

# Inizializzazione bot Discord
intents = discord.Intents.all()
intents.message_content = True
intents.guilds = True
intents.members = True
intents.presences = True
intents.voice_states = True
botDiscord = commands.Bot(command_prefix="!", intents=intents)


# Questo metodo viene invocato quando il bot Discord viene avviato e viene inizializzato
@botDiscord.event
async def on_ready():
    """
    Questo metodo viene invocato quando il bot Discord viene avviato e viene inizializzato
    """
    botDiscord.loop.create_task(ut.audio_player())
    print(f"Logged in as {botDiscord.user.name} - Ready", flush=True)
    check_online.start()
    try:
        await botDiscord.tree.sync()
        # for guild in botDiscord.guilds:
        #     print(f"Nome del Server: {guild.name}, ID del Server: {guild.id}")
        print(f"Commands synced for {botDiscord.user.name}")
    except discord.Forbidden:
        print("Unexpected forbidden from application scope.")


# Questo metodo verrà chiamato ogni 70 minuti in loop fino a quando il bot non viene interrotto
@loop(minutes=70)
async def check_online():
    """
    Questo metodo verrà chiamato ogni 70 minuti in loop fino a quando il bot non viene interrotto
    """
    # if id_users["alexssio"] in last_notification:
    #     await sendmessage_alexssio()
    # if (
    #     isOnChannel_users[f"isOnChannel{names_users['lykanos']}"]
    #     and isOn_Users[f"isOn{names_users['lykanos']}"]
    #     and not isOn_Users[f"isOn{names_users['dark_lord']}"]
    # ):
    #     await sendmessage_lykanos()

    guild = botDiscord.get_guild(int(id_server_discord))
    if guild is None:
        print(f"Il server con ID {id_server_discord} non è stato trovato.")
        return

    # Itera sui membri del server
    for member in guild.members:
        if member.bot:  # Ignora i bot
            continue

        # Itera sulle attività dell'utente
        for activity in member.activities:
            # print(member.activities)
            if isinstance(activity, Game) or activity.type == ActivityType.playing:
                print(f"{member.name} sta giocando a {activity.name}")
            if (
                isinstance(activity, Streaming)
                or activity.type == ActivityType.streaming
            ):
                print(
                    f"{member.name} sta facendo streaming di {activity.name} su {activity.platform}"
                )
            if isinstance(activity, Spotify) or activity.type == ActivityType.listening:
                print(
                    f"{member.name} sta ascoltando {activity.title} di {activity.artist}"
                )
            if (
                isinstance(activity, CustomActivity)
                or activity.type == ActivityType.custom
            ):
                print(f"{member.name} sta facendo {activity.name} su qualcosa...")

    print("Controllo delle attività completato.")

    print(f"{len(users_online)} utenti online: {users_online}", flush=True)


async def check_and_send_message(member, before, after):
    if before.channel is None and after.channel is not None:
        if str(after.channel.id) in (
            chats_database["chat_vocale_privato"],
            chats_database["chat_vocale_privato2"],
            chats_database["chat_vocale_privato3"],
        ):
            now = datetime.datetime.now()
            send_notification = False

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

            if send_notification:
                last_notification[member.id] = now
                # @BradipinoMetallaro64551
                # @Lykanos94
                # @Alexssio
                nomeUtente = [
                    value for key, value in names_users.items() if value == member.name
                ]
                text = f"{nomeUtente} è entrato nel canale vocale {after.channel.name}"
                urlAPITelegram = (
                    f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
                )
                data_chat_private = {
                    "chat_id": TELEGRAM_CHAT_ID,
                    "text": text,
                }
                data_chat_group = {
                    "chat_id": TELEGRAM_GROUP_CHAT_ID,
                    "text": text,
                }
                try:
                    response = requests.post(urlAPITelegram, data=data_chat_private)
                    responseGroup = requests.post(urlAPITelegram, data=data_chat_group)
                    if response.status_code != 200:
                        print("Error sending message to Telegram", response.text)
                    if responseGroup.status_code != 200:
                        print("Error sending message to Telegram", responseGroup.text)
                except Exception as e:
                    print("Error sending message to Telegram", e)
            elif member.name != "BOT-ErVongola":
                print(
                    f"Notifica già inviata a {member.name} in questo intervallo di tempo."
                )


@botDiscord.event
async def on_voice_state_update(member, before, after):
    """
    Questo metodo viene invocato ogni volta che c'è un cambio di stato sul member e su quale canale si è spostato
    """
    print(
        f"Canale prima: {before.channel}, Canale dopo: {after.channel}, Utente: {member.name}",
        flush=True,
    )
    await check_and_send_message(member, before, after)
    if member.name in names_users.values():
        if before.channel and before.channel.id in (
            int(chats_database["chat_afk"]),
            int(chats_database["chat_studio"]),
        ):
            sync_user_status(member, online=False)

        if after.channel and after.channel.id in (
            int(chats_database["chat_afk"]),
            int(chats_database["chat_studio"]),
        ):
            sync_user_status(member, online=False)

        if after.channel is None:
            sync_user_status(member, online=False)

        if (
            after.channel
            and after.channel is not None
            and after.channel.id
            not in (int(chats_database["chat_afk"]), int(chats_database["chat_studio"]))
            and before.channel != after.channel
        ):
            sync_user_status(member, online=True)
            await ut.make_audio(botDiscord, member, after.channel.id)

    print(f"{len(users_online)} utenti online: {users_online}", flush=True)


def sync_user_status(member, online=True):
    """
    Questo metodo sincronizza lo stato dell'utente con la lista degli utenti monitorati
    """

    global users_online

    username = member.name.lower()

    if username not in names_users.values():
        return  # Non è uno degli utenti monitorati

    user_key = next(
        (key for key, value in names_users.items() if value == username), None
    )
    if user_key is None:
        return  # Nome utente non trovato

    # Aggiorna lo stato dell'utente
    if f"isOn{user_key}" in isOn_Users:
        if online:
            isOn_Users[f"isOn{user_key}"] = True
            if username not in users_online:
                users_online.append(username)
            else:
                users_online[users_online.index(username)] = username
        else:
            isOn_Users[f"isOn{user_key}"] = False
            if username in users_online:
                users_online.remove(username)


# Comando per mostrare la lista dei file audio
@botDiscord.tree.command(
    name="list_audio_commands",
    description="Mostra la lista dei comandi vocali disponibili",
)
async def list_audio(interaction: discord.Interaction):
    audio_files = ut.get_command_audio_files()
    if not audio_files:
        await interaction.response.send_message(
            "Nessun file audio disponibile.", ephemeral=True
        )
        return

    audio_list = "\n".join([f"{id}: {name}" for id, name in audio_files.items()])
    await interaction.response.send_message(
        f"Ecco la lista dei file audio:\n```\n{audio_list}\n``` Scrivi /play_audio_command e il numero dell'audio per riprodurlo.",
    )


# Funzione per gestire la riproduzione della coda
async def play_queue(vc, interaction: discord.Interaction):
    global audio_queue
    while audio_queue:
        # Ottieni il prossimo file dalla coda
        current_audio = audio_queue.pop(0)
        audio_path = os.path.join(ut.AUDIO_FOLDER, current_audio)
        vc.play(
            discord.FFmpegPCMAudio(source=audio_path),
            after=lambda e: print(f"Riproduzione terminata: {e}"),
        )

        await interaction.followup.send(
            f"Sto riproducendo: `{current_audio}`", ephemeral=True
        )


# Comando per riprodurre un file audio dato il suo ID
@botDiscord.tree.command(
    name="play_audio_command",
    description="Riproduce un file audio secondo il suo ID, visualizzabile con `/list_audio_commands`",
)
async def play_audio(interaction: discord.Interaction, audio_id: int):
    global audio_queue
    audio_files = ut.get_command_audio_files()

    if audio_id not in audio_files:
        await interaction.response.send_message(
            "ID audio non valido. Usa `!list_audio_commands` per vedere gli ID disponibili.",
            ephemeral=True,
        )
        return

    # Controlla se l'utente è in un canale vocale
    if not interaction.user.voice or not interaction.user.voice.channel:
        await interaction.response.send_message(
            "Devi essere in un canale vocale per usare questo comando.", ephemeral=True
        )
        return

    # Risposta immediata all'utente
    await interaction.response.send_message(
        "Elaborazione del comando... Attendi un momento.", ephemeral=True
    )
    # Aggiungi il file alla coda
    audio_queue.append(audio_files[audio_id])

    # Connettiti al canale vocale se non sei già connesso
    voice_channel = interaction.user.voice.channel
    vc = discord.utils.get(botDiscord.voice_clients, guild=interaction.guild)

    if not vc:
        vc = await voice_channel.connect()

        # Avvia la riproduzione della coda
        await play_queue(vc, interaction)
    elif not vc.is_playing():
        # Se il bot è già nel canale ma inattivo, avvia la coda
        await play_queue(vc, interaction)
    elif vc.is_playing():
        # Notifica che è stato aggiunto alla coda
        await interaction.followup.send(
            f"Aggiunto alla coda: `{audio_files[audio_id]}`. Verrà riprodotto a breve.",
            ephemeral=True,
        )


# Questo metodo cattura i messaggi testuali
# @botDiscord.event
# async def on_message(message):
#     if message.author.bot:
#         return
#     message_user = str(message.content)
#     for value in keysQuestionRoma:
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
#             response = clientAI.chat(
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
        f"Sono un'assistente virtuale chiamato Er Vongola, super potente e cazzuto in grado di annunciare l'entrata di alcuni specifici utenti che lo desiderano, quando entrano in determinati canali vocali."
    )
    await interaction.channel.send(
        f"Può assistervi come farebbe una vera intelligenza artificiale attraverso la chat testuale 'parla-con-l-ia' o attraverso la sua chat privata."
    )
    await interaction.channel.send(
        f"Scrivi / in una delle chat testuali a disposizione per visualizzare la lista dei comandi disponibili."
    )


@botDiscord.tree.command(
    name="avvisa_darklord",
    description="Manda un messaggio a DarkLord per comunicargli che siamo online... Comando PRIVATO",
)
async def sendmessage_darklord(interaction: discord.Interaction):
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
            print(f"Utente {member_interaction.name} ha il ruolo richiesto")
            if interaction.user.name.lower() == "alexssio":
                await dark_Lord.send(f"{member_interaction.name} {messagePersonIsHere}")
                await interaction.response.send_message(
                    "Messaggio inviato!", ephemeral=True
                )
            if interaction.user.name.lower() == "lykanos94":
                await dark_Lord.send(f"{member_interaction.name} {messagePersonIsHere}")
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
    alexssio = await botDiscord.fetch_user(id_users["alexssio"])
    if interacted_member.roles != None:
        has_role = any(
            role.id == int(id_roles["corpo_di_ricerca"])
            or role.id == int(id_roles["supremo"])
            for role in interacted_member.roles
        )
        # Controlla se l'utente ha il ruolo richiesto per inviare il messaggio

        if has_role:
            await alexssio.send(f"{interacted_member.name} {messagePersonIsHere}")
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
    lykanos = await botDiscord.fetch_user(id_users["lykanos"])
    if interacted_member.roles != None:
        has_role = any(
            role.id == int(id_roles["corpo_di_ricerca"])
            or role.id == int(id_roles["supremo"])
            for role in interacted_member.roles
        )
        # Controlla se l'utente ha il ruolo richiesto per inviare il messaggio
        if has_role:
            await lykanos.send(f"{interacted_member.name} {messagePersonIsHere}")
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
                        botDiscord,
                        custom_message,
                        f"bestemmie_{startCounter}",
                        voice_state.channel.id,
                    )
    else:
        await interaction.response.send_message(
            "Non sei nel canale giusto oppure non hai il ruolo per poter lanciare questo comando."
        )


@botDiscord.tree.command(name="barzelletta", description="Genera una barzelletta")
async def barzeletta(interaction: discord.Interaction):
    """Genera una barzelletta, entra nel canale vocale e la riproduce"""

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
        if interaction.channel != None:
            await ut.text_to_speech(
                botDiscord, responseFormatted, "barzeletta", interaction.channel.id
            )
        else:
            await interaction.response.send_message(
                f"Non posso leggerti la barzeletta perché non sei connesso a nessun canale vocale.",
                ephemeral=True,
            )
    except ollama.ResponseError as e:
        print(e, flush=True)
        await interaction.response.send_message(
            f"Si è verificato un errore durante l'elaborazione della richiesta. {e}"
        )


@botDiscord.tree.command(name="freddura", description="Genera una freddura/battuta")
async def freddura(interaction: discord.Interaction):
    """
    Genera una freddura/battuta, entra nel canale vocale e la riproduce
    """

    try:
        await interaction.response.send_message(
            f"Sto generando una freddura, eccola..."
        )
        response = clientAI.chat(
            model="gemma2",
            messages=[
                {
                    "role": "user",
                    "content": "raccontami una freddura divertente o squallida oppure una battuta",
                },
            ],
        )
        responseFormatted = response["message"]["content"]
        await interaction.channel.send(content=responseFormatted[:1999])
        if len(responseFormatted) >= 1999:
            for i in range(0, 1999, 1999):
                await interaction.channel.send(content=responseFormatted[i : i + 1999])
        print(responseFormatted, flush=True)
        if (interaction.channel) != None:
            await ut.text_to_speech(
                botDiscord, responseFormatted, "freddura", interaction.channel.id
            )
        else:
            await interaction.response.send_message(
                f"Non posso leggerti la freddura perché non sei connesso a nessun canale vocale.",
                ephemeral=True,
            )
    except ollama.ResponseError as e:
        print(e, flush=True)


@botDiscord.tree.command(
    name="read_news_tech",
    description="Entra nel canale vocale dove ti trovi e ti legge 'n' notizie riguardo l'ambito della tecnologia",
)
async def newstech(interaction: discord.Interaction, countnews: str):
    """
    Entra nel canale vocale dove ti trovi e ti legge tot -> 'countnews' notizie riguardo l'ambito della tecnologia
    """

    if countnews == "":
        countnews = 1
    else:
        countnews = int(countnews)

    channel_news_tech = botDiscord.get_channel(int(chats_database["chat_news_tech"]))
    if (channel_news_tech) != None:
        await interaction.response.send_message(
            f"Ti sto per leggere {countnews} notizie riguardo l'ambito della tecnologia",
            ephemeral=True,
        )
        await ut.leggi_notizie(botDiscord, interaction, countnews, channel_news_tech)
    else:
        await interaction.response.send_message(
            f"Non posso leggerti la notizia perché non sei connesso a nessun canale vocale.",
            ephemeral=True,
        )


@botDiscord.tree.command(
    name="read_news_general",
    description="Entra nel canale vocale dove ti trovi e ti legge 'n' notizie riguardo l'ambito generale",
)
async def newsgeneral(interaction: discord.Interaction, countnews: str):
    """Entra nel canale vocale dove ti trovi e ti legge 'n' notizie riguardo l'ambito generale"""

    if countnews == "":
        countnews = 1
    else:
        countnews = int(countnews)

    channel_news_general = botDiscord.get_channel(
        int(chats_database["chat_news_general"])
    )
    if (channel_news_general) != None:
        await interaction.response.send_message(
            f"Ti sto per leggere {countnews} notizie riguardo l'ambito generale, di cronaca",
            ephemeral=True,
        )
        await ut.leggi_notizie(botDiscord, interaction, countnews, channel_news_general)
    else:
        await interaction.response.send_message(
            f"Non posso leggerti la notizia perché non sei connesso a nessun canale vocale.",
            ephemeral=True,
        )


@botDiscord.tree.command(
    name="read_news_videogames",
    description="Entra nel canale vocale dove ti trovi e ti legge 'n' notizie riguardo l'ambito dei videogames",
)
async def newsvideogames(interaction: discord.Interaction, countnews: str):
    """Entra nel canale vocale dove ti trovi e ti legge 'n' notizie riguardo l'ambito dei videogames"""

    if countnews == "":
        countnews = 1
    else:
        countnews = int(countnews)

    channel_news_videogames = botDiscord.get_channel(
        int(chats_database["chat_news_videogames"])
    )
    if (channel_news_videogames) != None:
        await interaction.response.send_message(
            f"Ti sto per leggere {countnews} notizie riguardo l'ambito dei videogiochi",
            ephemeral=True,
        )
        await ut.leggi_notizie(
            botDiscord, interaction, countnews, channel_news_videogames
        )
    else:
        await interaction.response.send_message(
            f"Non posso leggerti la notizia perché non sei connesso a nessun canale vocale.",
            ephemeral=True,
        )


@botDiscord.tree.command(
    name="freevideogames",
    description="Ti legge l'ultimo gioco gratis del momento su Epic Games Store e/o Steam",
)
async def freevideogames(interaction: discord.Interaction):
    """Entra nel canale vocale dove ti trovi e ti legge i giochi gratuiti del momento su Epic Games Store e/o Steam"""

    channel_free_videogames = botDiscord.get_channel(
        int(chats_database["chat_free_games"])
    )
    if (channel_free_videogames) != None:
        await interaction.response.send_message(
            f"Ti sto per leggere il nome del gioco gratuito del momento su Epic Games Store e/o Steam",
            ephemeral=True,
        )
        name_videogame_free = await ut.leggi_giochi_gratis(
            botDiscord, interaction, channel_free_videogames
        )
        if name_videogame_free != "" and name_videogame_free != None:
            await interaction.channel.send(
                f"Al momento è disponibile {name_videogame_free}"
            )
    else:
        await interaction.response.send_message(
            f"Non posso leggerti la notizia perché non sei connesso a nessun canale vocale.",
            ephemeral=True,
        )


@botDiscord.tree.command(
    name="suggerimento", description="Invia un suggerimento per una nuova funzione"
)
async def suggerimento(interaction: discord.Interaction, testo: str):
    """Invia un suggerimento per una nuova funzione per il bot"""

    with open("app/outfiles/suggerimenti.txt", "a") as file:
        file.write(f"{interaction.user}: {testo}\n")
    await interaction.response.send_message("Grazie per il tuo suggerimento!")


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
    description="Ferma la riproduzione audio e disconnette il bot dal canale vocale",
)
async def stop(interaction: discord.Interaction):
    """Ferma la riproduzione audio e disconnette il bot dal canale vocale"""

    await ut.stop(interaction)


@botDiscord.tree.command(
    name="lae",
    description="IN BETA TEST > Il bot inizia ad ascoltarti ed esegue specifici comandi, POTREBBE NON FUNZIONARE.",
)
async def joinandlisten(interaction: discord.Interaction):
    """Il bot si unisce al canale ed inizia ad ascoltarti eseguendo specifici comandi"""
    # TO DO DA FARE
    # await ut.join_and_listen(interaction)


@check_online.before_loop
async def before_monitor_members():
    print("Avvio del monitoraggio dei membri...")
    await botDiscord.wait_until_ready()


# Esegui il bot Discord e inizializza il monitoraggio degli utenti
users_online = []
botDiscord.run(DISCORD_TOKEN)
