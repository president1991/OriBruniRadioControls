import meshtastic
import meshtastic.serial_interface
from .models import MeshNode


class MeshtasticInterface:
    def __init__(self, port=None):
        # Se port è None, verrà usata la porta di default
        self.interface = meshtastic.serial_interface.SerialInterface(port)

    def get_nodes(self):
        nodes = []
        for node_id, node_info in self.interface.nodes.items():
            user = node_info.get('user', {}).get('longName', 'Unknown')
            battery_level = node_info.get('position', {}).get('batteryLevel', 'N/A')
            node = MeshNode(id=node_id, user=user, battery_level=battery_level)
            nodes.append(node)
        return nodes