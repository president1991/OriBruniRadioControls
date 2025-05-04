import sys
import serial.tools.list_ports
import logging
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QListWidget,
    QMessageBox,
    QMenu
)
from PyQt6.QtGui import QAction
from PyQt6.QtCore import QTimer
from .meshtastic_interface import MeshtasticInterface

class MeshDashWindow(QMainWindow):
    def __init__(self, port=None, refresh_interval=10000):
        super().__init__()
        self.setWindowTitle("MeshDash")
        self.resize(400, 300)

        # 1) Non apro più subito la porta: aspetto la selezione dal menu
        self.port = port
        self.interface = None

        # 2) Se config.ini conteneva una porta valida, spunteremo già quella voce nel menu
        #    Ma non la apriamo fino a selezione esplicita.

        # Widget centrale
        central = QWidget()
        self.setCentralWidget(central)
        self.layout = QVBoxLayout(central)

        self.label = QLabel("Dispositivi Meshtastic rilevati:")
        self.device_list = QListWidget()
        self.refresh_button = QPushButton("Aggiorna")
        self.refresh_button.clicked.connect(self.refresh_devices)

        self.layout.addWidget(self.label)
        self.layout.addWidget(self.device_list)
        self.layout.addWidget(self.refresh_button)

        # Timer per aggiornamento automatico
        self.timer = QTimer()
        self.timer.timeout.connect(self.refresh_devices)
        if refresh_interval > 0:
            self.timer.start(refresh_interval)
            logging.info(f"Timer auto-refresh impostato a {refresh_interval} ms")
        else:
            self.timer.stop()
            logging.info("Timer auto-refresh disabilitato")

        # Barra dei menu e sottomenu Serial Port
        menubar = self.menuBar()
        settings_menu = menubar.addMenu("Settings")
        port_menu = QMenu("Serial Port...", self)
        settings_menu.addMenu(port_menu)
        self.port_actions = []
        self._populate_port_menu(port_menu)

        # NOTA: non chiamo refresh_devices() qui perché interface è ancora None

    def _populate_port_menu(self, menu: QMenu):
        """Popola il sottomenu con le porte COM disponibili e spunta la porta configurata."""
        menu.clear()
        self.port_actions.clear()
        ports = serial.tools.list_ports.comports()

        for port in ports:
            act = QAction(port.device, self, checkable=True)
            if port.device == self.port:
                act.setChecked(True)
            act.triggered.connect(lambda checked, p=port.device: self._change_port(p))
            menu.addAction(act)
            self.port_actions.append(act)

        menu.setEnabled(bool(ports))

    def _change_port(self, port: str):
        """Quando selezioni una porta, la apro e avvio il refresh."""
        self.port = port
        # aggiorna le spunte del menu
        for act in self.port_actions:
            act.setChecked(act.text() == port)

        # Provo ad aprire l'interfaccia con la nuova porta
        try:
            self.interface = MeshtasticInterface(port=self.port)
            logging.info(f"Connesso a porta seriale: {self.port}")
            # Dopo aver aperto con successo, faccio subito un refresh
            self.refresh_devices()
        except Exception as e:
            QMessageBox.warning(
                self,
                "Errore porta seriale",
                f"Impossibile aprire la porta '{self.port}':\n{e}"
            )
            logging.error(f"Errore apertura porta {self.port}: {e}")
            # Mantengo interface = None finché non selezioni una porta valida

    def refresh_devices(self):
        """Aggiorna la lista solo se l'interfaccia è stata inizializzata."""
        if not self.interface:
            return

        try:
            nodes = self.interface.get_nodes()
            self.device_list.clear()
            for node in nodes:
                self.device_list.addItem(
                    f"{node.user}: {node.id} (Battery: {node.battery_level}%)"
                )
            logging.debug(f"Aggiornati {len(nodes)} dispositivi")
        except Exception as e:
            QMessageBox.warning(
                self,
                "Errore connessione",
                f"Errore di connessione:\n{e}"
            )
            logging.error(f"Errore durante refresh_devices: {e}")

if __name__ == "__main__":
    # Blocco di test rapido
    app = QApplication(sys.argv)
    window = MeshDashWindow(port=None, refresh_interval=5000)
    window.show()
    sys.exit(app.exec())
