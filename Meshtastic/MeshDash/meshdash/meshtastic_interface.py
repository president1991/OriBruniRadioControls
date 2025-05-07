import meshtastic
import meshtastic.serial_interface
from pubsub import pub
from .models import MeshNode

class MeshtasticInterface:
    def __init__(self, port=None):
        # Apri la porta e sottoscrivi le callback
        self.interface = meshtastic.serial_interface.SerialInterface(port)
        self._links_buffer = []
        
        # Subscribe per pacchetti neighbor-info e telemetry
        pub.subscribe(self._on_receive_neighbors, "meshtastic.receive")
        pub.subscribe(self._on_receive_telemetry, "meshtastic.receive.telemetry")

    def _on_receive_neighbors(self, packet, interface=None):
        """
        Callback per i pacchetti che contengono informazioni sui vicini
        """
        decoded = packet.get('decoded', {})
        if 'neighbors' not in decoded:
            return
        src = packet.get('fromId')
        for nb in decoded['neighbors']:
            dst = nb.get('nodeId')
            snr = nb.get('snr', 0)
            entry = (src, dst, snr)
            if entry not in self._links_buffer:
                self._links_buffer.append(entry)

    def _on_receive_telemetry(self, packet, interface=None):
        """
        Callback per i pacchetti telemetry: aggiorna i metrics dei nodi
        """
        decoded = packet.get('decoded', {})
        telemetry = decoded.get('telemetry', {})
        metrics = telemetry.get('deviceMetrics', {})
        node_num = packet.get('from')
        # Se il nodo è già presente, aggiorna il livello batteria
        node_info = self.interface.nodes.get(node_num)
        if node_info and metrics:
            # Assicura che la struttura 'position' esista
            if 'position' not in node_info:
                node_info['position'] = {}
            node_info['position']['batteryLevel'] = metrics.get('batteryLevel')

    def get_nodes(self):
        """
        Ritorna la lista di MeshNode rilevati, con id, nome e livello batteria aggiornato.
        """
        nodes = []
        for node_num, node_info in self.interface.nodes.items():
            user = node_info.get('user', {}).get('longName', 'Unknown')
            battery = node_info.get('position', {}).get('batteryLevel', 'N/A')
            nodes.append(MeshNode(id=node_num, user=user, battery_level=battery))
        return nodes

    def get_links(self) -> list[tuple[str, str, float]]:
        """
        Restituisce e svuota il buffer dei link raccolti dai neighbor-info.
        """
        links = list(self._links_buffer)
        self._links_buffer.clear()
        return links

    def request_telemetry(self):
        """
        Richiede ai nodi di inviare dati telemetry (include neighbor-info se supportato dal firmware).
        """
        # SerialInterface potrebbe offrire un metodo per requestTelemetry
        if not hasattr(self.interface, 'requestTelemetry'):
            raise NotImplementedError("La richiesta di telemetry non è supportata da questa interfaccia.")
        # Invia la richiesta a tutti i nodi
        self.interface.requestTelemetry()  
