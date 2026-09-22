"""Credential data models for Astra Link terminals."""

import hashlib
from dataclasses import dataclass
from typing import Any, Dict, Optional

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, x25519


@dataclass(frozen=True)
class TerminalPublicCredentials:
    """Public credential container for an Astra Link terminal.
    
    Contains only non-sensitive public key material that can be shared across terminals
    and registered in identity stores.
    """

    terminal_id: str
    identity_public_key: ed25519.Ed25519PublicKey
    agreement_public_key: x25519.X25519PublicKey

    def get_identity_bytes(self) -> bytes:
        """Return raw Ed25519 public key bytes (32 bytes)."""
        return self.identity_public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )

    def get_agreement_bytes(self) -> bytes:
        """Return raw X25519 public key bytes (32 bytes)."""
        return self.agreement_public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )

    def get_identity_pem(self) -> str:
        """Return Ed25519 public key as PEM string."""
        return self.identity_public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("utf-8")

    def get_agreement_pem(self) -> str:
        """Return X25519 public key as PEM string."""
        return self.agreement_public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("utf-8")

    def compute_fingerprint(self) -> str:
        """Compute a deterministic, human-readable fingerprint for the terminal identity.
        
        Derived from SHA-256 hash of the Ed25519 public key raw bytes.
        Format: SHA256:<HEX:COLON:PAIR>
        """
        raw_bytes = self.get_identity_bytes()
        digest = hashlib.sha256(raw_bytes).hexdigest().upper()
        colon_formatted = ":".join(digest[i : i + 2] for i in range(0, len(digest), 2))
        return f"SHA256:{colon_formatted}"

    def to_dict(self, name: Optional[str] = None) -> Dict[str, Any]:
        """Serialize public credentials to JSON-friendly dictionary."""
        return {
            "terminal_id": self.terminal_id,
            "name": name or f"Terminal {self.terminal_id}",
            "identity_public_key": self.get_identity_pem(),
            "agreement_public_key": self.get_agreement_pem(),
            "fingerprint": self.compute_fingerprint(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TerminalPublicCredentials":
        """Deserialize public credentials from a dictionary containing PEM public keys."""
        terminal_id = data.get("terminal_id")
        if not terminal_id or not isinstance(terminal_id, str):
            raise ValueError("Dictionary missing valid terminal_id.")

        id_pem = data.get("identity_public_key")
        agr_pem = data.get("agreement_public_key")

        if not id_pem or not agr_pem:
            raise ValueError(f"Dictionary missing identity_public_key or agreement_public_key for terminal {terminal_id}.")

        pub_id_key = serialization.load_pem_public_key(id_pem.encode("utf-8"))
        if not isinstance(pub_id_key, ed25519.Ed25519PublicKey):
            raise ValueError(f"identity_public_key for {terminal_id} is not Ed25519")

        pub_agr_key = serialization.load_pem_public_key(agr_pem.encode("utf-8"))
        if not isinstance(pub_agr_key, x25519.X25519PublicKey):
            raise ValueError(f"agreement_public_key for {terminal_id} is not X25519")

        return cls(
            terminal_id=terminal_id,
            identity_public_key=pub_id_key,
            agreement_public_key=pub_agr_key,
        )

    def __repr__(self) -> str:
        return (
            f"TerminalPublicCredentials(terminal_id={self.terminal_id!r}, "
            f"fingerprint={self.compute_fingerprint()!r})"
        )


@dataclass(frozen=True)
class TerminalPrivateCredentials:
    """Private credential container for an Astra Link terminal.
    
    Contains sensitive private key material. Must be stored securely and never logged.
    """

    terminal_id: str
    identity_private_key: ed25519.Ed25519PrivateKey
    agreement_private_key: x25519.X25519PrivateKey

    def __repr__(self) -> str:
        # Strictly mask private key material in string representations
        return f"TerminalPrivateCredentials(terminal_id={self.terminal_id!r}, keys=[REDACTED])"

    def __str__(self) -> str:
        return self.__repr__()


@dataclass(frozen=True)
class TerminalCredentials:
    """Full credential bundle containing public and optional private key material."""

    public_credentials: TerminalPublicCredentials
    private_credentials: Optional[TerminalPrivateCredentials] = None

    @property
    def terminal_id(self) -> str:
        return self.public_credentials.terminal_id

    @property
    def has_private_key(self) -> bool:
        return self.private_credentials is not None

    @property
    def fingerprint(self) -> str:
        return self.public_credentials.compute_fingerprint()

    def __repr__(self) -> str:
        priv_status = "present" if self.has_private_key else "absent"
        return (
            f"TerminalCredentials(terminal_id={self.terminal_id!r}, "
            f"fingerprint={self.fingerprint!r}, private_keys={priv_status})"
        )

    def __str__(self) -> str:
        return self.__repr__()
