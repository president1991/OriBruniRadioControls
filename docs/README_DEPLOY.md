# OriBruniRadioControls - Deploy Automatico per Raspberry Pi

Sistema completo di installazione e configurazione automatica per dispositivi **LETTORI** e **RICEVITORI** su Raspberry Pi.

## 🎯 Panoramica Sistema

### 🔴 **LETTORI (RadioControls)**
- Leggono dati dalla seriale SportIdent
- Trasmettono via Internet E/O Meshtastic mesh
- Relay automatico messaggi Meshtastic
- Display OLED 0.96" I2C 128x64 per status
- Sincronizzazione temporale automatica

### 🔵 **RICEVITORI (Receivers)**
- Raccolgono dati da Meshtastic E Internet
- Database MySQL locale
- API REST `/getpunches`
- Dashboard web
- Server di sincronizzazione temporale

## 🚀 Installazione Rapida

### Prerequisiti
- Raspberry Pi 3/4 con Raspberry Pi OS
- Utente `pi` (NON root)
- Connessione Internet per installazione
- Hardware specifico per tipo dispositivo

### 1. Download e Preparazione
```bash
# Clona il repository
git clone https://github.com/president1991/OriBruniRadioControls.git
cd OriBruniRadioControls

# Rendi eseguibile il deployer
chmod +x deploy_raspberry.py
```

### 2. Deploy LETTORE
```bash
# Installa e configura un lettore
python3 deploy_raspberry.py reader reader-01

# Con avvio automatico
python3 deploy_raspberry.py reader reader-01 --auto-start
```

### 3. Deploy RICEVITORE
```bash
# Installa e configura un ricevitore
python3 deploy_raspberry.py receiver receiver-main

# Con avvio automatico
python3 deploy_raspberry.py receiver receiver-main --auto-start
```

## 🔧 Hardware Richiesto

### LETTORE
- **Raspberry Pi 3/4**
- **2x USB-Serial**: SportIdent + Meshtastic
- **Display OLED 0.96" I2C** (SSD1306, indirizzo 0x3C)
- **GPIO opzionali**: LED (pin 18), Buzzer (pin 19), Button (pin 20)
- **Alimentazione**: Power bank o alimentatore

### RICEVITORE
- **Raspberry Pi 3/4** (preferibilmente 4GB+ RAM)
- **1x USB-Serial**: Meshtastic
- **Connessione Internet**: WiFi o Ethernet
- **Storage**: MicroSD 32GB+ (Classe 10)
- **Display opzionale**: LCD 20x4 I2C

## 📁 Struttura File Generati

```
OriBruniRadioControls/
├── config/                    # Configurazioni dispositivo
│   └── device-name.json
├── logs/                      # Log applicazioni
│   ├── deploy.log
│   ├── health.log
│   └── backup.log
├── backup/                    # Backup automatici
│   └── backup_YYYYMMDD_HHMMSS.tar.gz
├── venv/                      # Ambiente Python virtuale
├── start_oribruni.sh         # Script avvio servizi
├── health_check.sh           # Health check sistema
├── backup.sh                 # Script backup manuale
└── *.service                 # File servizi systemd
```

## 🎮 Controllo Servizi

### Avvio Sistema
```bash
# Avvio automatico tutti i servizi
./start_oribruni.sh

# Avvio manuale servizi specifici
sudo systemctl start oribruni-sportident    # Solo lettori
sudo systemctl start oribruni-meshtastic    # Comune
sudo systemctl start oribruni-display       # Solo lettori
sudo systemctl start oribruni-web          # Solo ricevitori
```

### Monitoraggio
```bash
# Status servizi
systemctl status oribruni-*

# Log in tempo reale
journalctl -f -u oribruni-*

# Health check
./health_check.sh

# Statistiche display (solo lettori)
python3 oled_display.py --demo
```

### Controllo Remoto
```bash
# Stop tutti i servizi
sudo systemctl stop oribruni-*

# Riavvio servizi
sudo systemctl restart oribruni-*

# Disabilita avvio automatico
sudo systemctl disable oribruni-*
```

