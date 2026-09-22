"""Phase 3 Trust, Optical Challenge, and Transmission Authorization Demonstration."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.identity import TerminalIdentity, TerminalRegistry
from src.authentication import authenticate_mutually
from src.tracking import TrackingState
from src.optical_challenge import (
    OpticalResponseSimulator,
    PhysicalConsistencyValidator,
    ProbeGenerator,
)
from src.trust import (
    SecurityLogger,
    TransmissionAuthorizationGate,
    TrustEngine,
)


def run_demo():
    print("==================================================")
    print("    ASTRA LINK MEMBER 3 - PHASE 3 DEMONSTRATION  ")
    print("==================================================")
    print()

    # 1. System Setup
    t1 = TerminalIdentity.create_new("T1")
    t2 = TerminalIdentity.create_new("T2")
    registry = TerminalRegistry()
    registry.register_public_credentials(t1.public_credentials)
    registry.register_public_credentials(t2.public_credentials)

    logger = SecurityLogger()
    probe_gen = ProbeGenerator(probe_count=4)
    simulator = OpticalResponseSimulator()
    validator = PhysicalConsistencyValidator()
    trust_engine = TrustEngine(min_motion_consistency=0.80)

    # Base Member 2 Tracking State
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

    # Perform Mutual Authentication Handshake
    auth_result = authenticate_mutually(t1, t2, registry)
    auth_valid = auth_result["mutual_authentication_success"]

    # =========================================================================
    # SCENARIO 1: LEGITIMATE TERMINAL
    # =========================================================================
    print("--------------------------------------------------")
    print("SCENARIO 1: Legitimate Terminal")
    print("--------------------------------------------------")
    print(f"Member 2 Tracking State: {tracking_locked.tracking_state} (Motion Consistency: {tracking_locked.motion_consistency:.2f})")
    print(f"Mutual Authentication:   {'VALID' if auth_valid else 'INVALID'}")

    challenge1 = probe_gen.generate_challenge(auth_result["initiator_session"].session_id, 1, tracking_locked)
    print(f"Optical Challenge ID:    {challenge1.challenge_id[:8]}... ({len(challenge1.probes)} probes generated)")

    legit_responses = simulator.simulate_legitimate_response(challenge1, tracking_locked)
    phys_res1 = validator.validate(challenge1, legit_responses, tracking_locked)
    print(f"Physical Validation:     {phys_res1.reason} (Avg Error: {phys_res1.position_error:.4f} rad)")

    eval1 = trust_engine.evaluate("T1", "T2", tracking_locked, auth_valid, physical_validation_result=phys_res1, logger=logger)
    gate1 = TransmissionAuthorizationGate.can_transmit(eval1, logger=logger)

    print(f"\n   --> TRUST        = {eval1.security_state.value}")
    print(f"   --> TRANSMISSION = {'ALLOWED' if gate1.allowed else 'BLOCKED'}\n")

    # =========================================================================
    # SCENARIO 2: FAKE BEACON (Unauthenticated Target)
    # =========================================================================
    print("--------------------------------------------------")
    print("SCENARIO 2: Fake Beacon")
    print("--------------------------------------------------")
    print(f"Member 2 Tracking State: {tracking_locked.tracking_state}")
    fake_auth_valid = False
    print("Mutual Authentication:   FAILED (Untrusted beacon key)")

    eval2 = trust_engine.evaluate("T1", "T2", tracking_locked, fake_auth_valid, logger=logger)
    gate2 = TransmissionAuthorizationGate.can_transmit(eval2, logger=logger)

    print(f"\n   --> TRUST        = {eval2.security_state.value}")
    print(f"   --> TRANSMISSION = {'ALLOWED' if gate2.allowed else 'BLOCKED'}\n")

    # =========================================================================
    # SCENARIO 3: AUTHENTICATED BUT PHYSICALLY INCONSISTENT (ANOMALY)
    # =========================================================================
    print("--------------------------------------------------")
    print("SCENARIO 3: Authenticated Physical Anomaly")
    print("--------------------------------------------------")
    print(f"Member 2 Tracking State: {tracking_locked.tracking_state}")
    print(f"Mutual Authentication:   {'VALID' if auth_valid else 'INVALID'}")

    challenge3 = probe_gen.generate_challenge(auth_result["initiator_session"].session_id, 1, tracking_locked)
    inconsistent_responses = simulator.simulate_inconsistent_response(challenge3, tracking_locked)
    phys_res3 = validator.validate(challenge3, inconsistent_responses, tracking_locked)
    print(f"Physical Validation:     FAILED ({phys_res3.reason})")

    eval3 = trust_engine.evaluate("T1", "T2", tracking_locked, auth_valid, physical_validation_result=phys_res3, logger=logger)
    gate3 = TransmissionAuthorizationGate.can_transmit(eval3, logger=logger)

    print(f"\n   --> TRUST        = {eval3.security_state.value}")
    print(f"   --> TRANSMISSION = {'ALLOWED' if gate3.allowed else 'BLOCKED'}\n")

    print("==================================================")
    print("PHASE 3 DEMONSTRATION COMPLETE - ALL CHECKS PASSED.")
    print("==================================================")


if __name__ == "__main__":
    run_demo()
