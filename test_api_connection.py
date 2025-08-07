#!/usr/bin/env python3
"""
Test di connessione alle API OriBruni RadioControls
Utility per testare la connettività e le credenziali del dispositivo
"""

import sys
import json
import requests
import time
import argparse
from pathlib import Path
from urllib.parse import urljoin

def test_api_ping(base_url: str, timeout: int = 10) -> bool:
    """Testa la connettività di base alle API"""
    print("🔍 Test connettività API...")
    
    endpoints_to_test = [
        'callhome.php',
        'radiocontrol_data.php'
    ]
    
    for endpoint in endpoints_to_test:
        url = urljoin(base_url, endpoint)
        try:
            print(f"   Testando {endpoint}...", end=" ")
            
            # Test HEAD request
            response = requests.head(url, timeout=timeout)
            
            if response.status_code in [200, 405]:  # 405 = Method Not Allowed è OK per HEAD
                print("✅ OK")
            else:
                print(f"⚠️ HTTP {response.status_code}")
                
        except requests.exceptions.Timeout:
            print("❌ Timeout")
            return False
        except requests.exceptions.ConnectionError:
            print("❌ Connessione fallita")
            return False
        except Exception as e:
            print(f"❌ Errore: {e}")
            return False
    
    return True

def test_device_credentials(base_url: str, device_name: str, pkey: str, timeout: int = 10) -> bool:
    """Testa le credenziali del dispositivo"""
    print(f"🔐 Test credenziali dispositivo '{device_name}'...")
    
    # Test con callhome.php
    url = urljoin(base_url, 'callhome.php')
    
    test_payload = {
        "name": device_name,
        "pkey": pkey,
        "action": "keepalive",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
        "client_version": "test-utility-1.0.0",
        "system_status": {
            "cpu_percent": 0.0,
            "memory_percent": 0.0,
            "memory_available_mb": 0.0,
            "disk_percent": 0.0,
            "disk_free_gb": 0.0,
            "temperature": 0.0,
            "uptime_hours": 0.0,
            "load_avg_1m": 0.0,
            "process_count": 0
        }
    }
    
    try:
        print("   Invio keepalive di test...", end=" ")
        
        response = requests.post(
            url,
            json=test_payload,
            timeout=timeout,
            headers={'Content-Type': 'application/json'}
        )
        
        print(f"HTTP {response.status_code}")
        
        if response.status_code == 200:
            try:
                result = response.json()
                if result.get('status') == 'success':
                    print("   ✅ Credenziali valide!")
                    return True
                else:
                    print(f"   ❌ Risposta: {result}")
                    return False
            except json.JSONDecodeError:
                if 'success' in response.text.lower():
                    print("   ✅ Credenziali valide! (risposta testo)")
                    return True
                else:
                    print(f"   ❌ Risposta non JSON: {response.text[:100]}")
                    return False
        
        elif response.status_code == 401:
            print("   ❌ Credenziali non valide!")
            return False
        
        elif response.status_code == 422:
            print("   ⚠️ Formato dati non valido")
            return False
        
        else:
            print(f"   ❌ Errore HTTP {response.status_code}: {response.text[:100]}")
            return False
            
    except requests.exceptions.Timeout:
        print("   ❌ Timeout")
        return False
    except requests.exceptions.ConnectionError:
        print("   ❌ Connessione fallita")
        return False
    except Exception as e:
        print(f"   ❌ Errore: {e}")
        return False

def test_device_list(base_url: str, timeout: int = 10) -> bool:
    """Testa il recupero della lista dispositivi"""
    print("📋 Test lista dispositivi...")
    
    url = urljoin(base_url, 'radiocontrol_data.php')
    
    try:
        print("   Recupero lista dispositivi...", end=" ")
        
        response = requests.get(url, timeout=timeout)
        
        print(f"HTTP {response.status_code}")
        
        if response.status_code == 200:
            try:
                devices = response.json()
                print(f"   ✅ Trovati {len(devices)} dispositivi registrati")
                
                # Mostra primi 3 dispositivi come esempio
                for i, device in enumerate(devices[:3]):
                    name = device.get('name', 'N/A')
                    last_callhome = device.get('last_callhome', 'Mai')
                    print(f"   - {name} (ultimo callhome: {last_callhome})")
                
                if len(devices) > 3:
                    print(f"   ... e altri {len(devices) - 3} dispositivi")
                
                return True
                
            except json.JSONDecodeError:
                print(f"   ❌ Risposta non JSON: {response.text[:100]}")
                return False
        
        else:
            print(f"   ❌ Errore HTTP {response.status_code}")
            return False
            
    except requests.exceptions.Timeout:
        print("   ❌ Timeout")
        return False
    except requests.exceptions.ConnectionError:
        print("   ❌ Connessione fallita")
        return False
    except Exception as e:
        print(f"   ❌ Errore: {e}")
        return False

