"""
Modulo TTS Manager
Gestisce la conversione text-to-speech con due motori in cascata:
  1. Google Cloud TTS — voci Neural2, qualità eccellente, gratuito fino a 1M caratteri/mese
  2. gTTS              — Google TTS base, fallback finale

Configurazione nel .env:
  GOOGLE_TTS_API_KEY  — chiave API Google Cloud TTS (obbligatoria per il motore principale)
  GOOGLE_TTS_VOICE    — voce da usare (default: it-IT-Neural2-A)
  GOOGLE_TTS_LANGUAGE — lingua (default: it-IT)

Voci italiane Google Neural2:
  - it-IT-Neural2-A   (Donna)
  - it-IT-Neural2-C   (Uomo)
"""

import logging
import os
import asyncio
import base64
import aiohttp
from gtts import gTTS

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configurazione Google Cloud TTS
# ---------------------------------------------------------------------------
GOOGLE_TTS_API_KEY = os.getenv("GOOGLE_TTS_API_KEY", "")
GOOGLE_TTS_VOICE = os.getenv("GOOGLE_TTS_VOICE", "it-IT-Neural2-A")
GOOGLE_TTS_LANGUAGE = os.getenv("GOOGLE_TTS_LANGUAGE", "it-IT")
GOOGLE_TTS_URL = "https://texttospeech.googleapis.com/v1/text:synthesize"


def log_tts_status() -> None:
    """
    Logga lo stato di tutti i motori TTS disponibili.
    Va chiamata da bot-discord.py subito dopo logging.basicConfig().
    """
    if GOOGLE_TTS_API_KEY:
        logger.info(
            f"[TTS] ✅ Google Cloud TTS configurato. "
            f"Voce: {GOOGLE_TTS_VOICE} | Lingua: {GOOGLE_TTS_LANGUAGE}"
        )
    else:
        logger.warning(
            "[TTS] ⚠️ GOOGLE_TTS_API_KEY non configurata — "
            "verrà usato gTTS come motore principale."
        )

    logger.info("[TTS] ✅ gTTS disponibile come fallback finale.")


# ---------------------------------------------------------------------------
# Google Cloud TTS — motore principale
# ---------------------------------------------------------------------------


async def _text_to_speech_google(text: str, filename: str) -> bool:
    """
    Genera audio con Google Cloud TTS (Neural2) in modo asincrono.
    Richiede GOOGLE_TTS_API_KEY nel .env e connessione internet.

    Args:
        text:     Testo da convertire.
        filename: Path del file .mp3 di output.

    Returns:
        True se la generazione è andata a buon fine, False altrimenti.
    """
    if not GOOGLE_TTS_API_KEY:
        return False

    logger.info(
        f"[TTS] Motore: Google Cloud TTS | "
        f"Voce: {GOOGLE_TTS_VOICE} | "
        f"Testo: {text[:50]!r}"
    )

    payload = {
        "input": {"text": text},
        "voice": {
            "languageCode": GOOGLE_TTS_LANGUAGE,
            "name": GOOGLE_TTS_VOICE,
        },
        "audioConfig": {
            "audioEncoding": "MP3",
            "speakingRate": 1.0,
            "pitch": 0.0,
        },
    }

    try:
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                f"{GOOGLE_TTS_URL}?key={GOOGLE_TTS_API_KEY}",
                json=payload,
            ) as response:
                if response.status != 200:
                    body = await response.text()
                    logger.error(
                        f"[TTS-Google] ❌ Errore API {response.status}: {body[:300]}"
                    )
                    return False

                data = await response.json()
                audio_content = data.get("audioContent", "")
                if not audio_content:
                    logger.error("[TTS-Google] ❌ Risposta API vuota.")
                    return False

                audio_bytes = base64.b64decode(audio_content)
                with open(filename, "wb") as f:
                    f.write(audio_bytes)

                logger.info(f"[TTS-Google] ✅ Audio generato: {filename}")
                return True

    except asyncio.TimeoutError:
        logger.error("[TTS-Google] ❌ Timeout connessione a Google Cloud TTS.")
        return False

    except aiohttp.ClientError as e:
        logger.error(f"[TTS-Google] ❌ Errore di rete ({type(e).__name__}): {e}")
        return False

    except OSError as e:
        logger.error(f"[TTS-Google] ❌ Errore scrittura file '{filename}': {e}")
        return False

    except Exception as e:
        logger.error(
            f"[TTS-Google] ❌ Errore imprevisto ({type(e).__name__}): {e}",
            exc_info=True,
        )
        return False


