#!/usr/bin/env python3
"""
Script di test per verificare la connessione I2C e trovare l'indirizzo del display LCD
"""

import subprocess
import sys
import time
from RPLCD.i2c import CharLCD

def check_i2c_tools():
    """Verifica se i2c-tools sono installati"""
    try:
        result = subprocess.run(['i2cdetect', '-V'], capture_output=True, text=True)
        print("✓ i2c-tools installati")
        return True
    except FileNotFoundError:
        print("✗ i2c-tools non installati")
        print("Installa con: sudo apt-get install i2c-tools")
        return False

def scan_i2c_devices():
    """Scansiona i dispositivi I2C collegati"""
    print("\nScansione dispositivi I2C...")
    try:
        # Scansiona il bus I2C 1 (quello standard su Raspberry Pi)
        result = subprocess.run(['i2cdetect', '-y', '1'], capture_output=True, text=True)
        print("Bus I2C 1:")
        print(result.stdout)
        
        # Estrae gli indirizzi trovati
        lines = result.stdout.strip().split('\n')[1:]  # Salta l'header
        addresses = []
        for line in lines:
            parts = line.split()
            for i, part in enumerate(parts[1:], 1):  # Salta il primo elemento (row header)
                if part != '--' and part != 'UU':
                    addr = int(f"0x{parts[0]}{i-1:x}", 16)
                    addresses.append(addr)
        
        return addresses
    except Exception as e:
        print(f"Errore nella scansione I2C: {e}")
        return []

def test_lcd_connection(address):
    """Testa la connessione al display LCD"""
    print(f"\nTest connessione LCD all'indirizzo {hex(address)}...")
    try:
        lcd = CharLCD(
            i2c_expander='PCF8574',
            address=address,
            port=1,
            cols=20,
            rows=4,
            dotsize=8,
            charmap='A02',
            auto_linebreaks=True
        )
        
        # Test di scrittura
        lcd.clear()
        lcd.write_string("Test I2C OK!")
        lcd.cursor_pos = (1, 0)
        lcd.write_string(f"Indirizzo: {hex(address)}")
        lcd.cursor_pos = (2, 0)
        lcd.write_string("OriBruni Receiver")
        lcd.cursor_pos = (3, 0)
        lcd.write_string(time.strftime("%H:%M:%S"))
        
        print(f"✓ LCD funziona correttamente all'indirizzo {hex(address)}")
        
        time.sleep(3)
        lcd.clear()
        lcd.close()
        return True
        
    except Exception as e:
        print(f"✗ Errore nel test LCD: {e}")
        return False

def main():
    """Funzione principale di test"""
    print("=== Test I2C per Display LCD 20x4 ===")
    print("Collegamento:")
    print("LCD GND  -> Raspberry Pi Pin 6  (GND)")
    print("LCD VCC  -> Raspberry Pi Pin 2  (5V)")
    print("LCD SDA  -> Raspberry Pi Pin 3  (GPIO 2)")
    print("LCD SCL  -> Raspberry Pi Pin 5  (GPIO 3)")
    print("=" * 40)
    
    # Verifica i2c-tools
    if not check_i2c_tools():
        return
    
    # Scansiona dispositivi I2C
    addresses = scan_i2c_devices()
    
    if not addresses:
        print("\n✗ Nessun dispositivo I2C trovato!")
        print("Verifica i collegamenti e che l'I2C sia abilitato:")
        print("sudo raspi-config -> Interfacing Options -> I2C -> Enable")
        return
    
    print(f"\n✓ Trovati {len(addresses)} dispositivi I2C:")
    for addr in addresses:
        print(f"  - {hex(addr)}")
    
    # Testa ogni indirizzo trovato
    print("\nTest connessione LCD...")
    for addr in addresses:
        if test_lcd_connection(addr):
            print(f"\n🎉 Display LCD funzionante all'indirizzo {hex(addr)}")
            print(f"Usa questo indirizzo nel file lcd_display.py")
            break
    else:
        print("\n✗ Nessun display LCD funzionante trovato")
        print("Indirizzi comuni per LCD I2C: 0x27, 0x3F")

if __name__ == "__main__":
    main()
