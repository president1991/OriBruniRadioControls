# OriBruni Raspberry RECEIVER - Docker Setup

Guida completa per l'installazione e gestione del sistema OriBruni Receiver utilizzando Docker su Raspberry Pi.

## 🐳 Vantaggi di Docker

- **Isolamento**: Ogni servizio gira in un container separato
- **Portabilità**: Funziona su qualsiasi sistema con Docker
- **Scalabilità**: Facile aggiungere/rimuovere servizi
- **Backup**: Volumi persistenti per dati importanti
- **Aggiornamenti**: Update semplici senza conflitti
- **Monitoraggio**: Health checks integrati

## 📋 Prerequisiti

### Hardware
- Raspberry Pi 4 (4GB+ RAM consigliato)
- MicroSD 32GB+ Classe 10
- Dispositivo Meshtastic USB
- Display LCD I2C 20x4 (opzionale)

### Software
- Raspberry Pi OS (64-bit consigliato)
- Docker Engine
- Docker Compose

## 🛠️ Installazione Docker

**Nota:** Le istruzioni seguenti sono per installare Docker sul Raspberry Pi (ambiente di runtime) e su un eventuale server di build (es. un server Linux su OVH). Per i servizi personalizzati di questo progetto (`app` e `lcd-display`), il build delle immagini Docker è ora pensato per essere eseguito su una macchina più potente (server di build) e le immagini risultanti vengono scaricate sul Raspberry Pi.

### Installazione Automatica (per Raspberry Pi o Server di Build Linux Debian/Ubuntu based)
```bash
# Script ufficiale Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Aggiungi utente al gruppo docker
sudo usermod -aG docker $USER

# Installa Docker Compose
sudo apt install docker-compose-plugin

# Riavvia per applicare modifiche gruppo
sudo reboot
```

### Verifica Installazione
```bash
docker --version
docker compose version
```

## 🚀 Setup Progetto

### 1. Clonare il Repository
Sul Raspberry Pi e sul server di build, clona il repository:
```bash
# Esempio per la home directory
cd ~ 
git clone https://github.com/president1991/OriBruniRadioControls.git
cd OriBruniRadioControls/Meshtastic/Raspberry_RECEIVER/
```
Assicurati di essere nel branch corretto e di avere l'ultima versione del codice (`git pull`).

### 2. Creazione Directory Necessarie (sul Raspberry Pi)
Prima di avviare i container per la prima volta sul Raspberry Pi, crea le directory per i volumi persistenti e i log:
```bash
# Dalla directory Meshtastic/Raspberry_RECEIVER/
mkdir -p data/mysql logs/nginx backups nginx/ssl
```

### 3. Creazione File di Configurazione Essenziali (sul Raspberry Pi e sul Server di Build)
I seguenti file sono ignorati da Git (presenti nel `.gitignore`) e devono essere creati manualmente:

*   **`config.ini`**:
    *   **Sul Raspberry Pi:** Crea questo file nella directory `Meshtastic/Raspberry_RECEIVER/`. Deve contenere la configurazione specifica per l'ambiente del Raspberry Pi (porte seriali, configurazioni I2C, ecc.).
    *   **Sul Server di Build (OVH):** Anche qui, una versione di `config.ini` deve essere presente in `Meshtastic/Raspberry_RECEIVER/` *prima* di eseguire il build delle immagini Docker, poiché i `Dockerfile` per `app` e `lcd-display` lo copiano al loro interno.
*   **`.env`**:
    *   **Sul Raspberry Pi:** Crea questo file nella directory `Meshtastic/Raspberry_RECEIVER/`. Conterrà le variabili d'ambiente sensibili come le password di MySQL. Fai riferimento a `.env.example` per le variabili necessarie. Esempio:
        ```env
        MYSQL_ROOT_PASSWORD=la_tua_password_segreta_per_root
        MYSQL_PASSWORD=la_tua_password_segreta_per_meshdash
        # Altre variabili come FLASK_ENV, LOG_LEVEL, ecc.
        ```

