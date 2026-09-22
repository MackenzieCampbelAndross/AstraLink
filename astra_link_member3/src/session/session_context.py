"""Session state model and structured session context."""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import x25519


class SessionState(Enum):
    """Lifecycle states for secure sessions."""

    NO_SESSION = "NO_SESSION"
    NEGOTIATING = "NEGOTIATING"
    ESTABLISHED = "ESTABLISHED"
    EXPIRED = "EXPIRED"
    TERMINATED = "TERMINATED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class SessionContext:
    """Immutable context binding security parameters to a session."""

    session_id: str
    initiator_id: str
    responder_id: str
    tracking_epoch: int
    created_at: float
    initiator_ephemeral_public_key: x25519.X25519PublicKey
    responder_ephemeral_public_key: x25519.X25519PublicKey
    protocol_version: str = "1.0"

    def get_initiator_pub_bytes(self) -> bytes:
        return self.initiator_ephemeral_public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )

    def get_responder_pub_bytes(self) -> bytes:
        return self.responder_ephemeral_public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize context to dictionary without exposing secret material."""
        return {
            "session_id": self.session_id,
            "initiator_id": self.initiator_id,
            "responder_id": self.responder_id,
            "tracking_epoch": self.tracking_epoch,
            "created_at": self.created_at,
            "protocol_version": self.protocol_version,
            "initiator_ephemeral_pub_bytes_len": len(self.get_initiator_pub_bytes()),
            "responder_ephemeral_pub_bytes_len": len(self.get_responder_pub_bytes()),
        }

    def __repr__(self) -> str:
        return (
            f"SessionContext(session_id={self.session_id[:8]}..., "
            f"initiator={self.initiator_id!r}, responder={self.responder_id!r}, "
            f"epoch={self.tracking_epoch})"
        )
