"""Ephemeral X25519 key exchange and ECDH shared secret derivation."""

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import x25519


class EphemeralKeyPair:
    """Container for an ephemeral X25519 key pair generated for a single secure session."""

    def __init__(self, terminal_id: str, private_key: x25519.X25519PrivateKey):
        if not terminal_id or not isinstance(terminal_id, str):
            raise ValueError("terminal_id must be a non-empty string.")
        if not isinstance(private_key, x25519.X25519PrivateKey):
            raise ValueError("Expected X25519PrivateKey instance.")

        self.terminal_id = terminal_id
        self._private_key = private_key
        self.public_key = private_key.public_key()

    @classmethod
    def generate(cls, terminal_id: str) -> "EphemeralKeyPair":
        """Generate a fresh X25519 ephemeral key pair."""
        private_key = x25519.X25519PrivateKey.generate()
        return cls(terminal_id=terminal_id, private_key=private_key)

    def get_public_bytes(self) -> bytes:
        """Return raw 32-byte X25519 public key bytes."""
        return self.public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )

    def get_public_pem(self) -> str:
        """Return PEM formatted X25519 public key."""
        return self.public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("utf-8")

    def __repr__(self) -> str:
        return f"EphemeralKeyPair(terminal_id={self.terminal_id!r}, private_key=[REDACTED])"

    def __str__(self) -> str:
        return self.__repr__()


class KeyExchange:
    """Executes X25519 ECDH key exchange between ephemeral key pairs."""

    @staticmethod
    def derive_shared_secret(
        our_ephemeral: EphemeralKeyPair,
        peer_public_key: x25519.X25519PublicKey,
    ) -> bytes:
        """Perform X25519 Diffie-Hellman key exchange to derive a 32-byte raw shared secret."""
        if not isinstance(our_ephemeral, EphemeralKeyPair):
            raise TypeError("Expected EphemeralKeyPair instance for our_ephemeral.")
        if not isinstance(peer_public_key, x25519.X25519PublicKey):
            raise TypeError("Expected X25519PublicKey instance for peer_public_key.")

        # X25519 ECDH exchange
        return our_ephemeral._private_key.exchange(peer_public_key)
