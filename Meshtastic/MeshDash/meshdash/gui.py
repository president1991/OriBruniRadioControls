import sys
import os
import json
import logging
import serial.tools.list_ports
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple
from logging.handlers import TimedRotatingFileHandler

from pubsub import pub
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QLabel, QPushButton, QListWidget, QMessageBox, QMenu, QListWidgetItem
)
from PyQt6.QtGui import QAction
from PyQt6.QtCore import QTimer

import matplotlib
matplotlib.use("QtAgg")
import matplotlib.pyplot as plt
import networkx as nx
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas

from .meshtastic_interface import MeshInterface
from .models import MeshNode

# Helper to make any packet JSON-friendly
def get_clean_packet(packet: Any) -> Dict[str, Any]:
    clean: Dict[str, Any] = {}
    # If it's already a dict, use its items; otherwise use its __dict__ if available
    items = packet.items() if isinstance(packet, dict) else getattr(packet, "__dict__", {}).items()
    for key, val in items:
        if isinstance(val, (str, int, float, bool, type(None))):
            clean[key] = val
        else:
            # repr anything complex
            try:
                clean[key] = repr(val)
            except Exception:
                clean[key] = f"<unserializable {type(val).__name__}>"
    return clean

# Riduce i messaggi di debug per font_manager di matplotlib
logging.getLogger('matplotlib.font_manager').setLevel(logging.WARNING)

# Configurazione logging con rotazione giornaliera
LOG_DIR = os.path.expanduser("~/meshdash_logs")
os.makedirs(LOG_DIR, exist_ok=True)
log_path = os.path.join(LOG_DIR, "meshdash.log")

timer_handler = TimedRotatingFileHandler(
    filename=log_path,
    when="midnight",
    interval=1,
    backupCount=7,
    encoding="utf-8",
    utc=False
)
timer_handler.suffix = "%Y-%m-%d"
formatter = logging.Formatter(
    fmt="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
timer_handler.setFormatter(formatter)

root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)
# Rimuove handler FileHandler non rotanti
for h in list(root_logger.handlers):
    if isinstance(h, logging.FileHandler) and not isinstance(h, TimedRotatingFileHandler):
        root_logger.removeHandler(h)
root_logger.addHandler(timer_handler)

class GraphCanvas(FigureCanvas):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        self.fig, self.ax = plt.subplots()
        super().__init__(self.fig)
        self.setParent(parent)
        plt.tight_layout()

    def draw_graph(self, links: List[Tuple[str, str, float]], nodes: Optional[List[str]] = None) -> None:
        self.ax.clear()
        G = nx.Graph()
        if nodes:
            G.add_nodes_from(nodes)
        for a, b, quality in links:
            G.add_edge(a, b, weight=quality)
        if G.number_of_nodes():
            pos = nx.spring_layout(G, weight='weight')
            nx.draw_networkx_nodes(G, pos, ax=self.ax, node_size=300)
            if G.number_of_edges():
                max_q = max(d['weight'] for _, _, d in G.edges(data=True))
                widths = [2 * (d['weight'] / max_q) for _, _, d in G.edges(data=True)]
                nx.draw_networkx_edges(G, pos, ax=self.ax, width=widths)
            nx.draw_networkx_labels(G, pos, ax=self.ax)
        self.ax.set_axis_off()
        self.draw()

