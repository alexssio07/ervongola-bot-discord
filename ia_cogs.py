"""
Modulo IACog — Cog Discord per l'integrazione con Ollama/Qwen2.5.

Gestisce:
- DM al bot                          → risposta IA con memoria conversazionale
- Messaggi in chat_for_ai_id_discord → risposta IA con memoria conversazionale
- Menzioni del bot                   → risposta IA con memoria conversazionale

Comandi slash:
  IA / Conversazione:
    /chiedi_ia      — domanda all'IA con risposta testuale (anche con TTS opzionale)
    /ask            — domanda amichevole con memoria
    /tech           — domanda tecnica con memoria
    /creative       — richiesta creativa con memoria
    /summarize      — riassunto di un testo (stateless)
    /translate      — traduzione di un testo (stateless)

  Memoria:
    /ricorda        — salva un documento in memoria persistente
    /dimentica      — azzera la cronologia conversazionale
    /dimentica_doc  — cancella un documento specifico
    /memoria        — mostra lo stato della memoria

  Audio:
    /ascoltaultimomessaggio — riproduce via TTS l'ultima risposta dell'IA nel canale vocale

  Utilità:
    /aiuto          — lista di tutti i comandi disponibili (/help è già definito in bot-discord.py)
    /ping           — latenza del bot
    /suggerimento   — invia un suggerimento per una nuova funzione

INTEGRAZIONE in bot-discord.py (già presente):
    from ia_cogs import IACog
    await botDiscord.add_cog(IACog(botDiscord))   # in on_ready con guard
"""

import discord
from discord.ext import commands
from discord import app_commands
import ia_manager as ia
import utils as ut
import constants
import logging

logger = logging.getLogger(__name__)

_DISCORD_MAX_LEN = 1900
_IA_PREFIX = "🤖"