## 🖥️ Display OLED (Lettori)

### Modalità Display
- **STARTUP**: Schermata avvio (3 secondi)
- **STATUS**: Stato sistema (default)
- **PUNCH_INFO**: Ultima punzonatura (5 secondi)
- **TIME_SYNC**: Info sincronizzazione
- **ERROR**: Messaggi errore (10 secondi)
- **QR_CODE**: QR code info dispositivo
- **MENU**: Menu navigazione

### Informazioni Mostrate
- Nome dispositivo
- Ora corrente
- Stato connessioni (Mesh ●/○, Net ●/○, Sync ●/○)
- Contatore punzonature
- Temperatura CPU
- Ultima punzonatura (Card, Control, Time)

### Test Display
```bash
# Test base
python3 oled_display.py --device-name test-reader

# Demo completa
python3 oled_display.py --device-name test-reader --demo

# Indirizzo I2C personalizzato
python3 oled_display.py --device-name test-reader --i2c-address 0x3D
```

## 🕐 Sincronizzazione Temporale

### Funzionamento
1. **RICEVITORI** inviano timestamp ogni 5 minuti via Meshtastic
2. **LETTORI** ricevono timestamp e confrontano con orologio locale
3. Se differenza > 15 secondi → aggiornamento automatico orologio
4. Log di tutte le sincronizzazioni

### Configurazione
```json
{
  "time_sync": {
    "enabled": true,
    "max_drift": 15.0,
    "client_mode": true,        // Per lettori
    "server_mode": true,        // Per ricevitori
    "broadcast_interval": 300   // 5 minuti
  }
}
```

### Test Sincronizzazione
```bash
# Test time sync manager
python3 time_sync_manager.py

# Forza sincronizzazione (lettori)
curl -X POST http://localhost:8000/api/time_sync/force

# Status sincronizzazione
curl http://localhost:8000/api/time_sync/status
```

## 🔧 Configurazione Avanzata

### File Configurazione Dispositivo
```json
{
  "device": {
    "name": "reader-01",
    "type": "reader",
    "installation_date": "2025-01-08T10:00:00"
  },
  "sportident": {
    "port": "/dev/ttyUSB0",
    "baudrate": 38400,
    "timeout": 1.0
  },
  "meshtastic": {
    "port": "/dev/ttyUSB1",
    "baudrate": 115200,
    "relay_enabled": true
  },
  "display": {
    "type": "oled_128x64",
    "i2c_address": "0x3C",
    "rotation": 0,
    "contrast": 255
  },
  "gpio": {
    "led_pin": 18,
    "buzzer_pin": 19,
    "button_pin": 20
  }
}
```

### Personalizzazione Porte
```bash
# Verifica porte disponibili
ls -la /dev/ttyUSB*
ls -la /dev/ttyACM*

# Test connessione seriale
python3 -c "
import serial
ser = serial.Serial('/dev/ttyUSB0', 38400, timeout=1)
print('Porta OK:', ser.is_open)
ser.close()
"
```

### Configurazione I2C
```bash
# Abilita I2C
sudo raspi-config nonint do_i2c 0

# Scan dispositivi I2C
i2cdetect -y 1

# Test display OLED
python3 -c "
from luma.core.interface.serial import i2c
from luma.oled.device import ssd1306
serial = i2c(port=1, address=0x3C)
device = ssd1306(serial)
print('Display OK')
"
```

## 🔍 Troubleshooting

### Problemi Comuni

#### 1. Display OLED non funziona
```bash
# Verifica I2C abilitato
sudo raspi-config nonint get_i2c
# Output: 0 = abilitato, 1 = disabilitato

# Scan I2C
i2cdetect -y 1
# Cerca indirizzo 3c o 3d

# Test librerie
python3 -c "from luma.oled.device import ssd1306; print('OK')"
```

