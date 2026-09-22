"""Session rekeying logic producing fresh ephemeral keys and session key material."""

import time
from typing import Tuple

from .hkdf_derivation import DerivedSessionKeys, derive_session_key_material
from .key_exchange import EphemeralKeyPair, KeyExchange
from .session_context import SessionContext


def execute_rekey(
    existing_context: SessionContext,
    initiator_ephemeral: EphemeralKeyPair,
    responder_ephemeral: EphemeralKeyPair,
) -> Tuple[SessionContext, DerivedSessionKeys]:
    """Execute session rekeying by generating new ephemeral key material while retaining session context.
    
    Returns:
        Tuple of (updated_SessionContext, new_DerivedSessionKeys)
    """
    if not isinstance(existing_context, SessionContext):
        raise TypeError("Expected SessionContext instance.")
    if not isinstance(initiator_ephemeral, EphemeralKeyPair):
        raise TypeError("Expected EphemeralKeyPair for initiator_ephemeral.")
    if not isinstance(responder_ephemeral, EphemeralKeyPair):
        raise TypeError("Expected EphemeralKeyPair for responder_ephemeral.")

    if initiator_ephemeral.terminal_id != existing_context.initiator_id:
        raise ValueError(
            f"Initiator ID mismatch: ephemeral has '{initiator_ephemeral.terminal_id}', "
            f"context has '{existing_context.initiator_id}'"
        )

    if responder_ephemeral.terminal_id != existing_context.responder_id:
        raise ValueError(
            f"Responder ID mismatch: ephemeral has '{responder_ephemeral.terminal_id}', "
            f"context has '{existing_context.responder_id}'"
        )

    # 1. Create updated SessionContext with fresh ephemeral public keys and updated timestamp
    new_context = SessionContext(
        session_id=existing_context.session_id,
        initiator_id=existing_context.initiator_id,
        responder_id=existing_context.responder_id,
        tracking_epoch=existing_context.tracking_epoch,
        created_at=round(time.time(), 3),
        initiator_ephemeral_public_key=initiator_ephemeral.public_key,
        responder_ephemeral_public_key=responder_ephemeral.public_key,
        protocol_version=existing_context.protocol_version,
    )

    # 2. Derive new X25519 ECDH shared secret
    new_shared_secret = KeyExchange.derive_shared_secret(
        initiator_ephemeral, responder_ephemeral.public_key
    )

    # 3. Derive fresh directional session key material via HKDF SHA-256
    new_keys = derive_session_key_material(new_shared_secret, new_context)

    return new_context, new_keys
