from dotenv import load_dotenv
import os

load_dotenv()


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
    "BLAcK_Knight": "366952021045280779",
    "dark_lord": "271371380467957762",
    "moonpantherredxvi": "399979832038916101",
    "melissa": "293497922870312961",
    "burzum": "303199273418489857",
    "carmineg": "275725325348896769",
}

names_users = {
    "alexssio": "alexssio",
    "BLAcK_Knight": "black_knight.94",
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

ID_SERVER_DISCORD = "679423743017091083"
# id_bot_ervongola = "1205585120187261000"

MESSAGE_PERSON_IS_HERE = "è online, se vuoi vai a fargli compagnia... Stronzo."

keys_question_roma = [
    "As Roma",
    "as roma",
    "partite",
    "partita",
    "biglietti",
    "biglietto",
]