# ---------------------------------------------------------------------------
# gTTS — fallback finale
# ---------------------------------------------------------------------------


def _text_to_speech_gtts_sync(text: str, filename: str) -> bool:
    """
    Genera audio con gTTS (Google TTS base) in modo sincrono.
    Fallback finale — disponibile finché c'è internet.

    Args:
        text:     Testo da convertire.
        filename: Path del file .mp3 di output.

    Returns:
        True se la generazione è andata a buon fine, False altrimenti.
    """
    logger.info(f"[TTS] Motore: gTTS | Testo: {text[:50]!r}")
    try:
        tts = gTTS(text=text, lang="it", tld="it", slow=False, lang_check=False)
        tts.save(filename)
        logger.info(f"[TTS-gTTS] ✅ Audio generato: {filename}")
        return True

    except OSError as e:
        logger.error(f"[TTS-gTTS] ❌ Errore scrittura file '{filename}': {e}")
        return False

    except Exception as e:
        logger.error(
            f"[TTS-gTTS] ❌ Errore imprevisto ({type(e).__name__}): {e}",
            exc_info=True,
        )
        return False


async def _text_to_speech_gtts(text: str, filename: str) -> bool:
    """
    Wrapper asincrono di gTTS tramite run_in_executor.
    gTTS è sincrono — viene eseguito in un thread separato
    per non bloccare il loop asyncio del bot.
    """
    try:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, _text_to_speech_gtts_sync, text, filename
        )
    except Exception as e:
        logger.error(
            f"[TTS-gTTS] ❌ Errore nel run_in_executor ({type(e).__name__}): {e}",
            exc_info=True,
        )
        return False


# ---------------------------------------------------------------------------
# API pubblica — unica funzione che il resto del codice deve chiamare
# ---------------------------------------------------------------------------


async def text_to_speech_async(text: str, filename: str) -> bool:
    """
    Converte testo in audio in modo asincrono.
    Cascata di motori in ordine di qualità:
      1. Google Cloud TTS (Neural2)
      2. gTTS (Google base)

    Args:
        text:     Testo da convertire in audio.
        filename: Path del file audio di output.

    Returns:
        True se la generazione è andata a buon fine, False altrimenti.
    """
    # Guard difensivo: garantisce che tutti i motori a valle ricevano
    # sempre una stringa. Senza questo controllo, un chiamante che passa
    # per errore un tipo diverso (es. un dict) causa un TypeError criptico
    # più a valle (es. "unhashable type: slice" su text[:50] in _text_to_speech_google),
    # invece di un warning chiaro e diagnosticabile qui all'ingresso.
    if not isinstance(text, str):
        logger.warning(
            f"[TTS] ⚠️ 'text' non è una stringa (tipo ricevuto: {type(text).__name__}) "
            f"— conversione forzata con str(). Controlla il chiamante."
        )
        text = str(text)

    # Tentativo 1: Google Cloud TTS
    success = await _text_to_speech_google(text, filename)
    if success:
        return True

    if GOOGLE_TTS_API_KEY:
        logger.warning("[TTS] ⚠️ Google Cloud TTS fallito — fallback su gTTS.")

    # Tentativo 2: gTTS
    success = await _text_to_speech_gtts(text, filename)
    if success:
        return True

    logger.error("[TTS] ❌ Tutti i motori TTS hanno fallito. Nessun audio generato.")
    return False


def text_to_speech_sync(text: str, filename: str) -> bool:
    """
    Converte testo in audio in modo sincrono.
    Usata solo dove asyncio non è disponibile.
    Usa gTTS direttamente (Google Cloud TTS è async).

    Args:
        text:     Testo da convertire in audio.
        filename: Path del file audio di output.

    Returns:
        True se la generazione è andata a buon fine, False altrimenti.
    """
    logger.info("[TTS-sync] Generazione sincrona via gTTS.")
    return _text_to_speech_gtts_sync(text, filename)