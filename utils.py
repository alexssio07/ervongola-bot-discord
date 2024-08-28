import re
import asyncio
from gtts import gTTS
import json
import discord
import frasiconteggio
import os
import uuid
import yt_dlp as youtube_dl

audio_queue = asyncio.Queue()  # Coda per le richieste audio

chat_vocale_privato = "707198443751211140"
chat_vocale_privato2 = "707514058990944256"
chat_vocale_privato3 = "783252026766131222"
chats = ["chat_vocale_privato", "chat_vocale_privato2", "chat_vocale_privato3"]
id_users = {
    "alexssio": "190745296500686857",
    "lykanos": "366952021045280779",
    "dark_lord": "271371380467957762",
    "blackpanthera666": "271371380467957762",
    "melissa": "293497922870312961",
    "burzum": "303199273418489857",
    "carmineg": "275725325348896769",
}

id_jordan = "379228448138461186"
current_vc = None


class Utils:
    def __init__(self, bot):
        self.bot = bot

    async def text_to_speech(self, custom_message, another_text_message, channelId):
        channelPrivato = self.bot.get_channel(int(chat_vocale_privato))
        fromChannel = self.bot.get_channel(channelId)
        # Genero il file audio contenente la frase costruita precedentemente
        tts = gTTS(custom_message, lang="it")
        # Salvo il file audio con il nome del membro associato
        tts.save(f"audio_{another_text_message}.mp3")
        print(f"Message/command received by channel: {fromChannel}", flush=True)
        try:
            if not (fromChannel and isinstance(fromChannel, discord.VoiceChannel)):
                print("Connecting to voice channel...", flush=True)
                await audio_queue.put(
                    (channelPrivato, f"audio_{another_text_message}.mp3")
                )
            else:
                print("Connecting to voice channel...", flush=True)
                await audio_queue.put(
                    (fromChannel, f"audio_{another_text_message}.mp3")
                )
        except Exception as e:
            print(f"Error: {e}", flush=True)

    async def make_audio(self, member, channelKey):
        # Apro la comunicazione con il file JSON per ottenermi la lista delle frasi
        with open("frasieffetto.json", "r", encoding="utf-8") as file:
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
            if str(member.id) == id_users["id_burzum"]:
                custom_message = f"Burzum {frasedeffetto}"
            elif str(member.id) == id_users["blackpanthera666"]:
                custom_message = f"Pantera {frasedeffetto}"
            elif str(member.id) == id_users["melissa"]:
                custom_message = f"Melissa {frasedeffetto}"
            elif str(member.id) == id_users["alexssio"]:
                custom_message = f"Alexssìo {frasedeffetto}"
            elif str(member.id) == id_users["carmineg"]:
                custom_message = f"Carmine {frasedeffetto}"
            else:
                custom_message = f"{member.name} {frasedeffetto}"

            await self.text_to_speech(
                custom_message,
                f"welcome_message_{member.name}_{str(uuid.uuid4())}",
                channel.id,
            )

    async def play_music(self, interaction: discord.Interaction, url: str, volume: int):
        global current_vc
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
        if current_vc:
            if current_vc.channel == channel:
                current_vc.stop()
            else:
                await current_vc.disconnect()
                current_vc = await channel.connect()
        else:
            current_vc = await channel.connect()

        def download_complete(d):
            if d["status"] == "finished":
                print(f"Download completato: {d['filename']}")
                asyncio.run_coroutine_threadsafe(
                    interaction.response.send_message(
                        f"Download completato: {d['filename']}"
                    )
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
                    "preferredquality": "192",
                }
            ],
        }

        await interaction.response.defer()

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
        current_vc.play(
            discord.FFmpegPCMAudio(file, options=ffmpeg_options), after=after_playing
        )
        await interaction.followup.send(
            f"Inizio a riprodurre l'audio {title} con link {url} con volume al {volume}%"
        )

    async def stop(self, interaction: discord.Interaction):
        global current_vc
        if current_vc and current_vc.is_playing():
            current_vc.stop()
            await current_vc.disconnect()
            current_vc = None
            await interaction.response.send_message(
                "Riproduzione interrotta e disconnesso dal canale vocale."
            )
        else:
            await interaction.response.send_message("Nessuna riproduzione in corso.")

        if current_vc and current_vc.is_playing():
            interaction.response.send_message("Riproduzione in corso...")

        # Attendere fino alla fine della riproduzione
        while current_vc and current_vc.is_playing():
            await asyncio.sleep(1)

        # Questo metodo connette il bot al canale vocale se il canale non è vuoto e riproduce il file audio,
        # rimane in attesa 3 secondi per permettere di aggiungersi altri file in coda da riprodurre successivamente

    async def audio_player(self):
        while True:
            channel, file_name = await audio_queue.get()
            try:
                vc = await channel.connect()
                # elif vc.channel.id != channel.id:
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

    async def enumerate_messages(self, aiterator):
        index = 0
        async for item in aiterator:
            yield index, item
            index += 1

    async def leggi_notizie(
        self, interaction: discord.Interaction, countnews, channel_news
    ):
        patternTextAndUrl = r"\nLEGGI LA NOTIZIA -> http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
        patternUrl = r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
        messages = []
        if channel_news != None and channel_news != "":
            # Ottieni le ultime 'n' notizie da channel_news con la funzione history
            async for index, message in self.enumerate_messages(
                channel_news.history(limit=countnews)
            ):
                message.content = re.sub(patternTextAndUrl, "", message.content)
                message.content = re.sub(patternUrl, "", message.content)
                messages.append(message.content)
                await self.text_to_speech(
                    message.content,
                    f"news_by_channel_{channel_news.id}_{index}",
                    interaction.channel.id,
                )

            print(f"Notizie: {messages}", flush=True)
