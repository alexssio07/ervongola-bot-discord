# ErVongola v5.0.0 (bot-discord)
![Logo](immagine_profilo.jpg)
Assistente virtuale chiamato Er Vongola, super potente e cazzuto in grado di annunciare l'entrata di uno specifico utente quando entra in determinati canali vocali. Può assistervi come farebbe una vera intelligenza artificiale attraverso la chat testuale "parla-con-l-ia" o attraverso la sua chat privata, cliccateci e leggete le istruzioni per poterlo usare.

- **Versione Python utilizzata:** arm64v8/python:3.11-slim

- **Librerie utilizzate:**
  aiohttp, discord.py, python-dotenv, nest-asyncio, logging, asyncio, gTTS, yt-dlp,
  requests, beautifulsoup4, feedparser, httpx, tiktoken, tqdm, pydantic

- **Altre dipendenze (gestite automaticamente):**
  aiosignal, attrs, frozenlist, multidict, yarl, idna, urllib3, certifi, charset-normalizer,
  sniffio, anyio, h11, httpcore, filelock, fsspec, Jinja2, MarkupSafe, typing_extensions,
  annotated-types, pydantic_core, soupsieve, propcache, colorama

- **Package interni separati:**
  generatoreblasfemie, utils, frasiconteggio, voice_manager


### COMANDI DA ESEGUIRE
- **ENTRA NELLA CARTELLA** >  ```cd Desktop/Discord```
Se necessario
- **ATTIVA L'AMBIENTE VIRTUALE** >  ```source venv/bin/activate```
(Verifica i pacchetti contenuti dentro il docker-file)
- **SCARICA TUTTI I PACCHETTI CON PIP** >  ```pip install -r .\requirements.txt```
- **AVVIA IL BOT** >  ```python bot-discord.py```

### DOCKER
- **COSTRUISCI L'IMMAGINE DOCKER** >  ```docker build -t bot-discord .```
- **AVVIA IL CONTAINER INSERENDO LE VARIABILI DI AMBIENTE** >  DISCORD_TOKEN recuperabile da [qua](https://discord.com/developers/applications), KEY_API_PERSONAL_AI, KEY_JWT_PERSONAL_AI (recuperabili da Ollama Client)


### Comandi creati per il bot Er-Vongola per Discord
- ``` /info``` (mostra le informazioni riguardo al bot)
- ``` /help``` (mostra aiuto e supporto su come utilizzarlo)
- ``` /nwt``` (ti legge n notizie ad alta voce prendendole dalla chat testuale ⁠💻news-tech💻 presente nella sezione NOTIZIE DI OGNI TIPO)
- ``` /nwg``` (ti legge n notizie ad alta voce prendendole dalla chat testuale ⁠📰news-generali📰 presente nella sezione NOTIZIE DI OGNI TIPO)
- ``` /nwv``` (ti legge n notizie ad alta voce prendendole dalla chat testuale ⁠🕹news-videogames🕹 presente nella sezione NOTIZIE DI OGNI TIPO)
- ``` /freevideogames```  (ti legge i giochi gratuiti del momento su Epic Games Store e/o Steam prendendole dalla chat testuale ⁠🕹free-videogames🕹 )
- ``` /suggerimento``` (Permette all'utente di inserire una nuova idea o implementazione per il bot, in sostanza se hai in mente un'idea.. scrivimela! E vedrò cosa posso fare)
- ``` /pvy``` (Permette di riprodurre un audio o musica da un link di YouTube)
- ``` /stop``` (Permette di fermare la musica o l'audio in riproduzione dal Bot)
- ``` /list_audio_commands``` (Mostra la lista dei file audio o comandi vocali disponibili dal Bot)
- ``` /play_audio_command``` (Riproduce un file audio secondo il suo ID, visualizzabile con il comando sopra citato)

<details>
  <summary>Avviso per le persone sensibili a parole o blasfemie</summary>
  
- ``` /bestemmia ``` > **Il Bot Er Vongola entrerà nel canale vocale e invierà un tot bestemmie causali**

</details>

![Copertina](ervongola-banner.jpeg)
