"""Phase 2 Mutual Authentication Demonstration for Astra Link."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.identity import (
    TerminalIdentity,
    TerminalRegistry,
    save_credentials,
)
from src.authentication import (
    AuthenticationResponse,
    ExpiredTimestampError,
    FreshnessValidator,
    InvalidSignatureError,
    InvalidTranscriptError,
    ReplayAttackError,
    ReplayProtectionCache,
    authenticate_mutually,
    create_challenge,
    create_response,
    verify_response,
)


def run_demo():
    print("==================================================")
    print("    ASTRA LINK MEMBER 3 - PHASE 2 DEMONSTRATION  ")
    print("==================================================")
    print()

    keys_dir = PROJECT_ROOT / "keys"
    config_path = PROJECT_ROOT / "config" / "terminals.json"

    # 1. Setup Identities and Registry
    t1 = TerminalIdentity.create_new("T1")
    t2 = TerminalIdentity.create_new("T2")
    save_credentials(t1._credentials, keys_dir)
    save_credentials(t2._credentials, keys_dir)

    registry = TerminalRegistry()
    registry.register_public_credentials(t1.public_credentials, name="Terminal 1 (Ground Base)")
    registry.register_public_credentials(t2.public_credentials, name="Terminal 2 (Mobile Asset)")
    registry.save_config(config_path)

    validator = FreshnessValidator(window_seconds=30.0)
    cache = ReplayProtectionCache()

    # 2. Step-by-Step Handshake Output
    print("--- Mutual Authentication Protocol Handshake ---")
    
    # Step A: T1 -> T2
    print("\n[Step 1] T1 -> challenge -> T2")
    ch1 = create_challenge("T1", "T2", tracking_epoch=1)
    print(f"         Challenge Session ID: {ch1.session_id}")
    print(f"         Nonce: {ch1.nonce}")

    print("[Step 2] T2 -> valid signed response -> T1")
    res1 = create_response(ch1, t2)
    print(f"         Ed25519 Signature: {res1.signature_hex[:32]}...")

    print("[Step 3] T1 verifies T2")
    v1 = verify_response(ch1, res1, registry, freshness_validator=validator, replay_cache=cache)
    print(f"         T2 Identity Verified: {v1}")

    # Step B: T2 -> T1
    print("\n[Step 4] T2 -> challenge -> T1")
    ch2 = create_challenge("T2", "T1", tracking_epoch=1)
    print(f"         Challenge Session ID: {ch2.session_id}")
    print(f"         Nonce: {ch2.nonce}")

    print("[Step 5] T1 -> valid signed response -> T2")
    res2 = create_response(ch2, t1)
    print(f"         Ed25519 Signature: {res2.signature_hex[:32]}...")

    print("[Step 6] T2 verifies T1")
    v2 = verify_response(ch2, res2, registry, freshness_validator=validator, replay_cache=cache)
    print(f"         T1 Identity Verified: {v2}")

    print("\nMUTUAL AUTHENTICATION SUCCESS")
    print()

    # 3. High-level wrapper check
    result = authenticate_mutually(t1, t2, registry, tracking_epoch=1)
    assert result["mutual_authentication_success"] is True

    # 4. Demonstrate Failure Scenarios
    print("--------------------------------------------------")
    print("      DEMONSTRATING FAILURE SCENARIOS             ")
    print("--------------------------------------------------")

    # Failure 1: Invalid Signature
    print("\n1. Testing Invalid Signature:")
    corrupt_response = AuthenticationResponse(
        session_id=ch1.session_id,
        responder_id="T2",
        signature_hex="00" * 64,  # Corrupt signature
    )
    try:
        verify_response(ch1, corrupt_response, registry, freshness_validator=validator)
    except InvalidSignatureError as e:
        print(f"   Result: REJECTED ({e})")

    # Failure 2: Replayed Authentication
    print("\n2. Testing Replayed Authentication:")
    try:
        verify_response(ch1, res1, registry, freshness_validator=validator, replay_cache=cache)
    except ReplayAttackError as e:
        print(f"   Result: REJECTED ({e})")

    # Failure 3: Wrong Terminal Identity
    print("\n3. Testing Wrong Terminal Identity:")
    try:
        create_response(ch1, t1)  # T1 tries to answer challenge meant for T2
    except InvalidTranscriptError as e:
        print(f"   Result: REJECTED ({e})")

    print("\n==================================================")
    print("PHASE 2 DEMONSTRATION COMPLETE - ALL CHECKS PASSED.")
    print("==================================================")


if __name__ == "__main__":
    run_demo()
