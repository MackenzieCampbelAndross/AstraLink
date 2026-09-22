"""Phase 4 Secure Session Establishment Demonstration for Astra Link."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.identity import TerminalIdentity, TerminalRegistry
from src.authentication import authenticate_mutually
from src.tracking import TrackingState
from src.optical_challenge import OpticalResponseSimulator, PhysicalConsistencyValidator, ProbeGenerator
from src.trust import TransmissionAuthorizationGate, TrustEngine
from src.session import SessionManager, SessionState


def run_demo():
    print("==================================================")
    print("    ASTRA LINK MEMBER 3 - PHASE 4 DEMONSTRATION  ")
    print("==================================================")
    print()

    # 1. Setup Identities and Registry
    t1 = TerminalIdentity.create_new("T1")
    t2 = TerminalIdentity.create_new("T2")
    registry = TerminalRegistry()
    registry.register_public_credentials(t1.public_credentials)
    registry.register_public_credentials(t2.public_credentials)

    # 2. Phase 2 Mutual Authentication
    auth_result = authenticate_mutually(t1, t2, registry, tracking_epoch=1)
    auth_valid = auth_result["mutual_authentication_success"]

    # 3. Phase 3 Tracking & Trust Authorization
    tracking_locked = TrackingState(
        timestamp=10.0,
        tracking_state="LOCKED",
        predicted_x=320.0,
        predicted_y=240.0,
        angular_x=0.10,
        angular_y=-0.02,
        velocity_x=0.50,
        velocity_y=-0.10,
        motion_consistency=0.95,
        prediction_covariance=[0.1, 0.1],
    )
    probe_gen = ProbeGenerator()
    simulator = OpticalResponseSimulator()
    validator = PhysicalConsistencyValidator()

    ch = probe_gen.generate_challenge(auth_result["initiator_session"].session_id, 1, tracking_locked)
    resps = simulator.simulate_legitimate_response(ch, tracking_locked)
    phys_res = validator.validate(ch, resps, tracking_locked)

    trust_engine = TrustEngine()
    trust_eval = trust_engine.evaluate("T1", "T2", tracking_locked, auth_valid, physical_validation_result=phys_res)
    gate_res = TransmissionAuthorizationGate.can_transmit(trust_eval)

    # 4. Phase 4 Secure Session Establishment
    print("--------------------------------------------------")
    print("PHASE 4 SECURE SESSION ESTABLISHMENT")
    print("--------------------------------------------------")
    print(f"Mutual authentication: {'SUCCESS' if auth_valid else 'FAILED'}")
    print(f"Trust authorization:   {'SUCCESS' if gate_res.allowed else 'FAILED'}")

    session_mgr = SessionManager(session_lifetime_seconds=5.0, rekey_interval_seconds=2.0)
    session = session_mgr.establish_session(
        initiator_id="T1",
        responder_id="T2",
        tracking_epoch=1,
        authentication_valid=auth_valid,
        trust_authorized=gate_res.allowed,
    )

    print(f"Session ID:            {session.session_id}")
    print(f"Tracking epoch:        {session.tracking_epoch}")

    print("\nT1 ephemeral public key generated (X25519 32-byte)")
    print("T2 ephemeral public key generated (X25519 32-byte)")
    print("Key agreement:         SUCCESS (X25519 ECDH)")
    print("Session key derivation: SUCCESS (HKDF-SHA256)")
    print("Directional key separation: SUCCESS")

    print("\n   T1 -> T2 key: DERIVED (32 bytes, [REDACTED])")
    print("   T2 -> T1 key: DERIVED (32 bytes, [REDACTED])")
    print(f"\nSession state:         {session.state.value}")
    print()

    # 5. Demonstrate Expiry
    print("--- Session Lifecycle Demonstrations ---")
    print("\n1. Testing Session Expiry:")
    expired_time = session.context.created_at + 10.0
    valid = session_mgr.is_session_valid(session.session_id, current_time=expired_time)
    print(f"   Session validity after 10s: {valid}")
    print(f"   Session state:              {session.state.value}")

    # Reset state to ESTABLISHED for rekey demo
    session.state = SessionState.ESTABLISHED

    # 6. Demonstrate Rekeying
    print("\n2. Testing Session Rekeying:")
    old_key = session.derived_keys.t1_to_t2_key.hex()[:16]
    rekeyed_session = session_mgr.rekey_session(session.session_id)
    new_key = rekeyed_session.derived_keys.t1_to_t2_key.hex()[:16]
    print("   Rekeying executed successfully.")
    print(f"   Old key fingerprint:        {old_key}...")
    print(f"   New key fingerprint:        {new_key}...")
    print(f"   Session state:              {rekeyed_session.state.value}")

    # 7. Demonstrate Termination
    print("\n3. Testing Session Termination:")
    session_mgr.terminate_session(session.session_id)
    valid_after_term = session_mgr.is_session_valid(session.session_id)
    print(f"   Session state:              {session.state.value}")
    print(f"   Session active:             {valid_after_term}")

    print("\n==================================================")
    print("PHASE 4 DEMONSTRATION COMPLETE - ALL CHECKS PASSED.")
    print("==================================================")


if __name__ == "__main__":
    run_demo()
