# OriBruni Raspberry RECEIVER

Sistema completo per ricevere e gestire dati da dispositivi Meshtastic, specificamente progettato per il controllo radio in eventi di orienteering.

## 🚀 Installazione Docker (CONSIGLIATA)

**Nota Importante sul Processo di Build Docker:**
Le immagini Docker per i servizi personalizzati di questo progetto (`app` e `lcd-display`) sono ora pensate per essere buildate su una macchina esterna più potente (es. un server Linux) e pushate su un registro Docker (come GitHub Container Registry - GHCR). Il Raspberry Pi scaricherà (`pull`) queste immagini pre-compilate. Questo approccio accelera significativamente i tempi di deployment sul Raspberry Pi.
Per i dettagli completi sul nuovo flusso di build e deployment, consulta il file `DOCKER_README.md`.

### ⚡ Installazione Ultra-Rapida (per il Raspberry Pi - ambiente di runtime)

```bash
# 1. Installa Git (se necessario)
sudo apt update && sudo apt install -y git

# 2. Clona repository
git clone https://github.com/president1991/OriBruniRadioControls.git
cd OriBruniRadioControls/Meshtastic/Raspberry_RECEIVER

# 3. Configura password sicure
cp .env.example .env
nano .env  # Inserisci password generate con: openssl rand -base64 32

# 4. Esegui installazione automatica
chmod +x install-docker.sh && ./install-docker.sh

# 5. Riavvia e avvia
sudo reboot
cd ~/oribruni-receiver && make up
```

### 🔒 IMPORTANTE - Sicurezza

**⚠️ ATTENZIONE**: Non usare mai le password di esempio! Genera password sicure:

```bash
# Genera password sicure
openssl rand -base64 32
```

Configura il file `.env`:
```env
MYSQL_ROOT_PASSWORD=TuaPasswordRootSicura123!
MYSQL_PASSWORD=TuaPasswordUserSicura456!
MYSQL_DATABASE=OriBruniRadioControls
MYSQL_USER=meshdash
FLASK_ENV=production
LOG_LEVEL=INFO
```

### 🌐 Accesso Sistema Docker

Dopo l'installazione:
- **🖥️ Interfaccia Web**: `http://[IP_RASPBERRY]`
- **🗄️ phpMyAdmin**: `http://[IP_RASPBERRY]:8080/phpmyadmin`
- **📊 Database**: `[IP_RASPBERRY]:3306`

### 📱 Comandi Docker

```bash
make help          # Mostra tutti i comandi
make up            # Avvia sistema
make down          # Ferma sistema
make status        # Stato servizi
make logs          # Logs in tempo reale
make health        # Verifica sistema
make db-backup     # Backup database
make shell         # Accesso shell app
```

---

## 🛠️ Installazione Tradizionale (Alternativa)

### Prerequisiti
- Raspberry Pi 4 (4GB+ RAM)
- Raspberry Pi OS
- Dispositivo Meshtastic USB
- Display LCD I2C 20x4 (opzionale)

### Script Automatico
```bash
chmod +x install.sh
sudo ./install.sh
sudo reboot
```

### Installazione Manuale

#### 1. Dipendenze Sistema
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-pip python3-dev python3-venv \
    build-essential libmariadb-dev pkg-config i2c-tools python3-smbus \
    git curl wget mariadb-server mariadb-client nginx