# Catalogo completo dei comandi — aggiorna qui quando aggiungi nuovi comandi.
# Struttura: (emoji, nome_comando, descrizione_breve)
_COMANDI: list[tuple[str, str, str]] = [
    # ── IA / Conversazione ──────────────────────────────────────────────
    ("🤖", "/chiedi_ia", "Fai una domanda all'IA (risposta in chat, TTS opzionale)"),
    ("💬", "/ask", "Domanda amichevole all'IA (con memoria conversazionale)"),
    ("🔧", "/tech", "Domanda tecnica all'IA (con memoria conversazionale)"),
    ("✨", "/creative", "Richiesta creativa all'IA (con memoria conversazionale)"),
    ("📝", "/summarize", "Chiedi all'IA di riassumere un testo"),
    ("🌐", "/translate", "Chiedi all'IA di tradurre un testo"),
    # ── Memoria ─────────────────────────────────────────────────────────
    ("💾", "/ricorda", "Insegna un testo all'IA — lo tiene in memoria"),
    ("🧹", "/dimentica", "Azzera la cronologia conversazionale con l'IA"),
    ("🗑️", "/dimentica_doc", "Cancella un documento memorizzato con /ricorda"),
    ("🧠", "/memoria", "Mostra lo stato della tua memoria con l'IA"),
    # ── Audio ────────────────────────────────────────────────────────────
    (
        "🔊",
        "/ascoltaultimomessaggio",
        "Riproduce via TTS l'ultima risposta dell'IA nel canale vocale",
    ),
    (
        "▶️",
        "/play_audio_command",
        "Riproduce un file audio dall'archivio (vedi /list_audio_commands)",
    ),
    ("📺", "/play_youtube_video", "Riproduce audio da YouTube nel canale vocale"),
    ("⏹️", "/stop", "Ferma la riproduzione audio"),
    ("🚪", "/exit", "Disconnette il bot dal canale vocale"),
    # ── Notifiche ────────────────────────────────────────────────────────
    ("📨", "/avvisa_darklord", "Avvisa DarkLord che siete online (comando privato)"),
    (
        "📨",
        "/avvisa_alexssio",
        "Avvisa Alexssio che DarkLord è online (comando privato)",
    ),
    ("📨", "/avvisa_lykanos", "Avvisa Lykanos che DarkLord è online (comando privato)"),
    # ── Notizie ──────────────────────────────────────────────────────────
    ("📰", "/read_tech_news", "Legge notizie di tecnologia nel canale vocale"),
    (
        "🧬",
        "/read_neuroscienze_news",
        "Legge notizie di neuroscienze nel canale vocale",
    ),
    ("📡", "/read_ansa_news", "Legge notizie ANSA nel canale vocale"),
    ("🗞️", "/read_cronaca_news", "Legge notizie di cronaca nel canale vocale"),
    ("🎮", "/read_videogames_news", "Legge notizie di videogiochi nel canale vocale"),
    ("🤖", "/read_robotica_news", "Legge notizie di robotica nel canale vocale"),
    ("⚡", "/read_fresh_news", "Legge le ultime notizie uscite di recente"),
    ("🌍", "/read_dal_mondo_news", "Legge notizie dal mondo nel canale vocale"),
    ("🚀", "/read_space_news", "Legge notizie sullo Spazio nel canale vocale"),
    ("💊", "/read_medicina_news", "Legge notizie di medicina nel canale vocale"),
    ("🎁", "/freevideogames", "Legge il gioco gratuito del momento su Epic/Steam"),
    # ── Blasfemie & Benvenuti ────────────────────────────────────────────
    ("😈", "/bestemmia", "Genera e riproduce bestemmie casuali (canale dedicato)"),
    ("➕", "/add_new_bestemmia", "Aggiunge una bestemmia al database"),
    ("➕", "/add_benvenuto", "Aggiunge una frase di benvenuto al database"),
    # ── Utilità ──────────────────────────────────────────────────────────
    ("🌤️", "/meteo", "Mostra le previsioni meteo per una città (Open-Meteo, gratuito)"),
    ("📌", "/ping", "Mostra la latenza del bot"),
    ("💡", "/suggerimento", "Invia un suggerimento per una nuova funzione"),
    ("❓", "/aiuto", "Mostra questo messaggio di aiuto"),
]


def _split_response(text: str, max_len: int = _DISCORD_MAX_LEN) -> list[str]:
    """
    Divide una risposta lunga in chunk sicuri per Discord.
    Spezza preferibilmente sui newline.
    """
    if len(text) <= max_len:
        return [text]
    chunks = []
    while text:
        if len(text) <= max_len:
            chunks.append(text)
            break
        split_at = text.rfind("\n", 0, max_len)
        if split_at == -1:
            split_at = max_len
        chunks.append(text[:split_at].rstrip())
        text = text[split_at:].lstrip()
    return chunks


async def _send_chunks(send_fn, text: str, prefix: str = _IA_PREFIX):
    """Invia la risposta in chunk, aggiungendo il prefix solo al primo."""
    chunks = _split_response(text)
    for i, chunk in enumerate(chunks):
        await send_fn(f"{prefix} {chunk}" if i == 0 else chunk)