### 4. Configurazione Permessi (sul Raspberry Pi)
```bash
# Dalla directory Meshtastic/Raspberry_RECEIVER/
# Rendi eseguibili gli script (se presenti e necessari)
# chmod +x scripts/backup.sh 

# Imposta permessi directory per i dati (esempio, potrebbe non essere necessario se Docker gestisce i permessi)
# sudo chown -R $USER:$USER . # O l'utente con cui gira Docker
# chmod 755 data logs backups
```

### 3. Configurazione I2C (per LCD)
```bash
# Abilita I2C
sudo raspi-config
# Interfacing Options -> I2C -> Enable

# Verifica I2C
sudo i2cdetect -y 1
```

## ⚙️ Configurazione

### File di Configurazione Principale
Modifica `config.ini`:
```ini
[serial]
port = auto  # Auto-detection dispositivo Meshtastic

[mysql]
host = mysql
port = 3306
user = meshdash
password = MeshDash2025!
database = OriBruniRadioControls
autocommit = True

[app]
log_file = logs/meshdash.log
refresh_interval = 5000
log_level = INFO
```

### Variabili di Ambiente
Crea file `.env` (opzionale):
```bash
# Database
MYSQL_ROOT_PASSWORD=PuhA7gWCrW
MYSQL_PASSWORD=MeshDash2025!

# Applicazione
FLASK_ENV=production
LOG_LEVEL=INFO

# Backup
RETENTION_DAYS=30
VERIFY_BACKUP=false
```

## 🚀 Flusso di Build e Deployment Ottimizzato (Build Remoto)

Per accelerare i tempi di deployment sul Raspberry Pi ed evitare lunghe compilazioni on-device, questo progetto ora utilizza un approccio di build multi-stage e build remoto.

### A. Build delle Immagini (su Server Esterno/Macchina di Sviluppo Potente, es. OVH)

1.  **Prerequisiti Server di Build:**
    *   Docker e Docker Buildx installati e configurati (vedi sezione "Installazione Docker").
    *   QEMU per il supporto multi-architettura (`sudo apt-get install qemu-user-static`).
    *   Codice sorgente del progetto clonato e aggiornato.
    *   File `config.ini` presente in `Meshtastic/Raspberry_RECEIVER/`.

2.  **Login a GitHub Container Registry (GHCR):**
    ```bash
    export YOUR_GITHUB_USERNAME="tuo-username-github" 
    export CR_PAT="tuo-personal-access-token-github"
    echo $CR_PAT | docker login ghcr.io -u $YOUR_GITHUB_USERNAME --password-stdin
    ```

3.  **Build e Push delle Immagini:**
    Naviga in `OriBruniRadioControls/Meshtastic/Raspberry_RECEIVER/` sul server di build.
    *   **Per il servizio `app`:**
        ```bash
        docker buildx build --platform linux/arm64 -t ghcr.io/$YOUR_GITHUB_USERNAME/oribruni-receiver-app:latest --push -f Dockerfile .
        ```
    *   **Per il servizio `lcd-display`:**
        ```bash
        docker buildx build --platform linux/arm64 -t ghcr.io/$YOUR_GITHUB_USERNAME/oribruni-lcd-display:latest --push -f Dockerfile.lcd .
        ```
    Sostituisci `$YOUR_GITHUB_USERNAME` con il tuo username GitHub (es. `president1991`).

### B. Deployment sul Raspberry Pi

1.  **Prerequisiti Raspberry Pi:**
    *   Docker e Docker Compose plugin installati.
    *   Codice sorgente del progetto clonato e aggiornato (in particolare `docker-compose.yml`).
    *   File `config.ini` e `.env` creati in `Meshtastic/Raspberry_RECEIVER/`.
    *   Directory per volumi (`data/mysql`, `logs/nginx`, `backups`) create.

2.  **Login a GHCR (Opzionale ma consigliato):**
    ```bash
    export YOUR_GITHUB_USERNAME="tuo-username-github" 
    export CR_PAT="tuo-personal-access-token-github"
    echo $CR_PAT | sudo docker login ghcr.io -u $YOUR_GITHUB_USERNAME --password-stdin
    ```

