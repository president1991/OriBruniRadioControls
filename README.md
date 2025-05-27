# OriBruniRadioControls

## 27/05/2025 v4.0 - Docker Edition
### Implementazione completa soluzione Docker per Raspberry RECEIVER
Creata soluzione Docker professionale per il sistema OriBruni Receiver:
- **Docker Compose** con MySQL 8.0, phpMyAdmin, Nginx, App Python
- **Installazione automatica** con script `install-docker.sh`
- **Backup automatici** con retention 30 giorni
- **Monitoraggio integrato** con health checks
- **Makefile** con comandi semplificati (make up, make down, make logs, etc.)
- **SSL ready** con certificati auto-generati
- **Display LCD I2C** supportato con container dedicato
- **Installazione one-liner** da repository GitHub
- **Guide complete** di installazione e configurazione

### File aggiunti:
- `Meshtastic/Raspberry_RECEIVER/docker-compose.yml` - Orchestrazione servizi
- `Meshtastic/Raspberry_RECEIVER/Dockerfile` - Container applicazione
- `Meshtastic/Raspberry_RECEIVER/Dockerfile.lcd` - Container display LCD
- `Meshtastic/Raspberry_RECEIVER/Makefile` - Comandi gestione
- `Meshtastic/Raspberry_RECEIVER/install-docker.sh` - Script installazione automatica
- `Meshtastic/Raspberry_RECEIVER/INSTALLAZIONE_ONE_LINER.md` - Guida installazione rapida
- `Meshtastic/Raspberry_RECEIVER/INSTALLAZIONE_RAPIDA.md` - Guida dettagliata
- `Meshtastic/Raspberry_RECEIVER/DOCKER_README.md` - Documentazione tecnica
- `Meshtastic/Raspberry_RECEIVER/nginx/nginx.conf` - Configurazione reverse proxy
- `Meshtastic/Raspberry_RECEIVER/sql/init.sql` - Inizializzazione database
- `Meshtastic/Raspberry_RECEIVER/scripts/backup.sh` - Script backup automatico

### Installazione ultra-rapida:
```bash
sudo apt update && sudo apt install -y git
git clone https://github.com/president1991/OriBruniRadioControls.git
cd OriBruniRadioControls/Meshtastic/Raspberry_RECEIVER
chmod +x install-docker.sh && ./install-docker.sh
sudo reboot
cd ~/oribruni-receiver && make up
```

## 17/05/2025 v3.1
Modifiche su MeshDash

## 07/05/2025 v3.0
Spostata la logica Meshtastic in un servizio a parte per la gestione completa.
Aggiornamenti Vari

## 04/05/2025 v2.6
Modifica script per fare in modo che se anche le porte usb vengono scambiate le porte seriali si aprano correttamente.  
Aggiunta illuminazione led e segnale acustico all'avvio del punto radio.  
Controlli e verifiche funzionamento.  

## 30/04/2025 v2.5
###
Aggiunta esportazione csv.  
Agginto log su file separato.  
Modifiche minori
## 29/04/2025 v2.2
### 
Aggiunto invio dati su interfaccia meshtastic.  
Test invio online OK  
Test invio Meshtastic OK  
Da implementare lettura meshtastic su OriBoss
### 

## 28/04/2025 - v1.4
### Modifica invio telemetria raspberry 
Ora invia anche dei dati (temperatura, utilizzo cpu, ram)
### Modifica Callhome
Modifica per ridurre il consumo di dati

## 22/04/2025 - v1.3
Aggiunta riduzione consumo dati mobili.  
Verifica funzionamento script per lettura SIAC anche in modalità AIR+
