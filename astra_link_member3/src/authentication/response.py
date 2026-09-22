"""Authentication Response dataclass and parsing utilities."""

from dataclasses import dataclass
from typing import Any, Dict


@dataclass(frozen=True)
class AuthenticationResponse:
    """Represents an authentication response produced by a responder terminal."""

    session_id: str
    responder_id: str
    signature_hex: str

    def get_signature_bytes(self) -> bytes:
        """Return raw signature bytes."""
        try:
            return bytes.fromhex(self.signature_hex)
        except ValueError as e:
            raise ValueError(f"Invalid hex signature string: {e}") from e

    def to_dict(self) -> Dict[str, Any]:
        """Serialize response to dictionary format."""
        return {
            "session_id": self.session_id,
            "responder_id": self.responder_id,
            "signature_hex": self.signature_hex,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AuthenticationResponse":
        """Deserialize response from dictionary format."""
        required = ["session_id", "responder_id", "signature_hex"]
        for field in required:
            if field not in data:
                raise ValueError(f"Missing required response field: {field}")

        return cls(
            session_id=str(data["session_id"]),
            responder_id=str(data["responder_id"]),
            signature_hex=str(data["signature_hex"]),
        )

    def __repr__(self) -> str:
        sig_prefix = self.signature_hex[:12] if self.signature_hex else "NONE"
        return (
            f"AuthenticationResponse(responder={self.responder_id!r}, "
            f"session_id={self.session_id[:8]}..., signature={sig_prefix}...)"
        )
