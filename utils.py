import asyncio
from gtts import gTTS
import json
import discord
import frasiconteggio
import os

audio_queue = asyncio.Queue()  # Coda per le richieste audio

chat_vocale_privato = "707198443751211140"
chat_vocale_privato2 = "707514058990944256"
chat_vocale_privato3 = "783252026766131222"
id_melissa = "293497922870312961"
id_black_panthera = "399979832038916101"
id_burzum = "303199273418489857"

class Utils:
    def __init__(self, bot):
        self.bot = bot

    async def text_to_speech(self, custom_message, another_text_message, channelId):
        channelPrivato = self.bot.get_channel(int(chat_vocale_privato))
        fromChannel = self.bot.get_channel(channelId)
        # Genero il file audio contenente la frase costruita precedentemente
        tts = gTTS(custom_message, lang="it")
        # Salvo il file audio con il nome del membro associato
        tts.save(f"welcome_message_{another_text_message}.mp3")
        print(f"Message/command received by channel: {fromChannel}", flush=True)
        try:
            if not(fromChannel and isinstance(fromChannel, discord.VoiceChannel)):
                print("Connecting to voice channel...", flush=True)
                await audio_queue.put((channelPrivato, f"welcome_message_{another_text_message}.mp3"))
            else:
                print("Connecting to voice channel...", flush=True)
                await audio_queue.put((fromChannel, f"welcome_message_{another_text_message}.mp3"))
        except Exception as e:
            print(f"Error: {e}", flush=True)

    async def make_audio(self, member, channelKey):
        # Apro la comunicazione con il file JSON per ottenermi la lista delle frasi
        with open("frasieffetto.json", "r") as file:
            data = json.load(file)
        frasi = frasiconteggio.FrasiConteggio(data)
        # Ottengo il canale tramite il channelKey
        channel = self.bot.get_channel(int(channelKey))
        # Controllo se l'utente è entrato in quel determinato canale
        if str(channel.id) in [
            chat_vocale_privato,
            chat_vocale_privato2,
            chat_vocale_privato3,
        ]:
            # Genero una frase casuale tramite il metodo frase_random della classe FrasiConteggio
            frasedeffetto = frasi.frase_random(member.name)
            if str(member.id) == id_burzum:
                custom_message = f"Burzum {frasedeffetto}"
            elif str(member.id) == id_black_panthera:
                custom_message = f"Pantera {frasedeffetto}"
            elif str(member.id) == id_melissa:
                custom_message = f"Melissa {frasedeffetto}"
            else:
                custom_message = f"{member.name} {frasedeffetto}"

            await self.text_to_speech(custom_message, member.name, channel.id)


    # Questo metodo connette il bot al canale vocale se il canale non è vuoto e riproduce il file audio, 
    # rimane in attesa 3 secondi per permettere di aggiungersi altri file in coda da riprodurre successivamente
    async def audio_player(self):
        while True:
            channel, file_name = await audio_queue.get()
            try:
                vc = await channel.connect()
                #elif vc.channel.id != channel.id:
                #   await vc.move_to(channel)
                vc.play(discord.FFmpegPCMAudio(file_name))
                while vc.is_playing():
                    await asyncio.sleep(4)
                os.remove(file_name)
                if vc and vc.is_connected():
                    await vc.disconnect()
                audio_queue.task_done()
            except Exception as e:
                print(f"Error: {e}", flush=True)