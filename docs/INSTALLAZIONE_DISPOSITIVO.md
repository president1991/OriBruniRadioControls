# 📱 Installazione Dispositivo OriBruni RadioControls

Guida completa per l'installazione e configurazione di un nuovo dispositivo lettore con verifica online delle credenziali.

## 🎯 Panoramica

Il sistema di installazione dispositivo gestisce:
- ✅ **Verifica online** delle credenziali (nome + pkey)
- ✅ **Configurazione automatica** del dispositivo locale
- ✅ **Integrazione** con il sistema di deploy esistente
- ✅ **Test di connettività** alle API remote
- ✅ **Salvataggio sicuro** delle configurazioni

## 🚀 Installazione Rapida

### Prerequisiti
- **Connessione Internet** attiva
- **Credenziali dispositivo** fornite dall'amministratore:
  - Nome dispositivo (es. `OBRC_004`)
  - Chiave dispositivo (es. `936D4854BB4E5`)

### Installazione Interattiva
```bash
# 1. Esegui lo script di installazione
python3 install_device.py

# 2. Inserisci i dati quando richiesto
# Nome dispositivo: OBRC_004
# Chiave dispositivo: 936D4854BB4E5

# 3. Conferma i dati
# Il sistema verificherà online le credenziali

# 4. Procedi con il deploy
python3 scripts/deploy_raspberry.py reader OBRC_004 --auto-start
```

### Installazione con Parametri
```bash
# Installazione diretta con credenziali
python3 install_device.py --name OBRC_004 --pkey 936D4854BB4E5

# Solo verifica online (senza salvare)
python3 install_device.py --name OBRC_004 --pkey 936D4854BB4E5 --verify-only

# Con URL API personalizzato
python3 install_device.py --api-url https://custom.domain.com/api/
```

## 🔍 Test e Verifica

### Test Connettività API
```bash
# Test completo con configurazione locale
python3 test_api_connection.py

# Test solo connettività (no credenziali)
python3 test_api_connection.py --ping-only

# Test con credenziali specifiche
python3 test_api_connection.py --name OBRC_004 --pkey 936D4854BB4E5
```

### Verifica Configurazione
```bash
# Controlla file di configurazione
cat config/config.ini

# Controlla info dispositivo
cat config/OBRC_004.json

# Controlla log di installazione
tail -f logs/install.log
```

## 📁 File Creati

### `config/config.ini`
Configurazione principale del sistema con sezioni aggiornate:
```ini
[DEVICE]
name = OBRC_004
pkey = 936D4854BB4E5
installation_date = 2024-01-15 10:30:45
verified_online = true

[REMOTE]
device_name = OBRC_004
device_pkey = 936D4854BB4E5
url = https://orienteering.services/radiocontrol/receive_data.php

[CALLHOME]
device_name = OBRC_004
device_pkey = 936D4854BB4E5
url = https://orienteering.services/radiocontrol/callhome.php
```

### `config/{DEVICE_NAME}.json`
Informazioni dettagliate del dispositivo:
```json
{
  "device": {
    "name": "OBRC_004",
    "pkey": "936D4854BB4E5",
    "installation_date": "2024-01-15 10:30:45",
    "verified_online": true,
    "installer_version": "1.0.0"
  },
  "api_endpoints": {
    "base_url": "https://orienteering.services/radiocontrol/",
    "callhome": "callhome.php",
    "receive_data": "receive_data.php"
  },
  "installation_info": {
    "python_version": "3.9.2",
    "platform": "linux",
    "working_directory": "/home/pi/OriBruniRadioControls"
  }
}
```

## 🔧 API Utilizzate

### Verifica Dispositivo
Il sistema utilizza due metodi per verificare le credenziali:

#### 1. callhome.php (Metodo Principale)
```bash
POST https://orienteering.services/radiocontrol/callhome.php
Content-Type: application/json

{
  "name": "OBRC_004",
  "pkey": "936D4854BB4E5",
  "action": "keepalive",
  "timestamp": "2024-01-15T10:30:45.000Z",
  "client_version": "installer-1.0.0",
  "system_status": {
    "cpu_percent": 0.0,
    "memory_percent": 0.0,
    ...
  }
}
```

**Risposte:**
- `200 + {"status":"success"}` → Credenziali valide ✅
- `401` → Credenziali non valide ❌
- `422` → Formato dati non valido ⚠️

#### 2. radiocontrol_data.php (Metodo Alternativo)
```bash
GET https://orienteering.services/radiocontrol/radiocontrol_data.php
```

Cerca il dispositivo nella lista restituita confrontando `name` e `pkey`.

## 🛠️ Opzioni Avanzate

### Parametri Disponibili
```bash
python3 install_device.py --help

Options:
  --name NAME           Nome del dispositivo (es. OBRC_004)
  --pkey PKEY          Chiave del dispositivo (es. 936D4854BB4E5)
  --verify-only        Solo verifica online, non salva configurazione
  --api-url URL        URL base delle API (default: https://orienteering.services/radiocontrol/)
  --timeout SECONDS    Timeout richieste HTTP (default: 10)
  --retries NUMBER     Numero massimo di tentativi (default: 3)
```

