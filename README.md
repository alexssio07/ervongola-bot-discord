# ErVongola v3.0 (bot-discord)
Assistente virtuale chiamato Er Vongola, super potente e cazzuto in grado di annunciare l'entrata di uno specifico utente quando entra in determinati canali vocali. Può assistervi come farebbe una vera intelligenza artificiale attraverso la chat testuale "parla-con-l-ia" o attraverso la sua chat privata, cliccateci e leggete le istruzioni per poterlo usare.


### COMANDI DA ESEGUIRE
- **ENTRA NELLA CARTELLA** >  ```cd Desktop/Discord```
Se necessario
- **ATTIVA L'AMBIENTE VIRTUALE** >  ```source venv/bin/activate```
(Verifica i pacchetti contenuti dentro il docker-file)
- **SCARICA TUTTI I PACCHETTI CON PIP** >  ```pip install -r .\requirements.txt```
- **AVVIA IL BOT** >  ```python bot-discord.py```

### DOCKER
- **COSTRUISCI L'IMMAGINE DOCKER** >  ```docker build -t bot-discord .```
- **AVVIA IL CONTAINER INSERENDO LE VARIABILI DI AMBIENTE** >  DISCORD_TOKEN recuperabile da [qua](https://discord.com/developers/applications/1205585120187261000/information), KEY_API_PERSONAL_AI, KEY_JWT_PERSONAL_AI (recuperabili da Ollama Client)