3.  **Scaricare le Immagini Aggiornate:**
    Naviga in `OriBruniRadioControls/Meshtastic/Raspberry_RECEIVER/` sul Raspberry Pi.
    ```bash
    sudo docker compose pull
    ```
    Questo scaricherà le immagini specificate nel `docker-compose.yml` da GHCR.

4.  **Avviare i Servizi:**
    ```bash
    sudo docker compose up -d
    ```

5.  **Verifica Stato:**
    ```bash
    sudo docker compose ps
    ```
    Controlla i log di un servizio specifico con `sudo docker compose logs nome-servizio`.

## 🏃 Avvio Sistema (Utilizzando Immagini Pre-Buildate)

Dopo aver completato i passaggi della sezione "Flusso di Build e Deployment Ottimizzato" (in particolare la parte B sul Raspberry Pi):

1.  **Avvio Completo:**
    ```bash
    # Dalla directory Meshtastic/Raspberry_RECEIVER/
    sudo docker compose up -d
    ```
2.  **Verifica Stato:**
    ```bash
    sudo docker compose ps
    ```
3.  **Prima Configurazione / Verifica Logs:**
    ```bash
    sudo docker compose logs -f app
    # Accedi al database se necessario (le credenziali sono nel tuo file .env)
    # docker compose exec mysql mysql -u root -pTUAPASSWORDROOT OriBruniRadioControls 
    ```

## 🌐 Accesso Servizi

