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

import matplotlib.pyplot as plt
import networkx as nx
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

from .meshtastic_interface import MeshtasticInterface

# Configurazione del logging su file
logging.basicConfig(
    filename='meshdash.log',
    filemode='a',
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)s: %(message)s'
)

class GraphCanvas(FigureCanvas):
    def __init__(self, parent=None):
        self.fig, self.ax = plt.subplots()
        super().__init__(self.fig)
        self.setParent(parent)
        plt.tight_layout()

    def draw_graph(self, links, nodes=None):
        """
        Draws a mesh graph.
        'links' is a list of tuples: (node_a, node_b, quality)
        'nodes' is an optional list of all node IDs to include as isolated vertices.
        """
        self.ax.clear()
        G = nx.Graph()
        if nodes:
            G.add_nodes_from(nodes)
        for a, b, quality in links:
            G.add_edge(a, b, weight=quality)
        pos = {}
        if G.number_of_nodes() > 0:
            pos = nx.spring_layout(G, weight='weight')
        nx.draw_networkx_nodes(G, pos, ax=self.ax, node_size=300)
        if G.number_of_edges() > 0:
            max_q = max(d['weight'] for _, _, d in G.edges(data=True))
            widths = [2 * (d['weight'] / max_q) for _, _, d in G.edges(data=True)]
            nx.draw_networkx_edges(G, pos, ax=self.ax, width=widths)
        nx.draw_networkx_labels(G, pos, ax=self.ax)
        self.ax.set_axis_off()
        self.draw()

class MeshDashWindow(QMainWindow):
    def __init__(self, port=None, refresh_interval=10000):
        super().__init__()
        self.setWindowTitle("MeshDash")
        self.resize(600, 500)

        self.port = port
        self.interface = None

        central = QWidget()
        self.setCentralWidget(central)
        self.layout = QVBoxLayout(central)

        self.label = QLabel("Dispositivi Meshtastic rilevati:")
        self.device_list = QListWidget()
        self.refresh_button = QPushButton("Aggiorna")
        self.refresh_button.clicked.connect(self.refresh_all)

        self.layout.addWidget(self.label)
        self.layout.addWidget(self.device_list)
        self.layout.addWidget(self.refresh_button)

        self.graph_canvas = GraphCanvas(self)
        self.layout.addWidget(self.graph_canvas)

        self.timer = QTimer()
        self.timer.timeout.connect(self.refresh_all)
        if refresh_interval > 0:
            self.timer.start(refresh_interval)
            logging.info(f"Timer auto-refresh impostato a {refresh_interval} ms")
        else:
            self.timer.stop()
            logging.info("Timer auto-refresh disabilitato")

        menubar = self.menuBar()
        settings_menu = menubar.addMenu("Settings")
        port_menu = QMenu("Serial Port...", self)
        settings_menu.addMenu(port_menu)
        self.port_actions = []
        self._populate_port_menu(port_menu)

    def _populate_port_menu(self, menu: QMenu):
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
        self.port = port
        for act in self.port_actions:
            act.setChecked(act.text() == port)
        try:
            self.interface = MeshtasticInterface(port=self.port)
            logging.info(f"Connesso a porta seriale: {self.port}")
            self.refresh_all()
        except Exception as e:
            QMessageBox.warning(
                self,
                "Errore porta seriale",
                f"Impossibile aprire la porta '{self.port}':\n{e}"
            )
            logging.error(f"Errore apertura porta {self.port}: {e}")
            self.interface = None

    def refresh_all(self):
        if not self.interface:
            return
        self.refresh_devices()
        self.refresh_graph()

    def refresh_devices(self):
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

    def refresh_graph(self):
        try:
            nodes = self.interface.get_nodes()
            links = self.interface.get_links()
            logging.debug(f"Ricevuti {len(links)} link da disegnare, {len(nodes)} nodi")

            node_ids = [n.id for n in nodes]
            self.graph_canvas.draw_graph(links, nodes=node_ids)

            if not links:
                reply = QMessageBox.question(
                    self,
                    "Nessun collegamento rilevato",
                    "Non sono stati trovati link tra i nodi. Vuoi richiedere i dati di neighbor_info?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if reply == QMessageBox.StandardButton.Yes:
                    # Tenta di richiedere i dati via MeshtasticInterface se supportato
                    if hasattr(self.interface, 'request_telemetry'):
                        try:
                            self.interface.request_telemetry("neighbor_info")
                            # Riprova a disegnare dopo breve attesa
                            QTimer.singleShot(2000, self.refresh_graph)
                        except Exception as e:
                            QMessageBox.warning(
                                self,
                                "Errore richiesta dati",
                                f"Impossibile richiedere neighbor_info:\n{e}"
                            )
                            logging.error(f"Errore in request_telemetry: {e}")
                    else:
                        QMessageBox.warning(
                            self,
                            "Metodo non supportato",
                            "La richiesta di telemetry non è supportata da questa interfaccia."
                        )
                        logging.error("request_telemetry non disponibile su MeshtasticInterface")
        except Exception as e:
            QMessageBox.warning(
                self,
                "Errore grafo",
                f"Errore durante aggiornamento grafo:\n{e}"
            )
            logging.error(f"Errore durante refresh_graph: {e}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MeshDashWindow(port=None, refresh_interval=5000)
    window.show()
    sys.exit(app.exec())
