import discord
from discord.ext import commands
from discord import app_commands
from discord.ext.tasks import loop
from discord.utils import get
from dotenv import load_dotenv
import os
from ollama import Client
import ollama
import json
import streamlit as st
import nest_asyncio
import generatoreblasfemie
import utils as ut
import logging
import voice_manager as vc

# import scraper

nest_asyncio.apply()
load_dotenv()
logging.basicConfig(level=logging.INFO)

# Configurazioni
discord_token = os.getenv("DISCORD_TOKEN")
key_api_personal_ai = os.getenv("KEY_API_PERSONAL_AI")
key_jwt_personal_ai = os.getenv("KEY_JWT_PERSONAL_AI")

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
    "chat_afk": "679436863492194338",
    "chat_studio": "1242219732938264596",
}

id_users = {
    "alexssio": "190745296500686857",
    "lykanos": "366952021045280779",
    "dark_lord": "271371380467957762",
    "blackpanthera666": "399979832038916101",
    "melissa": "293497922870312961",
    "burzum": "303199273418489857",
    "carmineg": "275725325348896769",
}

names_users = {
    "alexssio": "alexssio",
    "lykanos": "lykanos94",
    "dark_lord": "6dark6lord6",
    "blackpanthera666": "blackpanthera666",
    "melissa": "melissa",
    "burzum": "crypo1398",
    "wolfvf": "wolfvf",
    ".carmineg": ".carmineg",
}

id_roles = {"corpo_di_ricerca": "1109819956524224532", "supremo": "679447959309516830"}

# id_server_discord = "679423743017091083"
# id_bot_ervongola = "1205585120187261000"

messageTheyAre = (
    "Lykanos e Alexssio sono online, se vuoi vai a fargli compagnia... Stronzo."
)
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

clientAI = Client(host="http://host.docker.internal:11434/api/generate -d")

# Inizializzazione bot Discord
intents = discord.Intents.all()
intents.message_content = True
intents.guilds = True
intents.members = True
intents.voice_states = True
botDiscord = commands.Bot(command_prefix="!", intents=intents)


# Questo metodo viene invocato quando il bot Discord viene avviato e viene inizializzato
@botDiscord.event
async def on_ready():
    """
    Questo metodo viene invocato quando il bot Discord viene avviato e viene inizializzato
    """
    botDiscord.loop.create_task(ut.audio_player())
    print(f"Logged in as {botDiscord.user.name} ({botDiscord.user.id})", flush=True)
    check_online.start()
    try:
        await botDiscord.tree.sync()
        print("Synced")
    except discord.Forbidden:
        print("Unexpected forbidden from application scope.")


# Questo metodo verrà chiamato ogni 70 minuti in loop fino a quando il bot non viene interrotto
@loop(minutes=70)
async def check_online():
    """
    Questo metodo verrà chiamato ogni 70 minuti in loop fino a quando il bot non viene interrotto
    """

    dark_Lord = await botDiscord.fetch_user(id_users["dark_lord"])
    alexssio = await botDiscord.fetch_user(id_users["alexssio"])
    if (
        isOnChannel_users[f"isOnChannel{names_users['alexssio']}"]
        and isOnChannel_users[f"isOnChannel{names_users['lykanos']}"]
        and isOn_Users[f"isOn{names_users['alexssio']}"]
        and isOn_Users[f"isOn{names_users['lykanos']}"]
        and not isOn_Users[f"isOn{names_users['dark_lord']}"]
    ):
        await dark_Lord.send(messageTheyAre)
        await alexssio.send(messageTheyAre)

    # print(f"{len(users_online)} utenti online: {users_online}", flush=True)


@botDiscord.event
async def on_voice_state_update(member, before, after):
    """
    Questo metodo viene invocato ogni volta che c'è un cambio di stato sul member e su quale canale si è spostato
    """
    print(
        f"Canale prima: {before.channel}, Canale dopo: {after.channel}, Utente: {member.name}",
        flush=True,
    )
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


