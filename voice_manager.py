import discord
from typing import Optional
import discord.ext.voice_recv as voice_recv
import logging
import asyncio

# Lock per prevenire tentativi di connessione simultanei
voice_lock = asyncio.Lock()

# Global variable to track the active voice client
current_vc: Optional[discord.VoiceClient] = None


async def connect_to_channel(channel: discord.VoiceChannel):
    try:
        await asyncio.wait_for(voice_lock.acquire(), timeout=30)
    except asyncio.TimeoutError:
        logging.error("[VOICE] Timeout voice_lock (30s) — deadlock! Abort.")
        raise RuntimeError("voice_lock deadlock timeout")

    try:
        logging.info(f"[VOICE] Tentativo connessione: {channel.name} (ID: {channel.id})")

        # Pulizia client locale esistente
        existing_vc = channel.guild.voice_client
        if existing_vc is not None:
            logging.info(f"[VOICE] Client esistente trovato. Disconnessione...")
            try:
                await existing_vc.disconnect(force=True)
            except Exception:
                pass
            await asyncio.sleep(1.0)

        # Connessione
        logging.info("[VOICE] Avvio handshake (timeout=60s, self_deaf=True)...")
        new_vc = await channel.connect(
            cls=voice_recv.VoiceRecvClient,
            timeout=60.0,
            reconnect=False,
            self_deaf=False,   # False: il bot può sentire E parlare
            self_mute=False,   # False: microfono attivo per VoiceRecvClient
        )
        logging.info("[VOICE] Handshake completato con successo.")
        global current_vc
        current_vc = new_vc
        return new_vc

    except discord.errors.ConnectionClosed as e:
        logging.error(
            f"[VOICE] WebSocket chiuso — codice: {e.code}, motivo: {e.reason}"
        )
        current_vc = None
        try:
            vc_to_kill = channel.guild.voice_client
            if vc_to_kill:
                await vc_to_kill.disconnect(force=True)
        except Exception:
            pass
        raise

    except Exception as e:
        logging.error(f"[VOICE] Errore durante handshake: {e}")
        current_vc = None
        raise

    finally:
        voice_lock.release()
        logging.debug("[VOICE_LOCK] Rilasciato (connect).")


async def disconnect(guild: Optional[discord.Guild] = None):
    global current_vc

    try:
        await asyncio.wait_for(voice_lock.acquire(), timeout=15)
    except asyncio.TimeoutError:
        logging.warning("[VOICE] Timeout voice_lock durante disconnect (15s) — skip.")
        return

    try:
        vc = None
        if guild is not None:
            vc = guild.voice_client
        elif current_vc is not None:
            vc = current_vc
            guild = current_vc.guild
        else:
            logging.warning("[VOICE] Nessun voice client attivo da disconnettere.")
            return

        if vc:
            logging.info(f"[VOICE] Disconnessione da: {guild.name}")
            try:
                await vc.disconnect(force=True)
                current_vc = None
            except discord.errors.ConnectionClosed as e:
                logging.error(
                    f"[VOICE] WebSocket chiuso durante disconnect — codice: {e.code}, motivo: {e.reason}"
                )
                current_vc = None
            except Exception as e:
                logging.error(f"[VOICE] Errore durante la disconnessione: {e}")
    finally:
        voice_lock.release()
        logging.debug("[VOICE_LOCK] Rilasciato (disconnect).")


def notify_bot_disconnected():
    """Stub per compatibilità — non più necessario."""
    pass
