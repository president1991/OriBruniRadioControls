from dataclasses import dataclass, field
from typing import Dict, Any, Optional

@dataclass
class MeshNode:
    """
    Rappresenta un nodo nella rete mesh Meshtastic
    con il supporto per attributi aggiuntivi.
    """
    id: str
    user: str = "Sconosciuto"
    battery_level: int = 0
    raw_data: Dict[str, Any] = field(default_factory=dict)  # Per conservare i dati grezzi dal dispositivo
    
    def __repr__(self) -> str:
        return f"MeshNode(id={self.id}, user={self.user}, battery={self.battery_level}%)"