def check_user_online(username, status):
    """
    Questo metodo controlla se l'utente è online o no
    """

    global users_online
    if status == "offline":
        for user in users_online:
            # Se l'utente non è online, rimuovi l'utente dalla lista
            users_online.pop(users_online.index(user))
            return

    # Se la lista degli utenti online è vuota, aggiungi il primo utente
    if len(users_online) == 0:
        users_online.append(username)
        update_user_status(username, status)
        return
    # Se l'utente è già nella lista, aggiorna lo status
    if username in users_online:
        update_user_status(username, status)
    else:
        # Se l'utente non è nella lista, aggiungilo
        users_online.append(username)
        update_user_status(username, status)


def update_user_status(username, status):
    """Aggiorna gli stati in base allo status"""

    if username == names_users["alexssio"]:
        isOnChannel_users[f"isOn{names_users['alexssio']}"] = status == "online"
    elif username == names_users["lykanos"]:
        isOnChannel_users[f"isOn{names_users['lykanos']}"] = status == "online"
    elif username == names_users["dark_lord"]:
        isOnChannel_users[f"isOn{names_users['dark_lord']}"] = status == "online"


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
    name="avvisadarklord",
    description="Manda un messaggio a DarkLord per comunicargli che siamo online...",
)
async def sendmessage_darklord(interaction: discord.Interaction):
    """Manda un messaggio a DarkLord per comunicargli che siamo online..."""
    member = interaction.user
    has_role = any(
        role.id == int(id_roles["corpo_di_ricerca"])
        or role.id == int(id_roles["supremo"])
        for role in member.roles
    )
    if has_role:
        dark_Lord = await botDiscord.fetch_user(id_users["dark_lord"])
        alexssio = await botDiscord.fetch_user(id_users["alexssio"])
        await dark_Lord.send(messageTheyAre)
        await alexssio.send(messageTheyAre)
        await interaction.response.send_message("Messaggio inviato!")
    else:
        await interaction.response.send_message(
            "Non hai il ruolo richiesto per inviare il messaggio"
        )


# Funzione per generare casualmente una bestemmia scrivendola in chat e creando un file audio che riprodurrà immediatamente tramite il metodo text_to_speech
@botDiscord.tree.command(
    name="bestemmia",
    description="Il Bot Er Vongola entrerà nel canale vocale e invierà un tot bestemmie",
)
async def bestemmia(interaction: discord.Interaction, numerobestemmie: str):
    """Il Bot Er Vongola entrerà nel canale vocale e invierà un tot bestemmie"""

    user = interaction.user
    voice_state = user.voice
    if numerobestemmie == "":
        numerobestemmie = 1
    else:
        numerobestemmie = int(numerobestemmie)
    await interaction.response.send_message(
        f"Sto generando {numerobestemmie} bestemmie, eccole..."
    )
    with open("blasfemia.json", "r", encoding="utf-8") as file:
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
        await messageTheyAre.reply(
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
        await messageTheyAre.reply(
            f"Si è verificato un errore durante l'elaborazione della richiesta. {e}"
        )


@botDiscord.tree.command(
    name="newstech",
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
    name="newsgeneral",
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
    name="newsvideogames",
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
    name="suggerimento", description="Invia un suggerimento per una nuova funzione"
)
async def suggerimento(interaction: discord.Interaction, testo: str):
    """Invia un suggerimento per una nuova funzione per il bot"""

    with open("suggerimenti.txt", "a") as file:
        file.write(f"{interaction.user}: {testo}\n")
    await interaction.response.send_message("Grazie per il tuo suggerimento!")


@botDiscord.tree.command(
    name="playmusic",
    description="Riproduce audio da YouTube nel canale vocale con un volume di default di 100% o volume impostato",
)
async def play_music(interaction: discord.Interaction, url: str, volume: int = 100):
    """Riproduce audio da YouTube nel canale vocale con un volume di default di 100% o volume impostato"""

    await ut.play_music(interaction, url, volume)


@botDiscord.tree.command(
    name="stop",
    description="Ferma la riproduzione audio e disconnette il bot dal canale vocale",
)
async def stop(interaction: discord.Interaction):
    """Ferma la riproduzione audio e disconnette il bot dal canale vocale"""

    await ut.stop(interaction)


@check_online.before_loop
async def before_monitor_members():
    print("Avvio del monitoraggio dei membri...")
    await botDiscord.wait_until_ready()


# Esegui il bot Discord
users_online = []
botDiscord.run(discord_token)
