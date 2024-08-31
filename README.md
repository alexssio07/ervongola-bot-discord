# ErVongola v4.6 (bot-discord)
![Logo](immagine_profilo.jpg)
Assistente virtuale chiamato Er Vongola, super potente e cazzuto in grado di annunciare l'entrata di uno specifico utente quando entra in determinati canali vocali. Può assistervi come farebbe una vera intelligenza artificiale attraverso la chat testuale "parla-con-l-ia" o attraverso la sua chat privata, cliccateci e leggete le istruzioni per poterlo usare.

- **Versione Python utilizzata 3.10.2 64bit**
- **Librerie utilizzate Discord API, dotenv, os, ollama, json, streamlit, nest_asyncio, logging, yt-dlp, re, asyncio, gTTS, uuid, random, SmartScraperGraph**
- **Package interni separati generatoreblasfemie, utils, frasiconteggio**


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
- ``` /ping ``` > **It will show the ping latecy of the bot**
- ``` /info_help ``` > **Mostra aiuto e supporto riguardo al bot**
- ``` /avvisadarklord ``` > **Manda un messaggio a DarkLord per comunicargli che siamo online...**
- ``` /bestemmia ``` > **Il Bot Er Vongola entrerà nel canale vocale e invierà un tot bestemmie causali**
- ``` /barzelletta ``` > **Genera una barzelletta, entra nel canale vocale e la riproduce**
- ``` /freddura ``` > **Genera una freddura/battuta, entra nel canale vocale e la riproduce**
- ``` /newstech ``` > **Entra nel canale vocale dove ti trovi e ti legge tot -> 'countnews' notizie riguardo l'ambito della tecnologia**
- ``` /newsgeneral ``` > **Entra nel canale vocale dove ti trovi e ti legge 'n' notizie riguardo l'ambito generale**
- ``` /newsvideogames ``` > **Entra nel canale vocale dove ti trovi e ti legge 'n' notizie riguardo l'ambito dei videogames**
- ``` /suggerimento ``` > **Invia un suggerimento per una nuova funzione**
- ``` /play_music ``` > **Riproduce audio da YouTube nel canale vocale con un volume di default di 100% o volume impostato**
- ``` /stop ``` > **Ferma la riproduzione audio e disconnette il bot dal canale vocale**


![Copertina](ervongola-banner.jpeg)
