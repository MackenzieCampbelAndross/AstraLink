"""Canonical transcript builder for binding authentication context deterministically."""

import json
from typing import Any, Dict

from .challenge import AuthenticationChallenge


def compute_canonical_transcript(
    challenge: AuthenticationChallenge,
    direction: str = "RESPONSE",
) -> bytes:
    """Compute deterministic canonical transcript bytes for a given challenge context.
    
    Binds:
        - protocol_version
        - initiator_id
        - responder_id
        - nonce
        - session_id
        - tracking_epoch
        - timestamp
        - direction
        
    Returns:
        UTF-8 encoded JSON bytes with lexicographically sorted keys.
    """
    if not isinstance(challenge, AuthenticationChallenge):
        raise TypeError("Expected AuthenticationChallenge instance.")

    canonical_dict: Dict[str, Any] = {
        "direction": str(direction).upper(),
        "initiator_id": challenge.initiator_id,
        "nonce": challenge.nonce,
        "protocol_version": challenge.protocol_version,
        "responder_id": challenge.responder_id,
        "session_id": challenge.session_id,
        "timestamp": float(challenge.timestamp),
        "tracking_epoch": int(challenge.tracking_epoch),
    }

    # sort_keys=True and separators=(',', ':') guarantees deterministic canonical bytes
    canonical_json_str = json.dumps(canonical_dict, sort_keys=True, separators=(",", ":"))
    return canonical_json_str.encode("utf-8")