def test_punches_data(base_url: str, timeout: int = 10) -> bool:
    """Testa il recupero dei dati punzonature"""
    print("🏃‍♂️ Test dati punzonature...")
    
    url = urljoin(base_url, 'radiocontrol_punches_data.php')
    
    try:
        print("   Recupero ultime punzonature...", end=" ")
        
        response = requests.get(url, timeout=timeout)
        
        print(f"HTTP {response.status_code}")
        
        if response.status_code == 200:
            try:
                punches = response.json()
                print(f"   ✅ Trovate {len(punches)} punzonature recenti")
                
                # Mostra prime 3 punzonature come esempio
                for i, punch in enumerate(punches[:3]):
                    card = punch.get('card_number', 'N/A')
                    control = punch.get('control', 'N/A')
                    time_str = punch.get('punch_time', 'N/A')
                    device = punch.get('device_id', 'N/A')
                    print(f"   - Chip {card}, controllo {control}, {time_str} ({device})")
                
                if len(punches) > 3:
                    print(f"   ... e altre {len(punches) - 3} punzonature")
                
                return True
                
            except json.JSONDecodeError:
                print(f"   ❌ Risposta non JSON: {response.text[:100]}")
                return False
        
        else:
            print(f"   ❌ Errore HTTP {response.status_code}")
            return False
            
    except requests.exceptions.Timeout:
        print("   ❌ Timeout")
        return False
    except requests.exceptions.ConnectionError:
        print("   ❌ Connessione fallita")
        return False
    except Exception as e:
        print(f"   ❌ Errore: {e}")
        return False

def load_device_config() -> tuple:
    """Carica configurazione dispositivo dal file config.ini"""
    config_file = Path("config/config.ini")
    
    if not config_file.exists():
        return None, None
    
    try:
        import configparser
        config = configparser.ConfigParser()
        config.read(config_file)
        
        if config.has_section('DEVICE'):
            device_name = config.get('DEVICE', 'name', fallback=None)
            pkey = config.get('DEVICE', 'pkey', fallback=None)
            return device_name, pkey
        
    except Exception as e:
        print(f"⚠️ Errore lettura configurazione: {e}")
    
    return None, None

def main():
    """Funzione principale"""
    parser = argparse.ArgumentParser(
        description='Test connessione API OriBruni RadioControls',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Esempi di utilizzo:

  # Test completo con configurazione locale
  python3 test_api_connection.py

  # Test solo connettività
  python3 test_api_connection.py --ping-only

  # Test con credenziali specifiche
  python3 test_api_connection.py --name OBRC_004 --pkey 936D4854BB4E5

  # Test con URL API personalizzato
  python3 test_api_connection.py --api-url https://custom.domain.com/api/
        """
    )
    
    parser.add_argument('--api-url', default='https://orienteering.services/radiocontrol/',
                       help='URL base delle API (default: https://orienteering.services/radiocontrol/)')
    parser.add_argument('--name', help='Nome del dispositivo da testare')
    parser.add_argument('--pkey', help='Chiave del dispositivo da testare')
    parser.add_argument('--timeout', type=int, default=10,
                       help='Timeout richieste HTTP in secondi (default: 10)')
    parser.add_argument('--ping-only', action='store_true',
                       help='Esegui solo test di connettività (no credenziali)')
    parser.add_argument('--verbose', action='store_true',
                       help='Output dettagliato')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("🧪 OriBruni RadioControls - Test API")
    print("=" * 60)
    print(f"URL API: {args.api_url}")
    print(f"Timeout: {args.timeout}s")
    print()
    
    # Test connettività di base
    if not test_api_ping(args.api_url, args.timeout):
        print("\n❌ Test connettività fallito!")
        sys.exit(1)
    
    print("✅ Connettività API OK")
    
    if args.ping_only:
        print("\n🎉 Test ping completato con successo!")
        sys.exit(0)
    
    # Carica credenziali
    device_name = args.name
    pkey = args.pkey
    
    if not device_name or not pkey:
        print("\n📁 Caricamento configurazione locale...")
        device_name, pkey = load_device_config()
        
        if not device_name or not pkey:
            print("❌ Credenziali non trovate!")
            print("   Usa --name e --pkey oppure esegui prima install_device.py")
            sys.exit(1)
        
        print(f"✅ Configurazione caricata: {device_name}")
    
    print()
    
    # Test credenziali dispositivo
    if not test_device_credentials(args.api_url, device_name, pkey, args.timeout):
        print("\n❌ Test credenziali fallito!")
        sys.exit(1)
    
    print()
    
    # Test lista dispositivi
    if not test_device_list(args.api_url, args.timeout):
        print("⚠️ Test lista dispositivi fallito (non critico)")
    
    print()
    
    # Test dati punzonature
    if not test_punches_data(args.api_url, args.timeout):
        print("⚠️ Test dati punzonature fallito (non critico)")
    
    print()
    print("=" * 60)
    print("🎉 Test API completato con successo!")
    print("=" * 60)
    print()
    print("✅ Il dispositivo è configurato correttamente")
    print("✅ Le API sono raggiungibili e funzionanti")
    print("✅ Le credenziali sono valide")
    print()
    print("Prossimi passi:")
    print("- Esegui il deploy con: python3 scripts/deploy_raspberry.py")
    print("- Avvia i servizi con: ./start_oribruni.sh")
    print("- Monitora con: journalctl -f -u oribruni-*")


if __name__ == '__main__':
    main()
