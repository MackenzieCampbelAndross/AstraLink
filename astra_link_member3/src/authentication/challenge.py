"""Authentication Challenge dataclass and creation utilities."""

import secrets
import time
from dataclasses import dataclass
from typing import Any, Dict


@dataclass(frozen=True)
class AuthenticationChallenge:
    """Represents a fresh authentication challenge created by an initiator terminal."""

    initiator_id: str
    responder_id: str
    nonce: str
    session_id: str
    tracking_epoch: int
    timestamp: float
    protocol_version: str = "1.0"

    @classmethod
    def create_fresh(
        cls,
        initiator_id: str,
        responder_id: str,
        tracking_epoch: int = 1,
        protocol_version: str = "1.0",
    ) -> "AuthenticationChallenge":
        """Generate a fresh authentication challenge with cryptographically secure random nonces and session ID."""
        if not initiator_id or not isinstance(initiator_id, str):
            raise ValueError("initiator_id must be a non-empty string.")
        if not responder_id or not isinstance(responder_id, str):
            raise ValueError("responder_id must be a non-empty string.")

        nonce = secrets.token_hex(16)  # 32 hex chars (128 bits entropy)
        session_id = secrets.token_hex(16)  # 32 hex chars
        timestamp = round(time.time(), 3)

        return cls(
            initiator_id=initiator_id,
            responder_id=responder_id,
            nonce=nonce,
            session_id=session_id,
            tracking_epoch=tracking_epoch,
            timestamp=timestamp,
            protocol_version=protocol_version,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize challenge to dictionary format."""
        return {
            "initiator_id": self.initiator_id,
            "responder_id": self.responder_id,
            "nonce": self.nonce,
            "session_id": self.session_id,
            "tracking_epoch": self.tracking_epoch,
            "timestamp": self.timestamp,
            "protocol_version": self.protocol_version,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AuthenticationChallenge":
        """Deserialize challenge from dictionary format."""
        required = ["initiator_id", "responder_id", "nonce", "session_id", "tracking_epoch", "timestamp"]
        for field in required:
            if field not in data:
                raise ValueError(f"Missing required challenge field: {field}")

        return cls(
            initiator_id=str(data["initiator_id"]),
            responder_id=str(data["responder_id"]),
            nonce=str(data["nonce"]),
            session_id=str(data["session_id"]),
            tracking_epoch=int(data["tracking_epoch"]),
            timestamp=float(data["timestamp"]),
            protocol_version=str(data.get("protocol_version", "1.0")),
        )

    def __repr__(self) -> str:
        return (
            f"AuthenticationChallenge(initiator={self.initiator_id!r}, "
            f"responder={self.responder_id!r}, session_id={self.session_id[:8]}..., "
            f"epoch={self.tracking_epoch})"
        )
