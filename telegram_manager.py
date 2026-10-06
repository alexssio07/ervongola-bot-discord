"""
Modulo Telegram Manager
Bot Telegram (python-telegram-bot v22, asyncio-nativo) che porta l'IA di
Er Vongola anche su Telegram, ma SOLO nel thread configurato e SOLO quando
il bot viene taggato (@menzione) — nessuna risposta "libera" a ogni messaggio.

Perché un modulo separato e non un secondo processo:
- Riusa la stessa istanza di ia_manager (stessa cache di history per utente,
  stesso pool aiohttp verso Ollama, stessi stili/system prompt) — zero
  duplicazione della logica IA tra Discord e Telegram.
- Gira nello stesso event loop asyncio di bot-discord.py (vedi main() in
  bot-discord.py) tramite asyncio.create_task(): un solo processo, un solo
  loop, niente thread aggiuntivi che condividerebbero le strutture dati di
  ia_manager senza sincronizzazione.

Architettura evento/metodo (separazione richiesta):
- _on_group_message(): è l'handler collegato all'evento (MessageHandler).
  Ha l'UNICA responsabilità di decidere "se rispondere": verifica che il
  messaggio sia nel gruppo/thread configurato (TELEGRAM_GROUP_CHAT_ID +
  TELEGRAM_GROUP_THREAD_ID) e che il bot sia taggato (@menzione esplicita
  nel testo). Se una delle due condizioni non è vera, esce senza fare nulla.
- _rispondi_ia(): è il metodo a parte che decide "cosa rispondere". Viene
  chiamato da _on_group_message solo dopo che il trigger è confermato.
  Pulisce il tag dal testo, chiama ia_manager con memoria conversazionale
  per utente, e invia la risposta (con chunking se supera il limite Telegram).

Un message_thread_id da solo non identifica univocamente una chat (è
un contatore interno alla chat), quindi il controllo verifica sempre anche
chat.id == TELEGRAM_GROUP_CHAT_ID insieme a TELEGRAM_GROUP_THREAD_ID.

Requisito operativo IMPORTANTE:
    Il bot Telegram deve avere la "privacy mode" DISABILITATA in @BotFather
    (comando /setprivacy → Disable) per poter leggere i messaggi nel gruppo
    che non sono comandi "/xxx". Senza questo, Telegram non consegna al bot
    i messaggi in cui viene semplicemente taggato con @nomebot in un gruppo.

Se Ollama non è raggiungibile, ia_manager restituisce None e qui viene
mostrato lo stesso messaggio di fallback usato su Discord.
"""

import asyncio
import logging
import re

from telegram import Update
from telegram.constants import ChatAction, MessageEntityType
from telegram.error import InvalidToken, NetworkError
from telegram.ext import (
    Application,
    ApplicationBuilder,
    ContextTypes,
    MessageHandler,
    filters,
)
from telegram.request import HTTPXRequest

import constants
import ia_manager as ia

logger = logging.getLogger(__name__)

_TELEGRAM_MAX_LEN = 4000  # margine di sicurezza sotto il limite Telegram di 4096 char
_IA_PREFIX = "🤖 "
_STYLE = "risposta_cinica_simpatica"

# Backoff del supervisore (secondi) e intervallo del controllo di liveness.
_RESTART_DELAY_MIN = 5.0
_RESTART_DELAY_MAX = 300.0
_HEALTHY_AFTER = 60.0  # se ha girato almeno così a lungo, il backoff riparte da MIN
_LIVENESS_INTERVAL = 30.0


