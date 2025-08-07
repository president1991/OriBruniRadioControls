# 🏃‍♂️ OriBruniRadioControls

Sistema completo per gestione punzonature elettroniche negli eventi di orienteering, con supporto **SportIdent**, **Meshtastic mesh network** e **sincronizzazione temporale automatica**.

## 🎯 Panoramica

### 🔴 **LETTORI (RadioControls)**
- Lettura automatica punzonature SportIdent
- Trasmissione via Meshtastic mesh + Internet
- Display OLED 0.96" I2C per status real-time
- Sincronizzazione temporale automatica
- Relay messaggi mesh per estendere copertura

### 🔵 **RICEVITORI (Receivers)**  
- Raccolta dati da Meshtastic + Internet
- Database MySQL con API REST
- Dashboard web per monitoraggio
- Server sincronizzazione temporale
- Backup automatici

## 🚀 Installazione Rapida

### Prerequisiti
- **Raspberry Pi 3/4** con Raspberry Pi OS
- **Hardware specifico** (vedi documentazione)
- **Connessione Internet** per installazione

### Deploy Automatico
```bash
# 1. Scarica il progetto
git clone https://github.com/president1991/OriBruniRadioControls.git
cd OriBruniRadioControls

# 2. Collega hardware (qualsiasi porta USB)

# 3. Deploy automatico
# Per LETTORE:
python3 scripts/deploy_raspberry.py reader reader-01 --auto-start

# Per RICEVITORE:
python3 scripts/deploy_raspberry.py receiver receiver-main --auto-start
```

**Il sistema rileva automaticamente le porte e configura tutto!** 🎉

## 📁 Struttura Progetto

```
OriBruniRadioControls/
├── 📖 docs/                          # Documentazione completa
│   ├── GUIDA_RAPIDA_INSTALLAZIONE.md # Guida installazione 5 minuti
│   ├── README_DEPLOY.md              # Documentazione deploy dettagliata
│   └── ANALISI_COMPLETA_E_ROADMAP.md # Analisi tecnica e roadmap
├── 🔧 scripts/                       # Script installazione e deploy
│   ├── deploy_raspberry.py           # Deploy automatico completo
│   ├── install_improvements.sh       # Script installazione Linux
│   └── release_ports.sh              # Utility rilascio porte
├── 🧠 src/                           # Codice sorgente
│   ├── core/                         # Moduli core
│   │   ├── config_manager.py         # Gestione configurazioni
│   │   ├── database_manager.py       # Gestione database thread-safe
│   │   ├── thread_safe_buffer.py     # Buffer condivisi sicuri
│   │   └── time_sync_manager.py      # Sincronizzazione temporale mesh
│   ├── hardware/                     # Moduli hardware
│   │   └── oled_display.py           # Display OLED 128x64 per lettori
│   └── services/                     # Servizi principali
├── ⚙️ config_templates/              # Template configurazioni
│   ├── config.ini                    # Configurazione base
│   └── requirements_improvements.txt # Dipendenze Python
├── 📊 Meshtastic/                    # Moduli Meshtastic esistenti
└── 📜 File legacy                    # File originali del progetto
```

## 🔧 Hardware Supportato

### LETTORI
- **Raspberry Pi 3/4**
- **SportIdent**: Adattatore seriale (baudrate 38400)
- **Meshtastic**: Modulo LoRa con seriale (baudrate 115200)
- **Display OLED**: 0.96" I2C SSD1306 (indirizzo 0x3C)
- **GPIO opzionali**: LED, Buzzer, Pulsanti

### RICEVITORI
- **Raspberry Pi 3/4** (preferibilmente 4GB+ RAM)
- **Meshtastic**: Modulo LoRa con seriale
- **Connessione Internet**: WiFi o Ethernet
- **Storage**: MicroSD 32GB+ Classe 10

## 📖 Documentazione

### 🚀 **Per Iniziare Subito**
- **[GUIDA RAPIDA](docs/GUIDA_RAPIDA_INSTALLAZIONE.md)** - Installazione in 5 minuti
- **[README DEPLOY](docs/README_DEPLOY.md)** - Documentazione completa deploy

### 🔍 **Per Approfondire**
- **[ANALISI COMPLETA](docs/ANALISI_COMPLETA_E_ROADMAP.md)** - Analisi tecnica dettagliata
- **[Codice Sorgente](src/)** - Moduli documentati

## ✨ Caratteristiche Principali

### 🔄 **Deploy Completamente Automatico**
- Rilevamento automatico hardware Raspberry Pi
- Installazione dipendenze sistema e Python
- Configurazione I2C, GPIO, permessi
- Creazione servizi systemd personalizzati
- Setup backup e monitoraggio automatici

### 🖥️ **Display OLED Intelligente** (Lettori)
- Schermata status con connessioni (●/○)
- Info punzonature in tempo reale
- QR code per debug rapido
- Menu navigazione e configurazione
- Gestione errori con auto-dismiss

### ⏰ **Sincronizzazione Temporale Mesh**
- RICEVITORI inviano timestamp ogni 5 minuti
- LETTORI aggiornano orologio se drift > 15 secondi
- Completamente automatico via Meshtastic
- Log dettagliati di tutte le sincronizzazioni

### 🔒 **Sicurezza e Affidabilità**
- Thread safety per tutti i buffer condivisi
- Context managers per connessioni database
- Gestione robusta errori con retry automatici
- Servizi systemd isolati con sicurezza
- Backup automatici giornalieri

### 📊 **Monitoraggio Completo**
- Health check automatici ogni 15 minuti
- Dashboard web per ricevitori
- API REST `/getpunches` per integrazioni
- Log strutturati e rotazione automatica
- Statistiche performance in tempo reale

## 🎮 Utilizzo

### Avvio Sistema
```bash
# Avvio automatico tutti i servizi
./start_oribruni.sh

# Monitoraggio log
journalctl -f -u oribruni-*

# Health check
./health_check.sh
```

### API REST (Ricevitori)
```bash
# Status generale
curl http://raspberry-ip:8000/api/status

# Punzonature
curl http://raspberry-ip:8000/api/punches

# Dashboard web
http://raspberry-ip:8000
```

## 🔍 Troubleshooting

### Problemi Comuni
- **Porte seriali**: Il sistema rileva automaticamente, non serve configurazione
- **Display OLED**: Verifica I2C con `i2cdetect -y 1`
- **Permessi**: Usa sempre utente `pi`, mai `root`
- **Log dettagliati**: `tail -f logs/deploy.log`

### Supporto
- **Issues**: [GitHub Issues](https://github.com/president1991/OriBruniRadioControls/issues)
- **Documentazione**: Cartella `docs/`
- **Log supporto**: `tar -czf support.tar.gz logs/ config/`

## 🏆 Ottimizzato per Eventi

- **Durata**: Testato per eventi 6-8 ore continue
- **Alimentazione**: Configurato per power bank
- **Recovery**: Riavvio automatico servizi in caso errore
- **Performance**: Uso ottimizzato memoria/CPU
- **Deploy rapido**: Installazione pre-evento in 5 minuti

## 📝 Licenza

Progetto open source per la comunità di orienteering italiana.

---

**🏃‍♂️ Buona fortuna con i vostri eventi di orienteering! 🧭**

*Sistema sviluppato e testato per OriBruni ASD*
