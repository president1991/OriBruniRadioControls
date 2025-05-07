import sys
import configparser
import logging
from PyQt6.QtWidgets import QApplication
from meshdash.gui import MeshDashWindow

def main():
    # 1. Leggi config.ini
    config = configparser.ConfigParser()
    config.read('config.ini')

    # 2. Serial port
    port = config.get('serial', 'port', fallback=None) or None

    # 3. Intervallo di refresh (ms)
    refresh_interval = config.getint('app', 'refresh_interval', fallback=10000)

    # 4. Livello di log
    log_level = config.get('app', 'log_level', fallback='INFO').upper()
    numeric_level = getattr(logging, log_level, logging.INFO)

    # 5. Nome del file di log
    log_file = config.get('app', 'log_file', fallback='meshdash.log')

    # 6. Configura il logging: tutto su file
    logging.basicConfig(
        level=numeric_level,
        format='[%(asctime)s] %(levelname)s: %(message)s',
        filename=log_file,
        filemode='a'  # 'w' per sovrascrivere ogni volta, 'a' per appendere
    )

    logging.info(f"Avvio MeshDash con porta={port!r}, refresh={refresh_interval}ms, log={log_level}")

    # 7. Avvia Qt e passa i parametri
    app = QApplication(sys.argv)
    window = MeshDashWindow(port=port, refresh_interval=refresh_interval)
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