```

#### 2. Abilita I2C
```bash
echo 'dtparam=i2c_arm=on' | sudo tee -a /boot/config.txt
sudo reboot
```

#### 3. Database MySQL
```bash
sudo mysql_secure_installation
sudo mysql -u root -p
```

```sql
CREATE DATABASE OriBruniRadioControls;
CREATE USER 'meshdash'@'localhost' IDENTIFIED BY 'password_sicura';
GRANT ALL PRIVILEGES ON OriBruniRadioControls.* TO 'meshdash'@'localhost';
FLUSH PRIVILEGES;
```

#### 4. Applicazione Python
```bash
sudo mkdir -p /opt/oribruni-receiver
cd /opt/oribruni-receiver
sudo cp -r /path/to/Raspberry_RECEIVER/* .
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## ⚙️ Configurazione

### File `config.ini`
```ini
[serial]
port = auto  # Auto-detection o porta specifica

[app]
log_file = meshdash.log
refresh_interval = 10000
log_level = INFO

[mysql]
host = localhost
port = 3306
user = meshdash
password = password_sicura
database = OriBruniRadioControls
autocommit = True
```

### Hardware Setup

#### Dispositivo Meshtastic
1. Collega via USB al Raspberry Pi
2. Verifica rilevamento: `lsusb` e `ls /dev/ttyUSB*`
3. Il sistema rileva automaticamente

#### Display LCD I2C (Opzionale)
1. **Collegamento**:
   - VCC → 5V (Pin 2)
   - GND → GND (Pin 6)
   - SDA → GPIO 2 (Pin 3)
   - SCL → GPIO 3 (Pin 5)

2. **Test**: `sudo i2cdetect -y 1`

---

## 🚀 Utilizzo

### Docker (Consigliato)
```bash
cd ~/oribruni-receiver
make up     # Avvia tutti i servizi
make status # Verifica stato
make logs   # Logs in tempo reale
```

### Tradizionale
```bash
cd /opt/oribruni-receiver
source venv/bin/activate
python server.py
```

### Servizi Systemd
```bash
sudo systemctl status oribruni-receiver
sudo systemctl start oribruni-receiver
sudo journalctl -u oribruni-receiver -f
```

---

## 📊 Interfaccia Web

### Dashboard
- **Visualizzazione Rete**: Grafico interattivo mesh
- **Lista Dispositivi**: Stato batteria e nodi
- **Real-time**: Aggiornamenti WebSocket

### API Esportazione
- **Endpoint**: `/export_punches`
- **Formato**: CSV
- **Filtri**: Unit ID, Last ID, Data/Ora

**Esempio**:
```
GET /export_punches?unitId=1&lastId=100&date=2025-05-27
```

---

## 🗄️ Database

### Tabella `messages`
- `id`: Chiave primaria
- `timestamp`: Data/ora ricezione
- `node_eui`: ID nodo mittente
- `field1`, `field2`, `field3`: Dati messaggio
- `raw`: Messaggio completo

### Tabella `punches`
- `id`: Chiave primaria
- `timestamp`: Data/ora
- `control`: Codice controllo
- `card_number`: Numero chip
- `punch_time`: Orario punzonatura

---

## 🔧 Manutenzione

### Backup
```bash
# Docker
make db-backup

# Tradizionale
/opt/oribruni-receiver/backup.sh
```

### Monitoraggio
```bash
# Docker
make status
make health
make logs

# Tradizionale
sudo systemctl status oribruni-receiver
htop
df -h
```

### Aggiornamenti
```bash
# Docker (con build remoto)
# 1. Sul server di build:
#    cd path/to/OriBruniRadioControls
#    git pull
#    cd Meshtastic/Raspberry_RECEIVER
#    # Ricostruisci e pusha le immagini Docker necessarie (app, lcd-display) su GHCR
#    # Esempio: docker buildx build --platform linux/arm64 -t ghcr.io/tuo-username/oribruni-receiver-app:latest --push -f Dockerfile .
#
# 2. Sul Raspberry Pi:
#    cd ~/OriBruniRadioControls/Meshtastic/Raspberry_RECEIVER # O dove hai clonato il progetto
#    git pull # Per aggiornare docker-compose.yml se necessario
#    sudo docker compose pull # Scarica le immagini aggiornate da GHCR
#    sudo docker compose up -d --force-recreate # Riavvia i servizi con le nuove immagini

# Tradizionale
cd /opt/oribruni-receiver # O il percorso della tua installazione tradizionale
git pull
source venv/bin/activate # Se usi un ambiente virtuale
pip install --upgrade -r requirements.txt
# Potrebbe essere necessario riavviare il servizio manualmente
```

---

## 🔒 Sicurezza

### 🚨 IMPORTANTE - Repository Pubblica

Se usi repository pubbliche:

1. **Non committare mai password**:
   ```bash
   # File protetti da .gitignore
   .env
   config.ini
   data/
   logs/
   backups/
   ```

2. **Usa file .env**:
   ```bash
   cp .env.example .env
   nano .env  # Inserisci password sicure
   ```

3. **Genera password sicure**:
   ```bash
   openssl rand -base64 32
   ```

### Firewall
```bash
sudo ufw allow ssh
sudo ufw allow 80
sudo ufw allow 443
sudo ufw enable
```

### Best Practices
- ✅ Password complesse (32+ caratteri)
- ✅ File .env locali non committati
- ✅ Firewall configurato
- ✅ Aggiornamenti regolari
- ❌ Mai password hardcoded

---

## 🐛 Risoluzione Problemi

### Meshtastic Non Rilevato
```bash
lsusb
ls /dev/ttyUSB*
sudo usermod -a -G dialout pi
```

### Database Non Raggiungibile
```bash
# Docker
make logs-db
docker compose exec mysql mysqladmin ping -u root -p

# Tradizionale
mysql -u meshdash -p OriBruniRadioControls
```

### Display LCD Non Funziona
```bash
sudo i2cdetect -y 1
lsmod | grep i2c
sudo modprobe i2c-dev
```

### Container Non Si Avvia
```bash
make logs-app
docker compose config
make rebuild
```

---

## 📚 Guide Complete

- **`INSTALLAZIONE_ONE_LINER.md`** - Installazione rapida
- **`INSTALLAZIONE_RAPIDA.md`** - Guida dettagliata
- **`DOCKER_README.md`** - Documentazione Docker
- **`SICUREZZA.md`** - Guida sicurezza completa

---

## 🤝 Contribuire

1. Fork repository
2. Crea branch: `git checkout -b feature/AmazingFeature`
3. Commit: `git commit -m 'Add AmazingFeature'`
4. Push: `git push origin feature/AmazingFeature`
5. Pull Request

---

## 📄 Licenza

Distribuito sotto licenza MIT. Vedi `LICENSE` per dettagli.

## 📞 Supporto

- **Issues**: [GitHub Issues](https://github.com/president1991/OriBruniRadioControls/issues)
- **Documentazione**: Guide complete nella directory del progetto

---

**OriBruni Radio Controls** - Sistema professionale per controllo radio eventi di orienteering con tecnologia Meshtastic.