### Interfacce Web
- **Applicazione Principale**: `http://[IP_RASPBERRY]` (se Nginx è configurato per la porta 80) o `http://[IP_RASPBERRY]:5000` (direttamente all'app)
- **phpMyAdmin**: `http://[IP_RASPBERRY]:8080` (l'immagine `linuxserver/phpmyadmin` usa la porta 80 internamente)
- **Database**: `[IP_RASPBERRY]:3306` (accessibile solo localmente o dalla rete Docker per default)

### Credenziali Database
- **Root**: `root` / `PuhA7gWCrW`
- **Applicazione**: `meshdash` / `MeshDash2025!`

## 📊 Monitoraggio

### Logs in Tempo Reale
```bash
# Tutti i servizi
docker compose logs -f

# Servizio specifico
docker compose logs -f app
docker compose logs -f mysql
docker compose logs -f nginx
```

### Stato Servizi
```bash
# Stato containers
docker compose ps

# Utilizzo risorse
docker stats

# Health checks
docker compose exec app curl -f http://localhost:5000/health
```

### Metriche Sistema
```bash
# Spazio disco
df -h

# Memoria
free -h

# Processi Docker
docker system df
```

## 💾 Backup e Restore

### Backup Manuale
```bash
# Backup database
docker compose --profile backup run --rm backup

# Backup completo (con volumi)
docker compose down
sudo tar -czf backup_$(date +%Y%m%d).tar.gz data/ logs/ backups/
```

### Backup Automatico
Il sistema esegue backup automatici ogni notte alle 02:00.

### Restore Database
```bash
# Stop applicazione
docker compose stop app

# Restore da backup
gunzip -c backups/oribruni_backup_YYYYMMDD_HHMMSS.sql.gz | \
docker compose exec -T mysql mysql -u root -pPuhA7gWCrW OriBruniRadioControls

# Restart applicazione
docker compose start app
```

## 🔧 Manutenzione

### Aggiornamento Sistema (con Build Remoto)

1.  **Build e Push Nuove Versioni delle Immagini:** Segui i passaggi della Sezione "A. Build delle Immagini" sul tuo server di build, usando eventualmente nuovi tag per le immagini (es. `:v1.1`) o sovrascrivendo il tag `:latest`. Se usi nuovi tag, aggiorna il file `docker-compose.yml` sul Raspberry Pi.

2.  **Sul Raspberry Pi:**
    *   Assicurati che il `docker-compose.yml` punti ai tag corretti.
    *   Scarica le immagini aggiornate:
        ```bash
        sudo docker compose pull
        ```
    *   Riavvia i servizi per usare le nuove immagini:
        ```bash
        sudo docker compose up -d --force-recreate # --force-recreate assicura che i container usino la nuova immagine
        ```
    *   Pulisci le immagini Docker vecchie e non utilizzate (opzionale):
        ```bash
        sudo docker image prune -f
        ```

### Pulizia Sistema
```bash
# Rimuovi containers stopped
docker container prune -f

# Rimuovi volumi non utilizzati
docker volume prune -f

# Pulizia completa
docker system prune -af
```

### Restart Servizi
```bash
# Restart singolo servizio
docker compose restart app

# Restart completo
docker compose down && docker compose up -d
```

## 🐛 Troubleshooting

### Problemi Comuni

#### Container non si avvia
```bash
# Verifica logs
docker compose logs app

# Verifica configurazione
docker compose config

# Rebuild immagine
docker compose build --no-cache app
```

#### Database non raggiungibile
```bash
# Verifica stato MySQL
docker compose exec mysql mysqladmin ping -u root -pPuhA7gWCrW

# Test connessione
docker compose exec app python -c "import mysql.connector; print('OK')"
```

#### Dispositivo Meshtastic non rilevato
```bash
# Verifica dispositivi USB
lsusb

# Verifica permessi
ls -la /dev/ttyUSB*

# Restart con privilegi
docker compose down
docker compose up -d
```

#### Display LCD non funziona
```bash
# Test I2C (assicurati sia abilitato via raspi-config)
sudo i2cdetect -y 1

# Verifica container LCD (usa il nome del servizio)
sudo docker compose logs lcd-display

# Nota: Il Dockerfile.lcd è stato aggiornato per includere 'smbus2' come dipendenza Python,
# il che dovrebbe risolvere problemi di ModuleNotFoundError.
# Se il problema persiste, verifica la connessione hardware e la configurazione I2C_ADDRESS nel .env.
```

### Debug Avanzato

#### Accesso Shell Container
```bash
# Shell applicazione
docker compose exec app bash

# Shell database
docker compose exec mysql bash

# Shell con root
docker compose exec --user root app bash
```

#### Verifica Rete Docker
```bash
# Lista reti
docker network ls

# Ispeziona rete
docker network inspect raspberry_receiver_oribruni-network

# Test connettività
docker compose exec app ping mysql
```

#### Analisi Performance
```bash
# Utilizzo risorse per container
docker stats --no-stream

# Logs performance
docker compose exec app top

# Spazio volumi
docker system df -v
```

## 🔒 Sicurezza

### Configurazione Firewall
```bash
# Abilita UFW
sudo ufw enable

# Regole base
sudo ufw allow ssh
sudo ufw allow 80/tcp
sudo ufw allow 8080/tcp
```

### Aggiornamenti Sicurezza
```bash
# Aggiorna sistema host
sudo apt update && sudo apt upgrade -y

# Aggiorna immagini Docker
docker compose pull
docker compose up -d
```

### Backup Configurazioni
```bash
# Backup configurazioni
tar -czf config_backup_$(date +%Y%m%d).tar.gz \
  config.ini docker-compose.yml nginx/ sql/
```

## 📈 Scaling e Performance

### Ottimizzazione MySQL
Modifica `docker-compose.yml`:
```yaml
mysql:
  command: >
    --default-authentication-plugin=mysql_native_password
    --innodb-buffer-pool-size=512M
    --max-connections=200
    --query-cache-size=64M
```

### Load Balancing (Futuro)
```yaml
app:
  deploy:
    replicas: 2
  
nginx:
  depends_on:
    - app
```

### Monitoraggio Avanzato
Aggiungi Prometheus/Grafana:
```yaml
prometheus:
  image: prom/prometheus
  ports:
    - "9090:9090"
```

## 📞 Supporto

### Logs Utili per Debug
```bash
# Salva logs per supporto
docker compose logs > debug_logs_$(date +%Y%m%d).txt

# Info sistema
docker version > system_info.txt
docker compose version >> system_info.txt
uname -a >> system_info.txt
```

### Comandi Diagnostici
```bash
# Health check completo
./scripts/health_check.sh

# Test connettività
./scripts/connectivity_test.sh

# Verifica configurazione
./scripts/config_validate.sh
```

---

**OriBruni Radio Controls** - Soluzione Docker professionale per controllo radio eventi di orienteering