### Configurazione URL API Personalizzato
```bash
# Per ambienti di test o installazioni personalizzate
python3 install_device.py \
  --name OBRC_004 \
  --pkey 936D4854BB4E5 \
  --api-url https://test.orienteering.services/radiocontrol/ \
  --timeout 15 \
  --retries 5
```

## 🔍 Troubleshooting

### Errori Comuni

#### ❌ "Dispositivo non trovato o credenziali non valide"
**Cause possibili:**
- Nome dispositivo errato
- Chiave (pkey) errata  
- Dispositivo non registrato nel sistema remoto
- Problemi di connessione internet

**Soluzioni:**
1. Verifica le credenziali con l'amministratore
2. Testa la connettività: `python3 test_api_connection.py --ping-only`
3. Controlla i log: `tail -f logs/install.log`

#### ❌ "Errore connessione"
**Cause possibili:**
- Nessuna connessione internet
- Firewall che blocca le richieste HTTPS
- Server API temporaneamente non disponibile

**Soluzioni:**
1. Verifica connessione: `ping orienteering.services`
2. Testa HTTPS: `curl -I https://orienteering.services/radiocontrol/callhome.php`
3. Controlla proxy/firewall

#### ❌ "Timeout"
**Cause possibili:**
- Connessione internet lenta
- Server API sovraccarico

**Soluzioni:**
1. Aumenta timeout: `--timeout 30`
2. Riprova più tardi
3. Usa più tentativi: `--retries 5`

#### ⚠️ "Test configurazione non completamente riuscito"
**Cause possibili:**
- Configurazione salvata ma problemi di connettività
- API temporaneamente non disponibili

**Soluzioni:**
1. La configurazione è comunque salvata
2. Testa successivamente: `python3 test_api_connection.py`
3. Procedi con il deploy

### Log e Debug

#### File di Log
```bash
# Log installazione
tail -f logs/install.log

# Log test API
python3 test_api_connection.py --verbose

# Log sistema (dopo deploy)
journalctl -f -u oribruni-*
```

#### Verifica Manuale API
```bash
# Test ping API
curl -I https://orienteering.services/radiocontrol/callhome.php

# Test lista dispositivi
curl https://orienteering.services/radiocontrol/radiocontrol_data.php

# Test keepalive manuale
curl -X POST https://orienteering.services/radiocontrol/callhome.php \
  -H "Content-Type: application/json" \
  -d '{"name":"OBRC_004","pkey":"936D4854BB4E5","action":"keepalive","timestamp":"2024-01-15T10:30:45.000Z","client_version":"manual-test","system_status":{"cpu_percent":0}}'
```

## 🔄 Integrazione con Deploy

### Workflow Completo
```bash
# 1. Installazione dispositivo
python3 install_device.py

# 2. Deploy automatico (lettore)
python3 scripts/deploy_raspberry.py reader OBRC_004 --auto-start

# 3. Verifica funzionamento
./health_check.sh

# 4. Monitoraggio
journalctl -f -u oribruni-*
```

### Configurazioni Ereditate
Il sistema di deploy eredita automaticamente:
- ✅ Nome dispositivo dalla sezione `[DEVICE]`
- ✅ Credenziali dalla sezione `[REMOTE]` e `[CALLHOME]`
- ✅ URL API configurati
- ✅ Parametri di timeout e retry

## 🔐 Sicurezza

### Gestione Credenziali
- Le **pkey** sono salvate in chiaro nel file di configurazione
- Il file `config.ini` ha permessi `600` (solo proprietario)
- Le credenziali sono trasmesse solo via HTTPS
- Nessuna credenziale è salvata nei log

### Best Practices
1. **Non condividere** i file di configurazione
2. **Backup sicuro** delle configurazioni: `tar -czf backup.tar.gz config/`
3. **Rotazione pkey** periodica (coordinare con amministratore)
4. **Monitoraggio accessi** tramite log del server remoto

## 📚 Riferimenti

### Script Correlati
- `install_device.py` - Installazione dispositivo principale
- `test_api_connection.py` - Test connettività e credenziali
- `scripts/deploy_raspberry.py` - Deploy automatico sistema
- `src/core/config_manager.py` - Gestione configurazioni

### Documentazione API
- [Documentazione API completa](../API_DOCUMENTATION.md) - Tutte le API disponibili
- [Sistema identificazione](SISTEMA_IDENTIFICAZIONE_E_DATABASE.md) - Database remoto e chiavi

### Guide Correlate
- [Guida rapida installazione](GUIDA_RAPIDA_INSTALLAZIONE.md) - Setup completo 5 minuti
- [README deploy](README_DEPLOY.md) - Deploy automatico dettagliato
- [Analisi completa](ANALISI_COMPLETA_E_ROADMAP.md) - Architettura sistema

---

## 🆘 Supporto

### Contatti
- **Issues GitHub**: [OriBruniRadioControls Issues](https://github.com/president1991/OriBruniRadioControls/issues)
- **Documentazione**: Cartella `docs/`

### Informazioni per Supporto
```bash
# Crea pacchetto supporto
tar -czf support_$(date +%Y%m%d_%H%M%S).tar.gz \
  logs/ config/ *.py docs/

# Include:
# - Log di installazione e test
# - Configurazioni (senza credenziali sensibili)
# - Script utilizzati
# - Documentazione
```

---

**🏃‍♂️ Sistema sviluppato per la comunità di orienteering italiana 🧭**
