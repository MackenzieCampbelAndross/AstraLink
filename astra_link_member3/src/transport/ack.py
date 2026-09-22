"""AckMessage data model and serialization for authenticated transport control."""

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass(frozen=True)
class AckMessage:
    """Represents a Cumulative and Selective ACK (SACK) control message."""

    protocol_version: str
    session_id: str
    transfer_id: str
    direction: str
    cumulative_ack: int
    selective_ack: List[int] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize AckMessage to dictionary format."""
        return {
            "protocol_version": self.protocol_version,
            "session_id": self.session_id,
            "transfer_id": self.transfer_id,
            "direction": self.direction,
            "cumulative_ack": int(self.cumulative_ack),
            "selective_ack": sorted(list(set(self.selective_ack))),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AckMessage":
        """Deserialize AckMessage from dictionary format."""
        required = ["protocol_version", "session_id", "transfer_id", "direction", "cumulative_ack"]
        for f in required:
            if f not in data:
                raise ValueError(f"Missing required AckMessage field: {f}")

        sack = [int(x) for x in data.get("selective_ack", [])]
        return cls(
            protocol_version=str(data["protocol_version"]),
            session_id=str(data["session_id"]),
            transfer_id=str(data["transfer_id"]),
            direction=str(data["direction"]),
            cumulative_ack=int(data["cumulative_ack"]),
            selective_ack=sorted(list(set(sack))),
        )

    def to_bytes(self) -> bytes:
        """Convert to canonical JSON UTF-8 bytes for AES-GCM control packet encryption."""
        json_str = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))
        return json_str.encode("utf-8")

    @classmethod
    def from_bytes(cls, data_bytes: bytes) -> "AckMessage":
        """Parse AckMessage from JSON UTF-8 bytes."""
        try:
            data_dict = json.loads(data_bytes.decode("utf-8"))
            return cls.from_dict(data_dict)
        except Exception as e:
            raise ValueError(f"Failed to parse AckMessage bytes: {e}") from e

    def __repr__(self) -> str:
        sack_str = f", SACK={self.selective_ack}" if self.selective_ack else ""
        return (
            f"AckMessage(transfer={self.transfer_id!r}, CumACK={self.cumulative_ack}{sack_str}, "
            f"direction={self.direction!r})"
        )
