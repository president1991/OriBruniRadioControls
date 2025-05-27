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

### Installazione Automatica
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

### 1. Preparazione Directory
```bash
# Crea struttura directory
mkdir -p ~/oribruni-receiver/{data/mysql,logs/nginx,backups,nginx/ssl}
cd ~/oribruni-receiver

# Copia file progetto
cp -r /path/to/Raspberry_RECEIVER/* .
```

### 2. Configurazione Permessi
```bash
# Rendi eseguibili gli script
chmod +x scripts/backup.sh

# Imposta permessi directory
sudo chown -R $USER:$USER .
chmod 755 data logs backups
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

## 🏃 Avvio Sistema

### Avvio Completo
```bash
# Avvia tutti i servizi
docker compose up -d

# Verifica stato
docker compose ps
```

### Avvio Servizi Specifici
```bash
# Solo servizi essenziali
docker compose up -d mysql app nginx

# Con phpMyAdmin
docker compose up -d mysql phpmyadmin app nginx

# Con LCD display
docker compose up -d mysql app nginx lcd-display
```

### Prima Configurazione
```bash
# Verifica logs
docker compose logs -f app

# Accedi al database
docker compose exec mysql mysql -u root -pPuhA7gWCrW OriBruniRadioControls
```

## 🌐 Accesso Servizi

### Interfacce Web
- **Applicazione Principale**: `http://[IP_RASPBERRY]:80`
- **phpMyAdmin**: `http://[IP_RASPBERRY]:8080/phpmyadmin`
- **Database**: `[IP_RASPBERRY]:3306`

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

### Aggiornamento Sistema
```bash
# Pull nuove immagini
docker compose pull

# Rebuild e restart
docker compose up -d --build

# Pulizia immagini vecchie
docker image prune -f
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
# Test I2C
sudo i2cdetect -y 1

# Verifica container LCD
docker compose logs lcd-display

# Test manuale
docker compose exec lcd-display python -c "from RPLCD.i2c import CharLCD; print('OK')"
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