#### 2. Porte seriali non trovate
```bash
# Verifica porte
dmesg | grep tty

# Permessi utente
sudo usermod -a -G dialout pi
# Riavvia sessione

# Test porta
sudo chmod 666 /dev/ttyUSB0
```

#### 3. Servizi non si avviano
```bash
# Log dettagliato
journalctl -u oribruni-sportident -f

# Verifica configurazione
systemctl cat oribruni-sportident

# Test manuale
cd /home/pi/OriBruniRadioControls
source venv/bin/activate
python3 read_serial_improved.py
```

#### 4. Sincronizzazione temporale non funziona
```bash
# Verifica time sync
python3 -c "
from time_sync_manager import TimeSyncManager
sync = TimeSyncManager('test', 'reader')
print(sync.health_check())
"

# Log Meshtastic
journalctl -u oribruni-meshtastic -f | grep "TIME_SYNC"
```

### Log Utili
```bash
# Log sistema
sudo journalctl -f

# Log specifici OriBruni
journalctl -f -u oribruni-*

# Log deploy
tail -f logs/deploy.log

# Log health check
tail -f logs/health.log

# Log Python
tail -f logs/*.log
```

## 🔄 Manutenzione

### Backup Automatico
- **Giornaliero**: 02:00 (cron job)
- **Manuale**: `./backup.sh`
- **Retention**: 10 backup più recenti
- **Contenuto**: Configurazioni, script, database

### Health Check
- **Automatico**: Ogni 15 minuti
- **Manuale**: `./health_check.sh`
- **Controlli**: Servizi, hardware, spazio disco, memoria, temperatura

### Aggiornamenti
```bash
# Aggiorna codice
git pull origin main

# Reinstalla dipendenze
source venv/bin/activate
pip install -r requirements_improvements.txt

# Riavvia servizi
sudo systemctl restart oribruni-*
```

### Pulizia
```bash
# Pulizia log vecchi (automatica ogni domenica)
find logs/ -name "*.log" -mtime +7 -delete

# Pulizia backup vecchi
find backup/ -name "backup_*.tar.gz" -mtime +30 -delete

# Pulizia cache Python
find . -name "__pycache__" -type d -exec rm -rf {} +
find . -name "*.pyc" -delete
```

## 📊 Monitoraggio e API

### Endpoint API (Ricevitori)
```bash
# Status generale
curl http://localhost:8000/api/status

# Punzonature
curl http://localhost:8000/api/punches

# Time sync status
curl http://localhost:8000/api/time_sync/status

# Health check
curl http://localhost:8000/api/health
```

### Metriche Sistema
```bash
# CPU e memoria
htop

# Temperatura
vcgencmd measure_temp

# Spazio disco
df -h

# Processi OriBruni
ps aux | grep oribruni
```

## 🆘 Supporto

### Informazioni Sistema
```bash
# Info Raspberry Pi
cat /proc/device-tree/model

# Versione OS
lsb_release -a

# Info hardware
lscpu
free -h
lsusb
```

### Raccolta Log per Supporto
```bash
# Crea archivio completo per supporto
tar -czf oribruni-support-$(date +%Y%m%d_%H%M%S).tar.gz \
    logs/ config/ *.log \
    /var/log/syslog \
    /etc/systemd/system/oribruni-*.service

# Invia archivio per analisi
```

### Contatti
- **Repository**: https://github.com/president1991/OriBruniRadioControls
- **Issues**: Usa GitHub Issues per bug report
- **Documentazione**: Vedi ANALISI_COMPLETA_E_ROADMAP.md

---

## 📝 Note Finali

- **Durata Eventi**: Sistema ottimizzato per eventi 6-8 ore
- **Alimentazione**: Usa power bank di qualità per lettori
- **Backup**: Sempre fare backup prima di modifiche importanti
- **Test**: Testare sempre in ambiente controllato prima dell'evento
- **Monitoraggio**: Controllare health check durante l'evento

**Buona fortuna con i vostri eventi di orienteering! 🏃‍♂️🧭**