class IACog(commands.Cog):
    """
    Cog che gestisce l'integrazione IA nel bot Er Vongola.
    Usa la memoria conversazionale per utente tramite ia_manager.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._ia_channel_id: int | None = self._load_ia_channel_id()

    def _load_ia_channel_id(self) -> int | None:
        try:
            raw = constants.chats_database.get("chat_for_ai_id_discord")
            if raw:
                return int(raw)
        except (ValueError, AttributeError, KeyError) as e:
            logger.warning(f"[IACog] chat_for_ai_id_discord non valido: {e}")
        return None

    # ------------------------------------------------------------------ #
    # Helper: risposta contestuale con memoria                             #
    # ------------------------------------------------------------------ #

    async def _risposta_contestuale(
        self,
        message: discord.Message,
        content: str,
        style: str = "risposta_amichevole",
    ):
        async with message.channel.typing():
            risposta = await ia.ask_ia_contextual(
                content, user_id=message.author.id, style=style
            )

        if not risposta:
            await message.reply(
                "⚠️ L'IA non è disponibile al momento. Riprova tra poco.",
                mention_author=False,
            )
            return

        await _send_chunks(
            lambda text: message.reply(text, mention_author=False), risposta
        )

    # ------------------------------------------------------------------ #
    # LISTENER on_message                                                   #
    # ------------------------------------------------------------------ #

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        is_dm = isinstance(message.channel, discord.DMChannel)
        is_ia_channel = (
            self._ia_channel_id is not None
            and isinstance(message.channel, discord.TextChannel)
            and message.channel.id == self._ia_channel_id
        )
        is_mention = self.bot.user in message.mentions

        if not (is_dm or is_ia_channel or is_mention):
            await self.bot.process_commands(message)
            return

        content = message.content
        if is_mention:
            content = content.replace(f"<@{self.bot.user.id}>", "").strip()
            content = content.replace(f"<@!{self.bot.user.id}>", "").strip()

        if not content.strip():
            if is_dm or is_mention:
                await message.reply(
                    "👋 Ciao! Scrivimi qualcosa e ti rispondo.", mention_author=False
                )
            await self.bot.process_commands(message)
            return

        prefix = self.bot.command_prefix
        if isinstance(prefix, str) and content.startswith(prefix):
            await self.bot.process_commands(message)
            return

        await self._risposta_contestuale(message, content)
        await self.bot.process_commands(message)

    # ------------------------------------------------------------------ #
    # SLASH COMMAND /ask                                                    #
    # ------------------------------------------------------------------ #

    @app_commands.command(
        name="ask", description="Fai una domanda all'IA (con memoria conversazionale)"
    )
    @app_commands.describe(domanda="La domanda da porre all'IA")
    async def ask_slash(self, interaction: discord.Interaction, domanda: str):
        await interaction.response.defer()
        risposta = await ia.ask_ia_contextual(
            domanda, user_id=interaction.user.id, style="risposta_amichevole"
        )
        if not risposta:
            await interaction.followup.send("⚠️ IA non disponibile.", ephemeral=True)
            return
        chunks = _split_response(risposta)
        await interaction.followup.send(f"{_IA_PREFIX} {chunks[0]}")
        for chunk in chunks[1:]:
            await interaction.followup.send(chunk)

    # ------------------------------------------------------------------ #
    # SLASH COMMAND /tech                                                   #
    # ------------------------------------------------------------------ #

    @app_commands.command(
        name="tech", description="Fai una domanda tecnica all'IA (con memoria)"
    )
    @app_commands.describe(domanda="La domanda tecnica")
    async def tech_slash(self, interaction: discord.Interaction, domanda: str):
        await interaction.response.defer()
        risposta = await ia.ask_ia_contextual(
            domanda, user_id=interaction.user.id, style="risposta_tecnica"
        )
        if not risposta:
            await interaction.followup.send("⚠️ IA non disponibile.", ephemeral=True)
            return
        chunks = _split_response(risposta)
        await interaction.followup.send(f"🔧 {chunks[0]}")
        for chunk in chunks[1:]:
            await interaction.followup.send(chunk)

    # ------------------------------------------------------------------ #
    # SLASH COMMAND /creative                                               #
    # ------------------------------------------------------------------ #

    @app_commands.command(
        name="creative", description="Chiedi qualcosa di creativo all'IA (con memoria)"
    )
    @app_commands.describe(domanda="La richiesta creativa")
    async def creative_slash(self, interaction: discord.Interaction, domanda: str):
        await interaction.response.defer()
        risposta = await ia.ask_ia_contextual(
            domanda, user_id=interaction.user.id, style="risposta_creativa"
        )
        if not risposta:
            await interaction.followup.send("⚠️ IA non disponibile.", ephemeral=True)
            return
        chunks = _split_response(risposta)
        await interaction.followup.send(f"✨ {chunks[0]}")
        for chunk in chunks[1:]:
            await interaction.followup.send(chunk)

    # ------------------------------------------------------------------ #
    # SLASH COMMAND /summarize                                              #
    # ------------------------------------------------------------------ #

    @app_commands.command(
        name="summarize", description="Chiedi all'IA di riassumere un testo"
    )
    @app_commands.describe(testo="Il testo da riassumere (minimo 50 caratteri)")
    async def summarize_slash(self, interaction: discord.Interaction, testo: str):
        if len(testo) < 50:
            await interaction.response.send_message(
                "❌ Testo troppo corto (minimo 50 caratteri).", ephemeral=True
            )
            return
        await interaction.response.defer()
        summary = await ia.generate_summary(testo)
        if not summary:
            await interaction.followup.send("⚠️ IA non disponibile.", ephemeral=True)
            return
        chunks = _split_response(summary)
        await interaction.followup.send(f"📝 **Riassunto:**\n{chunks[0]}")
        for chunk in chunks[1:]:
            await interaction.followup.send(chunk)

    # ------------------------------------------------------------------ #
    # SLASH COMMAND /translate                                              #
    # ------------------------------------------------------------------ #

    @app_commands.command(
        name="translate", description="Chiedi all'IA di tradurre un testo"
    )
    @app_commands.describe(
        testo="Il testo da tradurre",
        lingua="Lingua di destinazione (es. English, French, Spanish)",
    )
    async def translate_slash(
        self, interaction: discord.Interaction, testo: str, lingua: str = "English"
    ):
        await interaction.response.defer()
        translation = await ia.translate_text(testo, target_lang=lingua)
        if not translation:
            await interaction.followup.send("⚠️ IA non disponibile.", ephemeral=True)
            return
        chunks = _split_response(translation)
        await interaction.followup.send(f"🌐 **Traduzione in {lingua}:**\n{chunks[0]}")
        for chunk in chunks[1:]:
            await interaction.followup.send(chunk)

    # ------------------------------------------------------------------ #
    # SLASH COMMAND /ricorda                                                #
    # ------------------------------------------------------------------ #

    @app_commands.command(
        name="ricorda",
        description="Insegna un testo all'IA — lo terrà in memoria tra le sessioni",
    )
    @app_commands.describe(
        titolo="Nome/etichetta del documento (es. 'regole server', 'mia bio')",
        testo="Il testo da memorizzare",
    )
    async def ricorda_slash(
        self, interaction: discord.Interaction, titolo: str, testo: str
    ):
        ok, msg = ia.store_document(
            user_id=interaction.user.id, title=titolo, content=testo
        )
        await interaction.response.send_message(
            f"{'✅' if ok else '❌'} {msg}", ephemeral=True
        )

    # ------------------------------------------------------------------ #
    # SLASH COMMAND /dimentica                                              #
    # ------------------------------------------------------------------ #

    @app_commands.command(
        name="dimentica",
        description="Azzera la cronologia conversazionale (i documenti /ricorda restano intatti)",
    )
    async def dimentica_slash(self, interaction: discord.Interaction):
        ia.clear_memory(interaction.user.id)
        stats = ia.get_memory_stats(interaction.user.id)
        docs_info = (
            f"📂 {stats['docs']} documento/i memorizzato/i con `/ricorda` sono intatti."
            if stats["docs"] > 0
            else "📂 Nessun documento memorizzato."
        )
        await interaction.response.send_message(
            f"🧹 **Cronologia conversazione azzerata.** La prossima risposta riparte da zero.\n"
            f"{docs_info}\n"
            f"*(Usa `/ricorda` per insegnare testi permanenti all'IA.)*",
            ephemeral=True,
        )

    # ------------------------------------------------------------------ #
    # SLASH COMMAND /dimentica_doc                                          #
    # ------------------------------------------------------------------ #

    @app_commands.command(
        name="dimentica_doc",
        description="Cancella un documento memorizzato con /ricorda",
    )
    @app_commands.describe(titolo="Il titolo esatto del documento da cancellare")
    async def dimentica_doc_slash(self, interaction: discord.Interaction, titolo: str):
        ok, msg = ia.delete_document(interaction.user.id, titolo)
        await interaction.response.send_message(
            f"{'✅' if ok else '❌'} {msg}", ephemeral=True
        )

    # ------------------------------------------------------------------ #
    # SLASH COMMAND /memoria                                                #
    # ------------------------------------------------------------------ #

    @app_commands.command(
        name="memoria", description="Mostra lo stato della tua memoria con l'IA"
    )
    async def memoria_slash(self, interaction: discord.Interaction):
        stats = ia.get_memory_stats(interaction.user.id)

        if stats["expired"] or stats["turns"] == 0:
            sessione_info = "💤 Nessuna sessione attiva (o scaduta)."
        else:
            sessione_info = (
                f"💬 **{stats['turns']}/{stats['max_turns']}** turni in memoria "
                f"(inattiva da {stats['minutes_idle']} min, "
                f"scade dopo {stats['ttl_minutes']} min)"
            )

        if stats["docs"] == 0:
            doc_info = "📂 Nessun documento memorizzato."
        else:
            titoli = "\n".join(f"  • `{t}`" for t in stats["doc_titles"])
            doc_info = (
                f"📂 **{stats['docs']}/{stats['max_docs']}** documenti:\n{titoli}"
            )

        last_info = (
            "🔊 Ultima risposta IA disponibile per `/ascoltaultimomessaggio`."
            if stats.get("has_last_response")
            else "🔇 Nessuna risposta IA recente da riprodurre."
        )

        embed = discord.Embed(
            title="🧠 Stato memoria IA",
            description=f"{sessione_info}\n\n{doc_info}\n\n{last_info}",
            color=0x7289DA,
        )
        embed.set_footer(
            text="Usa /ricorda per aggiungere documenti • /dimentica per azzerare la chat"
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ------------------------------------------------------------------ #
    # SLASH COMMAND /ascoltaultimomessaggio                                 #
    # ------------------------------------------------------------------ #

    @app_commands.command(
        name="ascoltaultimomessaggio",
        description="Riproduce via TTS l'ultima risposta dell'IA nel canale vocale",
    )
    async def ascolta_slash(self, interaction: discord.Interaction):
        """
        Recupera l'ultima risposta IA per l'utente e la riproduce nel canale vocale
        tramite la stessa logica TTS usata per i messaggi di benvenuto:
        text_to_speech() → tts_manager → audio_queue → audio_player.

        Condizioni:
        - L'utente deve essere in un canale vocale consentito.
        - Deve esistere almeno una risposta IA precedente nella sessione corrente.
        """
        # Verifica che l'utente sia in un canale vocale
        voice_state = interaction.user.voice
        if not voice_state or not voice_state.channel:
            await interaction.response.send_message(
                "🎙️ Devi essere in un canale vocale per usare questo comando.",
                ephemeral=True,
            )
            return

        channel = voice_state.channel

        # Recupera l'ultima risposta IA
        last_response = ia.get_last_ia_response(interaction.user.id)
        if not last_response:
            await interaction.response.send_message(
                "🔇 Non ho ancora risposto nulla in questa sessione. "
                "Fai prima una domanda con `/ask` o `/chiedi_ia`.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            f"🔊 Riproduco l'ultima risposta nel canale **{channel.name}**...",
            ephemeral=True,
        )

        logger.info(
            f"[TTS] /ascoltaultimomessaggio — user={interaction.user.name} "
            f"canale='{channel.name}' | {len(last_response)} char"
        )

        # Stessa logica di make_audio / text_to_speech in utils.py:
        # genera il file mp3 tramite tts_manager e lo accoda in audio_queue.
        await ut.text_to_speech(
            last_response,
            f"ia_last_{interaction.user.id}",
            channel,
        )

    # ------------------------------------------------------------------ #
    # SLASH COMMAND /aiuto                                                  #
    # ------------------------------------------------------------------ #
    # Nota: bot-discord.py registra già un comando "/help" (info_help,
    # messaggio statico). Per evitare un conflitto di nomi nel command tree
    # (add_cog fallirebbe all'avvio), qui esponiamo solo "/aiuto" con il
    # catalogo completo e dinamico dei comandi.

    @app_commands.command(
        name="aiuto", description="Mostra tutti i comandi disponibili del bot"
    )
    async def aiuto_slash(self, interaction: discord.Interaction):
        await self._send_help(interaction)

    async def _send_help(self, interaction: discord.Interaction):
        """
        Costruisce e invia l'embed con la lista completa dei comandi.
        Usa il catalogo _COMANDI centralizzato in cima al modulo.
        Aggiorna _COMANDI per mantenere la lista sincronizzata.
        """
        # Raggruppa i comandi per sezione leggendo le righe del catalogo.
        # Le sezioni sono determinate dai commenti nel catalogo _COMANDI.
        sections = {
            "🤖 IA / Conversazione": [],
            "🧠 Memoria": [],
            "🔊 Audio": [],
            "📨 Notifiche": [],
            "📰 Notizie": [],
            "😈 Blasfemie & Benvenuti": [],
            "🛠️ Utilità": [],
        }

        # Assegna ogni comando alla sua sezione in base all'ordine in _COMANDI
        ia_cmds = [
            "/chiedi_ia",
            "/ask",
            "/tech",
            "/creative",
            "/summarize",
            "/translate",
        ]
        memoria_cmds = ["/ricorda", "/dimentica", "/dimentica_doc", "/memoria"]
        audio_cmds = [
            "/ascoltaultimomessaggio",
            "/play_audio_command",
            "/play_youtube_video",
            "/stop",
            "/exit",
        ]
        notif_cmds = ["/avvisa_darklord", "/avvisa_alexssio", "/avvisa_lykanos"]
        notizie_cmds = [
            "/read_tech_news",
            "/read_neuroscienze_news",
            "/read_ansa_news",
            "/read_cronaca_news",
            "/read_videogames_news",
            "/read_robotica_news",
            "/read_fresh_news",
            "/read_dal_mondo_news",
            "/read_space_news",
            "/read_medicina_news",
            "/freevideogames",
        ]
        blasf_cmds = ["/bestemmia", "/add_new_bestemmia", "/add_benvenuto"]

        for emoji, nome, desc in _COMANDI:
            entry = f"{emoji} **{nome}** — {desc}"
            nome_base = nome.split(" /")[0]  # gestisce "/aiuto / /help"
            if nome_base in ia_cmds:
                sections["🤖 IA / Conversazione"].append(entry)
            elif nome_base in memoria_cmds:
                sections["🧠 Memoria"].append(entry)
            elif nome_base in audio_cmds:
                sections["🔊 Audio"].append(entry)
            elif nome_base in notif_cmds:
                sections["📨 Notifiche"].append(entry)
            elif nome_base in notizie_cmds:
                sections["📰 Notizie"].append(entry)
            elif nome_base in blasf_cmds:
                sections["😈 Blasfemie & Benvenuti"].append(entry)
            else:
                sections["🛠️ Utilità"].append(entry)

        embed = discord.Embed(
            title="📋 Er Vongola — Comandi disponibili",
            description=(
                "Usa `/` per autocompletare i comandi direttamente in Discord.\n"
                "I comandi IA mantengono la memoria della conversazione per sessione."
            ),
            color=0x5865F2,
        )

        for section_name, entries in sections.items():
            if entries:
                embed.add_field(
                    name=section_name,
                    value="\n".join(entries),
                    inline=False,
                )

        embed.set_footer(
            text="Er Vongola Bot • Scrivi /suggerimento per proporre nuove funzioni"
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
