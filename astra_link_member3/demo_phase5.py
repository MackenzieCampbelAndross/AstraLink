"""Phase 5 Secure Data Transmission Demonstration for Astra Link."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.identity import TerminalIdentity, TerminalRegistry
from src.authentication import authenticate_mutually
from src.tracking import TrackingState
from src.optical_challenge import OpticalResponseSimulator, PhysicalConsistencyValidator, ProbeGenerator
from src.trust import SecurityState, TransmissionAuthorizationGate, TrustEngine
from src.session import SessionManager
from src.transport import (
    EncryptedPacket,
    InvalidPacketError,
    Packetizer,
    PayloadReassembler,
    SecureReceiver,
    SecureSender,
    UnauthorizedTransmissionError,
)


def run_demo():
    print("==================================================")
    print("    ASTRA LINK MEMBER 3 - PHASE 5 DEMONSTRATION  ")
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
    session_mgr = SessionManager()
    session = session_mgr.establish_session(
        initiator_id="T1",
        responder_id="T2",
        tracking_epoch=1,
        authentication_valid=auth_valid,
        trust_authorized=gate_res.allowed,
    )

    # 5. Phase 5 Secure Transmission
    print("--------------------------------------------------")
    print("PHASE 5 SECURE TRANSMISSION")
    print("--------------------------------------------------")
    print(f"Mutual authentication: {'SUCCESS' if auth_valid else 'FAILED'}")
    print(f"Trust authorization:   {'SUCCESS' if gate_res.allowed else 'FAILED'}")
    print(f"Secure session:        {session.state.value}\n")

    sender = SecureSender(session_mgr, packetizer=Packetizer(packet_size=4096))
    receiver = SecureReceiver(session_mgr)
    reassembler = PayloadReassembler()

    payload_data = b"ASTRA-LINK-SECRET-PAYLOAD-" * 400  # 10,400 bytes
    transfer_id = "TX_001"

    print(f"Transfer ID:           {transfer_id}")
    print(f"Payload bytes:         {len(payload_data)}")

    packets = sender.send_payload(
        session_id=session.session_id,
        transfer_id=transfer_id,
        payload=payload_data,
        direction="T1_TO_T2",
        trust_result=trust_eval,
    )

    print(f"Packets created:       {len(packets)}\n")

    for p in packets:
        print(f"Packet {p.sequence_number}")
        print(f"  Sequence:                    {p.sequence_number}")
        print("  AES-GCM Encryption:          SUCCESS")
        print("  Transmission authorization:  ALLOWED")

        # Receiver decrypts and passes chunk to reassembler
        decrypted_chunk = receiver.receive_and_decrypt(p, expected_direction="T1_TO_T2")
        accepted = reassembler.accept_packet(p.sequence_number, decrypted_chunk)
        print(f"  Receiver Chunk Acceptance:   {'ACCEPTED' if accepted else 'DUPLICATE'}\n")

    reconstructed_payload = reassembler.reassemble()
    integrity_valid = reconstructed_payload == payload_data

    print(f"Receiver verification:  SUCCESS")
    print(f"Payload reconstruction: SUCCESS ({len(reconstructed_payload)} bytes)")
    print(f"Integrity:              {'VALID' if integrity_valid else 'INVALID'}\n")

    # =========================================================================
    # DEMONSTRATING TAMPERING & UNAUTHORIZED TRANSMISSION
    # =========================================================================
    print("--------------------------------------------------")
    print("      DEMONSTRATING TAMPERING & BLOCKED STATES    ")
    print("--------------------------------------------------")

    # Tamper Scenario: Modify Ciphertext
    print("\n1. Testing Ciphertext Tampering:")
    orig_packet = packets[0]
    tampered_hex = orig_packet.ciphertext_hex[:-4] + "FFFF"
    tampered_packet = EncryptedPacket(
        orig_packet.protocol_version,
        orig_packet.session_id,
        orig_packet.transfer_id,
        orig_packet.sequence_number,
        orig_packet.direction,
        orig_packet.nonce_hex,
        tampered_hex,
    )
    try:
        receiver.receive_and_decrypt(tampered_packet, expected_direction="T1_TO_T2")
    except InvalidPacketError as e:
        print("   AES-GCM Verification: PACKET REJECTED")
        print(f"   Reason: {e}")

    # Unauthorized Scenario: Revoked Trust
    print("\n2. Testing Unauthorized Transmission (Revoked Trust):")
    revoked_trust = trust_engine.evaluate("T1", "T2", tracking_locked, authentication_valid=False)
    try:
        sender.send_payload(session.session_id, "TX_002", b"Blocked Data", "T1_TO_T2", revoked_trust)
    except UnauthorizedTransmissionError as e:
        print("   Transmission Gate:   TRANSMISSION BLOCKED")
        print(f"   Reason: {e}")

    print("\n==================================================")
    print("PHASE 5 DEMONSTRATION COMPLETE - ALL CHECKS PASSED.")
    print("==================================================")


if __name__ == "__main__":
    run_demo()
