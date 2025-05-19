import json
import threading
import queue
import logging
from typing import Any, Dict, List, Optional, Tuple
from meshtastic.serial_interface import SerialInterface
from meshtastic import mesh_interface
from .models import MeshNode
from pubsub import pub
from .db_logger import log_message, log_telemetry

logger = logging.getLogger(__name__)

class MeshInterfaceWorker(threading.Thread):
    """
    Thread to asynchronously process logging tasks to avoid blocking callbacks.
    """
    def __init__(self) -> None:
        super().__init__(daemon=True)
        self._tasks: "queue.Queue[Dict[str, Any]]" = queue.Queue()
        self._stop_event = threading.Event()

    def run(self) -> None:
        while not self._stop_event.is_set():
            try:
                task = self._tasks.get(timeout=1)
                if task["type"] == "message":
                    log_message(task["direction"], task["peer"], task["payload"])
                elif task["type"] == "telemetry":
                    log_telemetry(task["peer"], task["metrics"])
            except queue.Empty:
                continue
            except Exception:
                logger.exception("Error processing log task")

    def stop(self) -> None:
        self._stop_event.set()

    def enqueue_message(self, direction: str, peer: str, payload: Any) -> None:
        self._tasks.put({"type": "message", "direction": direction, "peer": peer, "payload": payload})

    def enqueue_telemetry(self, peer: str, metrics: Dict[str, Any]) -> None:
        self._tasks.put({"type": "telemetry", "peer": peer, "metrics": metrics})

class MeshInterface:
    """
    High-level interface for Meshtastic, handling serialization, callbacks,
    and asynchronous DB logging.
    """
    def __init__(self, port: str, baudrate: int = 921600) -> None:
        self.worker = MeshInterfaceWorker()
        self.worker.start()

        try:
            # Correzione: usa SerialInterface invece di MeshInterface
            self.interface = SerialInterface(devPath=port, debugOut=False)
        except Exception as e:
            logger.exception("Failed to open serial interface")
            raise

        self._links_buffer: List[Dict[str, Any]] = []
        self._links_lock = threading.Lock()

        # Subscribe with a single handler and dispatch by packet type
        pub.subscribe(self._on_receive, "meshtastic.receive")

    def close(self) -> None:
        """Stop worker and close interface."""
        self.worker.stop()
        try:
            self.interface.close()
        except Exception:
            logger.exception("Error closing interface")

    def _make_jsonable(self, obj: Any) -> Any:
        try:
            json.dumps(obj)
            return obj
        except (TypeError, OverflowError):
            if isinstance(obj, dict):
                return {self._make_jsonable(k): self._make_jsonable(v) for k, v in obj.items()}
            if isinstance(obj, (list, tuple)):
                return [self._make_jsonable(o) for o in obj]
            return repr(obj)

    def _format_peer(self, peer_id: int) -> str:
        return hex(peer_id)

    def _on_receive(self, packet: Any) -> None:
        """Unified callback for all packet types."""
        try:
            peer = self._format_peer(packet.get("from", {}).get("userId", 0))
            direction = packet.get("when", "unknown")
            # Log grezzo (sent/received) in background
            self.worker.enqueue_message(direction, peer, packet)


            # Handle neighbor info
#            if packet.get("decoded") and packet["decoded"].get("neigh_info"):  # neigh_info packet
#                neighbors = packet["decoded"]["neigh_info"].get("neighbors", [])
#                with self._links_lock:
#                    self._links_buffer.extend(
#                        [{"from": peer, "to": self._format_peer(n.get("id")), "rssi": n.get("rssi")} for n in neighbors]
#                    )

            # Handle TEXT_MESSAGE_APP JSON payloads for neigh_info
            decoded = packet.get("decoded", {}) or {}
            text = decoded.get("text") if isinstance(decoded, dict) else None
            if text:
                try:
                    obj = json.loads(text)
                    if obj.get("type") == "neigh_info":
                        data_list = obj.get("data", [])
                        with self._links_lock:
                            self._links_buffer.extend([
                                {
                                    "from": peer,
                                    "to": self._format_peer(entry.get("id")),
                                    "rssi": entry.get("rssi"),
                                }
                                for entry in data_list
                            ])
                        # Notifica subito la GUI di nuovi link
                        pub.sendMessage("meshdash.new_links")
                except Exception:
                    logger.exception("Errore parsing JSON di neigh_info")

            # Handle telemetry
#            if packet.get("decoded") and packet["decoded"].get("deviceMetrics"):
#                metrics = packet["decoded"]["deviceMetrics"]
#                self.worker.enqueue_telemetry(peer, metrics)

            # Handle structured deviceMetrics (telemetria)
            if decoded.get("deviceMetrics"):
                metrics = decoded["deviceMetrics"]
                self.worker.enqueue_telemetry(peer, metrics)

        except (AttributeError, KeyError) as e:
            logger.warning("Malformed packet received: %s", e)
        except Exception:
            logger.exception("Error in receive callback")

    def get_nodes(self) -> List[MeshNode]:
        """Return a list of MeshNode instances from current interface state."""
        nodes: List[MeshNode] = []
        
        # Correzione: Accedi a nodes attraverso l'interfaccia
        if hasattr(self.interface, 'nodes'):
            for node_id, node_info in self.interface.nodes.items():
                try:
                    # Estrai i dati grezzi per visualizzazione migliorata
                    node = MeshNode(
                        id=str(node_id), 
                        user=node_info.get('user', 'Unknown'),
                        battery_level=int(node_info.get('batteryLevel', 0)),
                        raw_data=node_info  # Mantieni i dati grezzi per un migliore rendering
                    )
                    nodes.append(node)
                except Exception as e:
                    logger.exception(f"Error parsing node info: {node_info}")
        else:
            logger.warning("No nodes attribute in interface")
            
        return nodes

    def get_links(self) -> List[Tuple[str, str, float]]:
        """Return and clear the current buffered links as tuples."""
        with self._links_lock:
            # Converto il formato del buffer in tuple (da, a, qualità)
            links = [(link["from"], link["to"], float(link.get("rssi", 0))) 
                     for link in self._links_buffer]
            self._links_buffer.clear()
        return links

    def request_telemetry(self, node_id: Optional[str] = None) -> None:
        """Request telemetry data for a specific node or broadcast if None."""
        try:
            if node_id:
                self.interface.requestTelemetry(node_id)
            else:
                self.interface.sendText("!stats")  # Comando per richiedere statistiche da tutti
        except Exception as e:
            logger.exception(f"Failed to request telemetry: {e}")

    def send_text(self, text: str, destination: Optional[str] = None) -> None:
        """Send a text message to the network or specific node."""
        try:
            if destination:
                self.interface.sendText(text, destinationId=destination)
            else:
                self.interface.sendText(text)
        except Exception as e:
            logger.exception(f"Failed to send text: {text}, error: {e}")