class _PollingNetworkErrorFilter(logging.Filter):
    """
    PTB logga a ERROR (con traceback completo) ogni NetworkError del long-poll,
    ma poi ritenta da solo con backoff: è un evento transitorio e
    autorisolvente (reset di connessione lato rete). Lo riduciamo a una riga
    WARNING, così resta visibile ma non spamma log e pannello web.
    Gli altri errori (non-NetworkError) passano invariati.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        exc = record.exc_info[1] if record.exc_info else None
        if isinstance(exc, NetworkError):
            record.levelno = logging.WARNING
            record.levelname = "WARNING"
            record.msg = (
                f"[TG] Errore di rete transitorio nel polling "
                f"({type(exc).__name__}: {exc}) — retry automatico in corso."
            )
            record.args = ()
            record.exc_info = None
            record.exc_text = None
        return True


logging.getLogger("telegram.ext.Updater").addFilter(_PollingNetworkErrorFilter())


def _session_id(telegram_user_id: int) -> str:
    """
    Namespace dedicato per le sessioni Telegram in ia_manager, che tiene le
    history in un dict globale chiavato per str(user_id). Discord passa i suoi
    ID (snowflake, ~18 cifre) così come sono; qui aggiungiamo un prefisso per
    escludere per costruzione qualunque collisione tra le due piattaforme —
    costo nullo, correttezza in più.
    """
    return f"tg-{telegram_user_id}"


def _split_response(text: str, max_len: int = _TELEGRAM_MAX_LEN) -> list[str]:
    """Divide una risposta lunga in chunk sicuri per Telegram (stessa logica di ia_cogs.py)."""
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


def _is_configured_thread(update: Update) -> bool:
    """
    True solo se il messaggio arriva nel gruppo/thread configurato:
    chat.id == TELEGRAM_GROUP_CHAT_ID E message_thread_id == TELEGRAM_GROUP_THREAD_ID.
    Se una delle due variabili non è configurata, il trigger resta disattivato
    (nessuna risposta "di default" su chat non esplicitamente indicate).
    """
    msg = update.effective_message
    chat = update.effective_chat
    if msg is None or chat is None or not msg.text:
        return False

    group_id = constants.TELEGRAM_GROUP_CHAT_ID
    thread_id = constants.TELEGRAM_GROUP_THREAD_ID
    if not group_id or not thread_id:
        return False

    return chat.id == int(group_id) and msg.message_thread_id == int(thread_id)


def _bot_is_mentioned(message, bot_username: str | None) -> bool:
    """
    True solo se il testo contiene un'entità Telegram di tipo "mention"
    (@nomebot) che corrisponde esattamente allo username del bot.
    Si usano le entities (non una semplice substring) per evitare falsi
    positivi su testo che contenga casualmente la stringa "@nomebot".
    """
    if not bot_username or not message.entities:
        return False

    mention_tag = f"@{bot_username}".lower()
    for entity in message.entities:
        if entity.type == MessageEntityType.MENTION:
            mention_text = message.text[entity.offset : entity.offset + entity.length]
            if mention_text.lower() == mention_tag:
                return True
    return False


async def _rispondi_ia(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Metodo a parte richiamato dall'evento SOLO dopo che il trigger è
    confermato (thread giusto + bot taggato). Pulisce il tag dal testo,
    interroga l'IA con memoria conversazionale per utente e invia la
    risposta, spezzata in più messaggi se supera il limite Telegram.
    """
    msg = update.effective_message
    chat = update.effective_chat
    user = update.effective_user

    bot_username = context.bot.username
    testo = msg.text
    if bot_username:
        testo = re.sub(
            rf"@{re.escape(bot_username)}\b", "", testo, flags=re.IGNORECASE
        ).strip()

    if not testo:
        await msg.reply_text("👋 Dimmi pure, sono qui.")
        return

    user_id = _session_id(user.id)

    await context.bot.send_chat_action(
        chat_id=chat.id,
        action=ChatAction.TYPING,
        message_thread_id=msg.message_thread_id,
    )

    logger.info(
        f"[TG] Taggato da {user.username or user.id} in thread="
        f"{msg.message_thread_id}: {testo[:80]}"
    )
    risposta = await ia.ask_ia_contextual(testo, user_id=user_id, style=_STYLE)

    if not risposta:
        await msg.reply_text("⚠️ L'IA non è disponibile al momento. Riprova tra poco.")
        return

    chunks = _split_response(risposta)
    await msg.reply_text(f"{_IA_PREFIX}{chunks[0]}")
    for chunk in chunks[1:]:
        await context.bot.send_message(
            chat_id=chat.id, text=chunk, message_thread_id=msg.message_thread_id
        )


