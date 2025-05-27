from RPLCD.i2c import CharLCD
from time import sleep

# Inizializza LCD 20x4 con indirizzo I2C 0x27
lcd = CharLCD(i2c_expander='PCF8574', address=0x27, port=1,
              cols=20, rows=4, charmap='A02', auto_linebreaks=True)

# Cancella e scrivi
lcd.clear()
lcd.write_string("LCD 20x4 online!\n")
lcd.write_string("Linea 2 attiva...\n")
lcd.write_string("Linea 3 attiva...\n")
lcd.write_string("Linea 4 attiva...")
sleep(10)

# Pulizia
lcd.clear()