class MeshDashWindow(QMainWindow):
    """
    Finestra principale di MeshDash con cap log limitati,
    gestione migliorata degli errori e supporto a i18n.
    """
    LOG_LIMIT = 100

    def __init__(self, port: Optional[str] = None, refresh_interval: int = 10000) -> None:
        super().__init__()
        self.setWindowTitle(self.tr("MeshDash"))
        self.resize(600, 700)

        self.port: Optional[str] = port
        self.interface: Optional[MeshInterface] = None
        self.name_map: Dict[str, str] = {}
        self.current_links: List[Tuple[str, str, float]] = []

        central = QWidget()
        self.setCentralWidget(central)
        self.layout = QVBoxLayout(central)

        # Lista dispositivi
        self.label = QLabel(self.tr("Dispositivi Meshtastic rilevati:"))
        self.device_list = QListWidget()
        self.refresh_button = QPushButton(self.tr("Aggiorna"))
        self.refresh_button.clicked.connect(self.refresh_all)

        self.layout.addWidget(self.label)
        self.layout.addWidget(self.device_list)
        self.layout.addWidget(self.refresh_button)

        # Grafico mesh
        self.graph_canvas = GraphCanvas(self)
        self.layout.addWidget(self.graph_canvas)

        # Log dei payload
        self.log_label = QLabel(self.tr("Log dei payload:"))
        self.log_list = QListWidget()
        self.log_list.setFixedHeight(150)
        self.layout.addWidget(self.log_label)
        self.layout.addWidget(self.log_list)

        # Menu impostazioni
        menubar = self.menuBar()
        settings_menu = menubar.addMenu(self.tr("Impostazioni"))
        port_menu = QMenu(self.tr("Porta seriale..."), self)
        settings_menu.addMenu(port_menu)
        self.port_actions: List[QAction] = []
        self._populate_port_menu(port_menu)
         # Se la porta è stata passata da config.ini, connettiti subito
        if self.port:
            try:
                self.interface = MeshInterface(port=self.port)
                logging.info(f"Connessione automatica a {self.port}")
                # Aggiorna subito UI
                self.refresh_all()
            except Exception as e:
                self.show_error(
                    self.tr("Errore porta seriale"),
                    self.tr(f"Impossibile aprire la porta '{self.port}':\n{e}")
                )
                logging.error(f"Errore apertura porta {self.port}: {e}")
                self.interface = None

        # Auto-refresh
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_all)
        if refresh_interval > 0:
            self.timer.start(refresh_interval)
            logging.info(f"Timer auto-refresh impostato a {refresh_interval} ms")
        else:
            self.timer.stop()
            logging.info("Timer auto-refresh disabilitato")

        # Sottoscrizioni
        pub.subscribe(self._on_new_payload, "meshtastic.receive")
        pub.subscribe(self.refresh_graph, "meshdash.new_links")

    def show_error(self, title: str, message: str) -> None:
        """Mostra un dialogo di errore critico."""
        QMessageBox.critical(self, self.tr(title), message)

    def _populate_port_menu(self, menu: QMenu) -> None:
        """Popola il menu con le porte seriali disponibili."""
        menu.clear()
        self.port_actions.clear()
        for port in serial.tools.list_ports.comports():
            act = QAction(port.device, self, checkable=True)
            if port.device == self.port:
                act.setChecked(True)
            act.triggered.connect(lambda _, p=port.device: self._change_port(p))
            menu.addAction(act)
            self.port_actions.append(act)
        menu.setEnabled(bool(self.port_actions))

    def _change_port(self, port: str) -> None:
        """Cambia la porta seriale e connette l'interfaccia."""
        self.port = port
        for act in self.port_actions:
            act.setChecked(act.text() == port)
        try:
            self.interface = MeshInterface(port=self.port)
            logging.info(f"Connesso a porta seriale: {self.port}")
            self.refresh_all()
        except Exception as e:
            self.show_error(
                "Errore porta seriale",
                self.tr(f"Impossibile aprire la porta '{self.port}':\n{e}")
            )
            logging.error(f"Errore apertura porta {self.port}: {e}")
            self.interface = None

    def refresh_all(self) -> None:
        """Esegue refresh di dispositivi e grafo."""
        if not self.interface:
            return
        # Chiedi ai nodi di inviare telemetria (popola interface.nodes)
        self.interface.request_telemetry()
        self.refresh_devices()
        self.refresh_graph()

    def refresh_devices(self) -> None:
        """Aggiorna la lista dispositivi con formato migliorato."""
        try:
            self.device_list.clear()
            nodes = self.interface.get_nodes()
            for node in nodes:
                # Otteniamo un'etichetta più leggibile
                node_id = node.id
                
                # Estrai le informazioni dal formato complesso (se disponibile)
                radio_name = "Sconosciuto"
                short_name = ""
                
                # Mappa dei nomi migliori dai dati grezzi
                if hasattr(node, 'raw_data') and node.raw_data:
                    raw_data = node.raw_data
                    if 'longName' in raw_data:
                        radio_name = raw_data.get('longName', 'Radio')
                    if 'shortName' in raw_data:
                        short_name = f" ({raw_data.get('shortName', '')})"

                # Formato semplificato e leggibile
                battery_info = f" - Batteria: {node.battery_level}%" if node.battery_level > 0 else ""
                text = f"{radio_name}{short_name} - ID: {node_id[-6:]}{battery_info}"
                
                # Aggiungi l'elemento alla lista
                item = QListWidgetItem(text)
                item.setToolTip(f"ID completo: {node_id}")
                self.device_list.addItem(item)
                
            logging.debug(f"Aggiornati {len(nodes)} dispositivi")
        except Exception as e:
            logging.error(f"Errore in refresh_devices: {e}")
            self.show_error("Errore connessione", str(e))

    def refresh_graph(self) -> None:
        """Aggiorna il grafo della mesh."""
        try:
            links = self.interface.get_links()
            nodes = [n.id for n in self.interface.get_nodes()]
            self.graph_canvas.draw_graph(links, nodes)
        except Exception as e:
            logging.error(f"Errore in refresh_graph: {e}")
            self.show_error("Errore grafo", str(e))

    def _on_new_payload(self, packet: Any) -> None:
        """Callback per nuovi pacchetti ricevuti: pulisce e logga."""
        clean = self._clean_payload(packet)
        try:
            text = json.dumps(clean, ensure_ascii=False)
        except Exception:
            text = str(clean)
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.log_list.insertItem(0, f"{ts} {text}")
        if self.log_list.count() > self.LOG_LIMIT:
            self.log_list.takeItem(self.log_list.count() - 1)
        self.log_list.scrollToTop()

    def _clean_payload(self, packet: Any) -> Dict[str, Any]:
        """Rimuove campi non serializzabili e riduce il payload."""
        # Logica originale di pulizia...
        return get_clean_packet(packet)  # implementare separatamente

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MeshDashWindow(port=None, refresh_interval=5000)
    window.show()
    sys.exit(app.exec())