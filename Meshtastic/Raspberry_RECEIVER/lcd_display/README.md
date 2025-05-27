# Display LCD 20x4 I2C per OriBruni Receiver

Questo progetto aggiunge il supporto per un display LCD 20x4 con interfaccia I2C al sistema OriBruni Receiver, mostrando l'IP privato del Raspberry Pi e altre informazioni utili.

## Hardware Richiesto

- Display LCD 20x4 con modulo I2C (PCF8574)
- Raspberry Pi con GPIO
- 4 cavi jumper per i collegamenti

## Collegamento Hardware

| LCD Pin | Funzione | Raspberry Pi Pin | Nome GPIO |
|---------|----------|------------------|-----------|
| GND     | Massa    | Pin 6            | GND       |
| VCC     | 5V       | Pin 2 o 4        | 5V        |
| SDA     | Dati I2C | Pin 3            | GPIO 2    |
| SCL     | Clock I2C| Pin 5            | GPIO 3    |

## Installazione

### 1. Preparazione del Sistema

Prima di tutto, assicurati che l'I2C sia abilitato sul Raspberry Pi:

```bash
sudo raspi-config
```

Vai su: `Interfacing Options` → `I2C` → `Enable`

Riavvia il sistema dopo aver abilitato l'I2C.

### 2. Installazione Automatica

Entra nella cartella del progetto LCD ed esegui lo script di installazione:

```bash
cd lcd_display
chmod +x install.sh
./install.sh
```

### 3. Installazione Manuale

Se preferisci installare manualmente:

```bash
# Aggiorna il sistema
sudo apt-get update

# Installa i2c-tools
sudo apt-get install -y i2c-tools python3-pip

# Installa le dipendenze Python
pip3 install -r requirements.txt

# Rendi eseguibili gli script
chmod +x lcd_display.py test_i2c.py
```

## Test e Configurazione

### 1. Test della Connessione I2C

Verifica che il display sia collegato correttamente:

```bash
python3 test_i2c.py
```

Questo script:
- Verifica che i2c-tools siano installati
- Scansiona il bus I2C per trovare dispositivi collegati
- Testa la connessione con il display LCD
- Mostra l'indirizzo I2C del display

### 2. Test del Display

Avvia il display manualmente per testarlo:

```bash
python3 lcd_display.py
```

Il display mostrerà:
- **Riga 1**: "OriBruni Receiver"
- **Riga 2**: IP privato del Raspberry Pi
- **Riga 3**: Nome host del sistema
- **Riga 4**: Data e ora correnti

Premi `Ctrl+C` per fermare il programma.

## Configurazione come Servizio

Per avviare automaticamente il display all'avvio del sistema:

### 1. Setup del Servizio

```bash
chmod +x setup_service.sh
./setup_service.sh
```

### 2. Gestione del Servizio

```bash
# Avvia il servizio
sudo systemctl start lcd-display

# Ferma il servizio
sudo systemctl stop lcd-display

# Verifica lo stato
sudo systemctl status lcd-display

# Visualizza i log
sudo journalctl -u lcd-display -f

# Disabilita l'avvio automatico
sudo systemctl disable lcd-display
```

## File del Progetto

- **`lcd_display.py`**: Script principale per controllare il display
- **`test_i2c.py`**: Script di test per verificare la connessione I2C
- **`requirements.txt`**: Dipendenze Python necessarie
- **`install.sh`**: Script di installazione automatica
- **`setup_service.sh`**: Script per configurare il servizio systemd
- **`lcd-display.service`**: File di configurazione del servizio systemd
- **`README.md`**: Questa documentazione

## Personalizzazione

### Modifica dell'Indirizzo I2C

Se il tuo display usa un indirizzo I2C diverso da `0x27`, modifica il file `lcd_display.py`:

```python
# Cambia questa riga nella classe LCDController
lcd_controller = LCDController(i2c_address=0x3F)  # Esempio per indirizzo 0x3F
```

### Personalizzazione del Display

Puoi modificare le informazioni mostrate sul display editando la funzione `display_ip_info()` nel file `lcd_display.py`.

### Intervallo di Aggiornamento

Per cambiare la frequenza di aggiornamento del display, modifica questa riga in `lcd_display.py`:

```python
time.sleep(30)  # Cambia 30 con il numero di secondi desiderato
```

## Risoluzione Problemi

### Display Non Rilevato

1. Verifica i collegamenti hardware
2. Assicurati che l'I2C sia abilitato: `sudo raspi-config`
3. Controlla i dispositivi I2C: `sudo i2cdetect -y 1`
4. Prova indirizzi comuni: `0x27`, `0x3F`

### Errori di Permessi

Se ricevi errori di permessi I2C, aggiungi l'utente al gruppo i2c:

```bash
sudo usermod -a -G i2c $USER
```

Poi riavvia o fai logout/login.

### Display Corrotto o Caratteri Strani

1. Verifica l'alimentazione (5V stabile)
2. Controlla i collegamenti SDA/SCL
3. Prova a cambiare il `charmap` nel codice:

```python
charmap='A00'  # Invece di 'A02'
```

### Servizio Non Si Avvia

Controlla i log del servizio:

```bash
sudo journalctl -u lcd-display -n 50
```

Verifica che i percorsi nel file `.service` siano corretti.

## Indirizzi I2C Comuni

- **0x27** (39): Indirizzo più comune per moduli PCF8574
- **0x3F** (63): Indirizzo alternativo comune
- **0x20-0x27**: Range tipico per PCF8574
- **0x38-0x3F**: Range alternativo per PCF8574

## Supporto

Per problemi o domande:
1. Verifica i collegamenti hardware
2. Esegui `python3 test_i2c.py` per diagnosticare
3. Controlla i log del sistema: `sudo journalctl -u lcd-display`

## Note Tecniche

- Il display viene aggiornato ogni 30 secondi
- Utilizza la libreria RPLCD per la comunicazione I2C
- Compatibile con moduli I2C basati su PCF8574
- Richiede Python 3.6 o superiore
- Testato su Raspberry Pi 3B+ e 4B

## Struttura File

```
lcd_display/
├── lcd_display.py          # Script principale
├── test_i2c.py            # Test I2C
├── requirements.txt        # Dipendenze Python
├── install.sh             # Installazione
├── setup_service.sh       # Setup servizio
├── lcd-display.service    # File servizio systemd
└── README.md              # Questa documentazione