async def _on_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Evento collegato al MessageHandler (unica responsabilità: decidere SE
    rispondere). Condizioni, entrambe necessarie:
    1. il messaggio è nel thread configurato (_is_configured_thread);
    2. il bot è esplicitamente taggato nel testo (_bot_is_mentioned).
    Se una manca, esce senza effetti collaterali. Solo se entrambe sono vere
    delega la risposta vera e propria a _rispondi_ia().
    """
    user = update.effective_user
    if user is None or user.is_bot:
        return

    if not _is_configured_thread(update):
        return

    if not _bot_is_mentioned(update.effective_message, context.bot.username):
        return

    await _rispondi_ia(update, context)


async def _on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(f"[TG] Errore non gestito: {context.error}", exc_info=context.error)


def _build_application() -> Application:
    # get_updates_read_timeout di default è 5s: troppo stretto per il long-poll
    # (che tiene la connessione aperta fino al `timeout` passato a
    # start_polling, default 10s) su una rete domestica/Wi-Fi meno stabile di
    # un datacenter. Un read_timeout troppo corto fa scadere lato client la
    # lettura della risposta prima che Telegram la invii, con conseguente
    # httpx.ReadError/NetworkError nel polling — non risolve un eventuale
    # reset di rete reale (fuori dal nostro controllo), ma elimina i falsi
    # allarmi dovuti al timeout troppo aggressivo e dà più margine al retry
    # automatico di network_retry_loop prima che debba loggare un errore.
    request = HTTPXRequest(
        connect_timeout=10.0,
        read_timeout=20.0,
        pool_timeout=10.0,
    )
    application = (
        ApplicationBuilder()
        .token(constants.TELEGRAM_TOKEN)
        .get_updates_read_timeout(20.0)
        .get_updates_connect_timeout(10.0)
        .get_updates_pool_timeout(10.0)
        .request(request)
        .build()
    )
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, _on_group_message)
    )
    application.add_error_handler(_on_error)
    return application


async def _run_telegram_once(stop_event: asyncio.Event) -> None:
    """
    Un ciclo di vita completo del bot Telegram: build → start → polling →
    attesa. Ritorna solo quando stop_event è impostato; lancia un'eccezione se
    l'avvio fallisce o se il polling si ferma inaspettatamente (così il
    supervisore in run_telegram_bot può ricostruire l'Application).

    bootstrap_retries=-1: al boot la rete può non essere ancora pronta
    (Raspberry/Docker); PTB riprova da solo finché non risponde invece di
    sollevare NetworkError al primo tentativo.
    """
    application = _build_application()

    async with application:
        await application.start()
        await application.updater.start_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True,
            bootstrap_retries=-1,
        )
        logger.info(
            "[TG] Bot Telegram in ascolto (polling) — risponde solo se taggato "
            f"nel thread {constants.TELEGRAM_GROUP_THREAD_ID} della chat "
            f"{constants.TELEGRAM_GROUP_CHAT_ID}."
        )
        try:
            while not stop_event.is_set():
                try:
                    await asyncio.wait_for(
                        stop_event.wait(), timeout=_LIVENESS_INTERVAL
                    )
                except asyncio.TimeoutError:
                    pass
                if not stop_event.is_set() and not application.updater.running:
                    raise RuntimeError("polling Telegram terminato inaspettatamente")
        finally:
            logger.info("[TG] Arresto bot Telegram...")
            # Ogni stop() può sollevare se il componente è già fermo: non deve
            # mai propagarsi (né impedire shutdown() in uscita da `async with`).
            for step in (application.updater.stop, application.stop):
                try:
                    await step()
                except Exception as e:  # noqa: BLE001
                    logger.debug(f"[TG] Stop ignorato: {e}")
            logger.info("[TG] Bot Telegram arrestato.")


async def run_telegram_bot(stop_event: asyncio.Event) -> None:
    """
    Supervisore del bot Telegram, da lanciare con
    asyncio.create_task(run_telegram_bot(stop_event)) nello stesso event loop
    di bot-discord.py (non usa Application.run_polling(), che gestisce un
    proprio loop bloccante).

    Garanzia: NON solleva mai eccezioni verso il chiamante — un problema di
    Telegram (rete assente, errore di setup, polling morto) non deve poter
    influire su Discord. In caso di errore ricostruisce l'Application con
    backoff esponenziale (5s → 5min). Un token non valido è l'unico caso in
    cui si ferma definitivamente (riprovare non servirebbe).

    drop_pending_updates=True evita di processare in un colpo solo tutti i
    messaggi accumulati mentre il bot era offline (raffica di chiamate a
    Ollama al riavvio).
    """
    if not constants.TELEGRAM_TOKEN:
        logger.warning("[TG] TELEGRAM_TOKEN non impostato — bot Telegram non avviato.")
        return

    loop = asyncio.get_running_loop()
    delay = _RESTART_DELAY_MIN
    while not stop_event.is_set():
        started = loop.time()
        try:
            await _run_telegram_once(stop_event)
            return  # uscita pulita: stop_event impostato
        except InvalidToken:
            logger.error("[TG] TELEGRAM_TOKEN non valido — bot Telegram disattivato.")
            return
        except Exception as e:  # noqa: BLE001 — il supervisore non deve mai cadere
            if loop.time() - started >= _HEALTHY_AFTER:
                delay = _RESTART_DELAY_MIN
            logger.error(
                f"[TG] Bot Telegram fermato da un errore ({type(e).__name__}: {e}); "
                f"riavvio tra {delay:.0f}s.",
                exc_info=not isinstance(e, NetworkError),
            )
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=delay)
            except asyncio.TimeoutError:
                pass
            delay = min(delay * 2, _RESTART_DELAY_MAX)
