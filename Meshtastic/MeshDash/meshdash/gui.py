import sys
import serial.tools.list_ports
import logging
from datetime import datetime
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QLabel, QPushButton, QListWidget, QMessageBox, QMenu
)
from PyQt6.QtGui import QAction
from PyQt6.QtCore import QTimer
logging.getLogger('matplotlib.font_manager').setLevel(logging.WARNING)
import matplotlib
matplotlib.use("QtAgg")
try:
    from matplotlib.backends.backend_qt6agg import FigureCanvasQTAgg as FigureCanvas
except ImportError:
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas

import matplotlib.pyplot as plt
import networkx as nx

from .meshtastic_interface import MeshtasticInterface
from pubsub import pub
import json

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
                widths = [2*(d['weight']/max_q) for _, _, d in G.edges(data=True)]
                nx.draw_networkx_edges(G, pos, ax=self.ax, width=widths)
            nx.draw_networkx_labels(G, pos, ax=self.ax)
        self.ax.set_axis_off()
        self.draw()

class MeshDashWindow(QMainWindow):
    def __init__(self, port=None, refresh_interval=10000):
        super().__init__()
        self.setWindowTitle("MeshDash")
        self.resize(600, 700)

        self.port = port
        self.interface = None

        # mappa peer_id (pkey) → nome ricevuto dal payload
        self.name_map: dict[str,str] = {}
        # archi costruiti manualmente dai neigh_info
        self.current_links: list[tuple[str,str,float]] = []

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

        self.log_label = QLabel("Log dei payload:")
        self.log_list = QListWidget()
        self.log_list.setFixedHeight(150)
        self.layout.addWidget(self.log_label)
        self.layout.addWidget(self.log_list)

        # timer di auto-refresh
        self.timer = QTimer()
        self.timer.timeout.connect(self.refresh_all)
        if refresh_interval > 0:
            self.timer.start(refresh_interval)
            logging.info(f"Timer auto-refresh impostato a {refresh_interval} ms")
        else:
            self.timer.stop()
            logging.info("Timer auto-refresh disabilitato")

        # sottoscriviamo il callback per tutti i pacchetti ricevuti
        pub.subscribe(self._on_new_payload, "meshtastic.receive")

        pub.subscribe(self.refresh_graph, "meshdash.new_links")  # Modificato

        # menu per scegliere la porta seriale
        menubar = self.menuBar()
        settings_menu = menubar.addMenu("Settings")
        port_menu = QMenu("Serial Port...", self)
        settings_menu.addMenu(port_menu)
        self.port_actions = []
        self._populate_port_menu(port_menu)

    def _populate_port_menu(self, menu: QMenu):
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

    def _change_port(self, port: str):
        self.port = port
        for act in self.port_actions:
            act.setChecked(act.text() == port)
        try:
            self.interface = MeshtasticInterface(port=self.port)
            logging.info(f"Connesso a porta seriale: {self.port}")
            self.refresh_all()
        except Exception as e:
            QMessageBox.warning(self, "Errore porta seriale",
                                f"Impossibile aprire la porta '{self.port}':\n{e}")
            logging.error(f"Errore apertura porta {self.port}: {e}")
            self.interface = None

    def refresh_all(self):
        if not self.interface:
            return
        self.refresh_devices()
        self.refresh_graph()
    
    def refresh_devices(self):
        """
        Aggiorna la lista dei dispositivi Meshtastic, mostrando
        user, id, battery e – se disponibili – i metadati dei neighbors.
        """
        try:
            nodes = self.interface.get_nodes()
            self.device_list.clear()

            for node in nodes:
                # Prendo i metadata salvati in MeshtasticInterface._on_receive_neighbors
                meta = getattr(self.interface, 'neighbor_data', {}).get(node.id, {})

                # Costruisco una lista di stringhe extra solo per i campi presenti
                extras = []
                if 'rx_snr' in meta and meta['rx_snr'] is not None:
                    extras.append(f"snr:{meta['rx_snr']}")
                if 'rx_rssi' in meta and meta['rx_rssi'] is not None:
                    extras.append(f"rssi:{meta['rx_rssi']}")
                if 'hop_limit' in meta and meta['hop_limit'] is not None:
                    extras.append(f"hop_limit:{meta['hop_limit']}")
                if 'hop_start' in meta and meta['hop_start'] is not None:
                    extras.append(f"hop_start:{meta['hop_start']}")
                if 'relay_node' in meta and meta['relay_node'] is not None:
                    extras.append(f"relay:{meta['relay_node']}")

                extras_str = ""
                if extras:
                    extras_str = "  •  " + ", ".join(extras)

                # Inserisco l’item con battery e gli extras (se ci sono)
                self.device_list.addItem(
                    f"{node.user}: {node.id}  "
                    f"(Battery: {node.battery_level} %){extras_str}"
                )

            logging.debug(f"Aggiornati {len(nodes)} dispositivi")
        except Exception as e:
            QMessageBox.warning(self, "Errore connessione", str(e))
            logging.error(f"Errore in refresh_devices: {e}")

    def refresh_graph(self):
        try:
            links = self.interface.get_links()
            logging.debug(f"refresh_graph: got links = {links}")
            nodes = self.interface.get_nodes()
            logging.debug(f"refresh_graph: nodes = {[n.id for n in nodes]}")
            logging.debug(f"Links: {links}")

            # Ottieni il tuo ID formattato (se disponibile)
            my_id = None
            if self.interface.my_info and hasattr(self.interface.my_info, 'id'):
                my_id = self.interface._format_peer(self.interface.my_info.id)
                logging.debug(f"refresh_graph: my_id = {my_id}")
            else:
                logging.warning("refresh_graph: Impossibile ottenere l'ID locale da self.interface.my_info")

            # Mappa id → label
            id_to_label = {n.id: self.name_map.get(n.id, n.user) for n in nodes}

            # Etichetta il nodo locale come "YOU" (se lo troviamo)
            if my_id and my_id in id_to_label:
                id_to_label[my_id] = "YOU"
            elif my_id:
                logging.warning(f"refresh_graph: Il nodo locale con ID {my_id} non è presente nei nodi rilevati")

            # Prepara gli archi con etichette
            named = [(id_to_label.get(a, a), id_to_label.get(b, b), q) for a, b, q in links]
            self.graph_canvas.draw_graph(named, nodes=list(id_to_label.values()))

        except Exception as e:
            QMessageBox.warning(self, "Errore grafo", str(e))
            logging.error(f"Errore in refresh_graph: {e}")

    def _on_new_payload(self, packet, interface=None):
        if not self.interface:
            return

        # 1) Preleva il dict "decoded" (se esiste) o usa direttamente packet
        raw = packet.get('decoded', packet)

        # 2) Se payload/text sono ancora stringhe JSON, parsale per togliere escape
        if isinstance(raw, dict):
            if isinstance(raw.get('payload'), str):
                try:
                    raw['payload'] = json.loads(raw['payload'])
                except json.JSONDecodeError:
                    pass
            if isinstance(raw.get('text'), str):
                try:
                    raw['text'] = json.loads(raw['text'])
                except json.JSONDecodeError:
                    pass

        # 3) Rendilo JSON-serializzabile
        clean = self.interface._make_jsonable(raw)

        # 4) Estrai eventuale neigh_info (annidato o top-level)
        info = clean.get('payload') if isinstance(clean.get('payload'), dict) else clean

        # 5) Se è neigh_info, ricava remote_id e my_id formattati e disegna il link
        if info.get('type') == 'neigh_info' and 'name' in info:
            # a) remoto: prendo l’ID dal packet, non dal pkey
            raw_peer  = packet.get('fromId', packet.get('from'))
            remote_id = self.interface._format_peer(raw_peer)
            self.name_map[remote_id] = info['name']

            # b) locale: *adesso* my_info è valorizzato
            try:
                my_id   = self.interface._format_peer(self.interface.my_info.id)
                quality = float(info.get('quality', 1.0))
                self.current_links = [(remote_id, my_id, quality)]
            except Exception:
                self.current_links = []

            # c) ridisegna subito (in refresh_graph il nodo locale diventerà "YOU")
            self.refresh_graph()

        # 6) Log pulito senza backslash
        try:
            text = json.dumps(clean, ensure_ascii=False)
        except Exception:
            text = str(clean)
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.log_list.insertItem(0, f"{ts} {text}")
        self.log_list.scrollToTop()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MeshDashWindow(port=None, refresh_interval=5000)
    window.show()
    sys.exit(app.exec())
