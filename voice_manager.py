import asyncio
import datetime
import logging
import discord
from typing import Optional

current_vc: Optional[discord.VoiceClient] = None
_lock = asyncio.Lock()  # unico lock globale per serializzare operazioni voice
MAX_RETRIES = 5
BASE_DELAY = 2.0


async def connect_to_channel(
    channel: discord.VoiceChannel,
    botDiscord: discord.Client,
    interaction: discord.Interaction,
) -> Optional[discord.VoiceClient]:
    """
    Connetti il bot al canale vocale. Se è già connesso a un altro canale,
    lo sposta sul nuovo. Restituisce il VoiceClient attivo.
    """
    global current_vc
    actual_datetime_string = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    async with _lock:
        # Se già connesso allo stesso canale → ritorna
        # print(
        #     f"current_vc: {current_vc} and current_vc.is_connected(): {current_vc and current_vc.is_connected()}"
        # )
        if (
            current_vc
            and current_vc.is_connected()
            or (current_vc and current_vc.channel.id == channel.id)
        ):
            logging.info(
                f"[{actual_datetime_string}] [VM] Già connesso a {channel.name}"
            )
            return current_vc

        # Se connesso a un altro canale → disconnetti prima
        if current_vc and current_vc.is_connected():
            try:
                logging.info(
                    f"[{actual_datetime_string}] [VM] Disconnessione da {current_vc.channel.name} prima di riconnettere..."
                )
                await current_vc.disconnect(force=True)
                await asyncio.sleep(1.5)
            except Exception as e:
                logging.warning(f"[VM] Errore durante la disconnessione VC: {e}")
            current_vc = None

        # Tenta connessione con retry/backoff
        print(f"current_vc: {current_vc}")
        attempt = 0
        while attempt < MAX_RETRIES:
            try:
                await asyncio.sleep(BASE_DELAY * (attempt + 1))
                current_vc = await channel.connect(reconnect=False)
                logging.info(
                    f"[{actual_datetime_string}] [VM] Connesso a {channel.name}"
                )
                return current_vc
            except Exception as e:
                code = getattr(e, "code", None)
                logging.warning(
                    f"[VM] Tentativo {attempt+1} fallito: {e} (code={code})"
                )

                # Gestione 4006 → resetta e ritenta
                if "4006" in str(e) or code == 4006:
                    logging.warning(
                        "[VM] Errore 4006 rilevato, reset connessione vocale"
                    )
                    try:
                        if current_vc:
                            await current_vc.disconnect(force=True)
                    except Exception:
                        pass
                    current_vc = None

                attempt += 1
                await asyncio.sleep(BASE_DELAY * (attempt + 1) * 2)

        logging.error(
            f"[VM] Impossibile connettersi al canale {channel.name} dopo {MAX_RETRIES} tentativi."
        )
        return None


async def disconnect_current_vc():
    """
    Disconnette completamente il VC corrente, se esiste.
    """
    global current_vc
    actual_datetime_string = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    async with _lock:
        if not current_vc:
            return
        try:
            if current_vc.is_connected():
                await current_vc.disconnect(force=True)
                await asyncio.sleep(1)
                logging.info(
                    f"[{actual_datetime_string}] [VM] Disconnesso correttamente dal canale vocale"
                )
        except Exception as e:
            logging.warning(
                f"[{actual_datetime_string}] [VM] Errore durante disconnect: {e}"
            )
        finally:
            current_vc = None


def get_current_vc() -> Optional[discord.VoiceClient]:
    return current_vc
