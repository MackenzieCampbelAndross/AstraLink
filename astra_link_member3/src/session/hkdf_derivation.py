"""HKDF SHA-256 session key derivation with context binding and directional key separation."""

import hashlib
from dataclasses import dataclass
from typing import Tuple

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from .session_context import SessionContext


@dataclass(frozen=True)
class DerivedSessionKeys:
    """Container for derived directional session keys."""

    initiator_to_responder_key: bytes
    responder_to_initiator_key: bytes
    initiator_id: str
    responder_id: str

    @property
    def t1_to_t2_key(self) -> bytes:
        """Return directional key for T1 -> T2 transmission."""
        if self.initiator_id == "T1":
            return self.initiator_to_responder_key
        elif self.responder_id == "T1":
            return self.responder_to_initiator_key
        else:
            return self.initiator_to_responder_key

    @property
    def t2_to_t1_key(self) -> bytes:
        """Return directional key for T2 -> T1 transmission."""
        if self.initiator_id == "T2":
            return self.initiator_to_responder_key
        elif self.responder_id == "T2":
            return self.responder_to_initiator_key
        else:
            return self.responder_to_initiator_key

    def __repr__(self) -> str:
        return (
            f"DerivedSessionKeys(initiator={self.initiator_id!r}, responder={self.responder_id!r}, "
            f"initiator_to_responder_key=[REDACTED], responder_to_initiator_key=[REDACTED])"
        )

    def __str__(self) -> str:
        return self.__repr__()


def derive_session_key_material(
    shared_secret: bytes,
    session_context: SessionContext,
) -> DerivedSessionKeys:
    """Derive directional session keys using HKDF-SHA256 bound to complete session context.
    
    Args:
        shared_secret: 32-byte raw ECDH shared secret.
        session_context: The SessionContext object binding protocol parameters.
        
    Returns:
        DerivedSessionKeys object containing distinct directional 32-byte keys.
    """
    if not shared_secret or not isinstance(shared_secret, bytes):
        raise ValueError("shared_secret must be non-empty bytes.")
    if not isinstance(session_context, SessionContext):
        raise TypeError("Expected SessionContext instance.")

    # 1. Compute salt derived from session ID and tracking epoch
    salt_data = f"ASTRA-SALT:{session_context.session_id}:{session_context.tracking_epoch}".encode("utf-8")
    salt = hashlib.sha256(salt_data).digest()

    # 2. Compute canonical info binding all session context parameters & ephemeral public keys
    info_prefix = (
        f"ASTRA-INFO:{session_context.protocol_version}:{session_context.initiator_id}:"
        f"{session_context.responder_id}:{session_context.session_id}:{session_context.tracking_epoch}:"
    ).encode("utf-8")

    info = (
        info_prefix
        + session_context.get_initiator_pub_bytes()
        + session_context.get_responder_pub_bytes()
    )

    # 3. Derive 64 bytes using HKDF-SHA256
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=64,
        salt=salt,
        info=info,
    )
    okm = hkdf.derive(shared_secret)

    init_to_resp_key = okm[:32]
    resp_to_init_key = okm[32:64]

    return DerivedSessionKeys(
        initiator_to_responder_key=init_to_resp_key,
        responder_to_initiator_key=resp_to_init_key,
        initiator_id=session_context.initiator_id,
        responder_id=session_context.responder_id,
    )
