import meshtastic
import meshtastic.serial_interface
from pubsub import pub
from .models import MeshNode
import json
from .db_logger import log_message, log_telemetry
from collections.abc import Mapping
import logging
import threading


class MeshtasticInterface:
    def __init__(self, port=None):
        self.interface = meshtastic.serial_interface.SerialInterface(port)
        try:
            self.my_info = self.interface.myInfo
        except AttributeError:
            self.my_info = None
        self._links_buffer: set[tuple[str, str, float]] = set()  # Usa un set per evitare duplicati
        self._links_buffer_lock = threading.Lock()  # Aggiungi un lock
        self.neighbor_data: dict[str, dict] = {}
        self._neighbor_data_lock = threading.Lock()  # Aggiungi un lock

        # Solo tre sottoscrizioni, senza duplicati:
        pub.subscribe(self._on_receive_packet,    "meshtastic.receive")
        pub.subscribe(self._on_receive_neighbors,"meshtastic.receive")
        pub.subscribe(self._on_receive_telemetry,"meshtastic.receive.telemetry")

    def _make_jsonable(self, obj):
        # 1) tipi JSON-safe
        if isinstance(obj, (str, int, float, bool, type(None))):
            return obj
        # 2) bytes → decode o hex
        if isinstance(obj, bytes):
            try:
                return obj.decode("utf-8")
            except UnicodeDecodeError:
                return obj.hex()
        # 3) Mapping → dict
        if isinstance(obj, Mapping):
            return {k: self._make_jsonable(v) for k, v in obj.items()}
        # 4) lista/tupla → list
        if isinstance(obj, (list, tuple)):
            return [self._make_jsonable(v) for v in obj]
        # 5) oggetti custom → __dict__
        if hasattr(obj, '__dict__'):
            return self._make_jsonable(vars(obj))
        # 6) fallback → stringa
        return str(obj)

    def _format_peer(self, peer_id):
        """
        Converte l'ID numerico del nodo in stringa HEX formattata 'XXXXXXXX'.
        Se non è un intero, ritorna str(peer_id).
        """
        try:
            pid = int(peer_id)
            hexstr = f"{pid:08X}"
            return f"{hexstr[:4]}{hexstr[4:]}"
        except (ValueError, TypeError):
            return str(peer_id)

    def _on_receive_packet(self, packet, interface=None):
        peer_id = packet.get('from', packet.get('fromId', 'unknown'))
        peer = self._format_peer(peer_id)

        payload = packet.get('decoded', packet)
        clean = self._make_jsonable(payload)
        # Deserializza JSON interno se presente
        nested = clean.get('payload')
        if isinstance(nested, str):
            try:
                clean['payload'] = json.loads(nested)
            except json.JSONDecodeError:
                pass

        log_message('received', peer, json.dumps(clean))

        if clean.get('type') == 'neigh_info':
            sender_id = self._format_peer(packet.get('fromId', packet.get('from')))

            for neighbor in clean.get('data', []):  # Assumiamo che 'data' sia una lista di vicini
                target_id = self._format_peer(neighbor.get('node_id'))
                quality = neighbor.get('link_quality', 1.0)  # Usa un valore di default

                # Aggiungi il link in entrambe le direzioni (non diretto)
                with self._links_buffer_lock:  # Acquisisci il lock prima di accedere a _links_buffer
                    self._links_buffer.add((sender_id, target_id, quality))
                    self._links_buffer.add((target_id, sender_id, quality))

            logging.debug(f"ricevuto neigh_info, links: {self._links_buffer}")  # Corretto
            pub.sendMessage("meshdash.new_links")  # Notifica alla GUI

    def _on_receive_neighbors(self, packet, interface=None):
        decoded = packet.get("decoded", {})
        neigh = decoded.get("neighbors")
        logging.debug(f"_on_receive_neighbors: decoded keys = {list(decoded.keys())}")
        logging.debug(f"_on_receive_neighbors: neighbors = {neigh}")
        if not neigh:
            return

        src = self._format_peer(packet.get("fromId"))
        for nb in neigh:
            dst   = self._format_peer(nb.get("nodeId"))
            snr   = nb.get("snr", 0)
            entry = (src, dst, snr)
            with self._links_buffer_lock:  # Acquisisci il lock prima di accedere a _links_buffer
                if entry not in self._links_buffer:
                    self._links_buffer.add(entry)  # Usa add per un set
        with self._neighbor_data_lock:
            self.neighbor_data[dst] = {  # Acquisisci il lock prima di accedere a neighbor_data
                "rx_snr":    snr,
                "rx_rssi":   nb.get("rssi"),
                "hop_limit": nb.get("hopLimit"),
                "hop_start": nb.get("hopStart"),
                "relay_node":nb.get("relayNode"),
                # …
            }
        logging.debug(f"_on_receive_neighbors: links_buffer = {self._links_buffer}")
        logging.debug(f"_on_receive_neighbors: neighbor_data keys = {list(self.neighbor_data.keys())}")
        # Se vuoi, notifica subito la GUI:
        pub.sendMessage("meshdash.new_neighbors")

    def _on_receive_telemetry(self, packet, interface=None):
        decoded = packet.get('decoded', {})
        telemetry = decoded.get('telemetry', {})
        metrics = telemetry.get('deviceMetrics', {})

        peer_id = packet.get('from', packet.get('fromId', 'unknown'))
        peer = self._format_peer(peer_id)
        if metrics:
            log_telemetry(peer, metrics)

        node_num = packet.get('from')
        node_info = self.interface.nodes.get(node_num)
        if node_info and metrics:
            node_info.setdefault('position', {})['batteryLevel'] = metrics.get('batteryLevel')

    def get_nodes(self):
        nodes = []
        for node_num, node_info in self.interface.nodes.items():
            peer = self._format_peer(node_num)
            #user = node_info.get('user', {}).get('longName', peer)
            ui   = node_info.get('user', {})
            # preferisci il nome “shortName” se presente, altrimenti il longName
            user = ui.get('shortName') or ui.get('longName') or peer
            battery = node_info.get('position', {}).get('batteryLevel', 'N/A')
            nodes.append(MeshNode(id=peer, user=user, battery_level=battery))
        return nodes

    def get_links(self) -> list[tuple[str, str, float]]:
        with self._links_buffer_lock:  # Acquisisci il lock prima di accedere a _links_buffer
            links = list(self._links_buffer)
            self._links_buffer.clear()
        return links

    def request_telemetry(self, *args, **kwargs):
        if not hasattr(self.interface, 'requestTelemetry'):
            raise NotImplementedError("La richiesta di telemetry non è supportata da questa interfaccia.")
        self.interface.requestTelemetry(*args, **kwargs)

    def send_text(self, text: str, dest=None):
        result = self.interface.sendText(text, dest)
        peer = self._format_peer(dest) if dest is not None else 'broadcast'
        log_message('sent', peer, text)
        return result