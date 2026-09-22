"""EncryptedPacket data model and Associated Authenticated Data (AAD) computation."""

import json
from dataclasses import dataclass
from typing import Any, Dict


def compute_packet_aad(
    protocol_version: str,
    session_id: str,
    transfer_id: str,
    sequence_number: int,
    direction: str,
) -> bytes:
    """Compute deterministic canonical Associated Authenticated Data (AAD) bytes.
    
    Binds:
        - protocol_version
        - session_id
        - transfer_id
        - sequence_number
        - direction
    """
    aad_dict: Dict[str, Any] = {
        "direction": str(direction).upper(),
        "protocol_version": str(protocol_version),
        "sequence_number": int(sequence_number),
        "session_id": str(session_id),
        "transfer_id": str(transfer_id),
    }

    # sort_keys=True and separators=(',', ':') guarantees deterministic AAD bytes across terminals
    aad_json_str = json.dumps(aad_dict, sort_keys=True, separators=(",", ":"))
    return aad_json_str.encode("utf-8")


@dataclass(frozen=True)
class EncryptedPacket:
    """Represents a wire-format encrypted packet containing AES-GCM ciphertext and authenticated metadata."""

    protocol_version: str
    session_id: str
    transfer_id: str
    sequence_number: int
    direction: str
    nonce_hex: str
    ciphertext_hex: str

    def get_nonce_bytes(self) -> bytes:
        """Return raw 12-byte GCM nonce."""
        try:
            return bytes.fromhex(self.nonce_hex)
        except ValueError as e:
            raise ValueError(f"Invalid hex nonce string: {e}") from e

    def get_ciphertext_bytes(self) -> bytes:
        """Return raw ciphertext bytes (includes 16-byte GCM authentication tag)."""
        try:
            return bytes.fromhex(self.ciphertext_hex)
        except ValueError as e:
            raise ValueError(f"Invalid hex ciphertext string: {e}") from e

    def compute_aad(self) -> bytes:
        """Compute expected canonical AAD bytes for this packet."""
        return compute_packet_aad(
            protocol_version=self.protocol_version,
            session_id=self.session_id,
            transfer_id=self.transfer_id,
            sequence_number=self.sequence_number,
            direction=self.direction,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize packet to dictionary format."""
        return {
            "protocol_version": self.protocol_version,
            "session_id": self.session_id,
            "transfer_id": self.transfer_id,
            "sequence_number": self.sequence_number,
            "direction": self.direction,
            "nonce_hex": self.nonce_hex,
            "ciphertext_hex": self.ciphertext_hex,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EncryptedPacket":
        """Deserialize packet from dictionary format."""
        required = [
            "protocol_version",
            "session_id",
            "transfer_id",
            "sequence_number",
            "direction",
            "nonce_hex",
            "ciphertext_hex",
        ]
        for f in required:
            if f not in data:
                raise ValueError(f"Missing required packet field: {f}")

        return cls(
            protocol_version=str(data["protocol_version"]),
            session_id=str(data["session_id"]),
            transfer_id=str(data["transfer_id"]),
            sequence_number=int(data["sequence_number"]),
            direction=str(data["direction"]),
            nonce_hex=str(data["nonce_hex"]),
            ciphertext_hex=str(data["ciphertext_hex"]),
        )

    def __repr__(self) -> str:
        ctx_prefix = self.ciphertext_hex[:12] if self.ciphertext_hex else "NONE"
        return (
            f"EncryptedPacket(seq={self.sequence_number}, transfer={self.transfer_id!r}, "
            f"session_id={self.session_id[:8]}..., direction={self.direction!r}, ciphertext={ctx_prefix}...)"
        )
