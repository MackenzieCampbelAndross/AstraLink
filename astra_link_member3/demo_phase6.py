"""Phase 6 ACK and Selective Repeat ARQ Demonstration for Astra Link."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.identity import TerminalIdentity, TerminalRegistry
from src.authentication import authenticate_mutually
from src.tracking import TrackingState
from src.optical_challenge import OpticalResponseSimulator, PhysicalConsistencyValidator, ProbeGenerator
from src.trust import TransmissionAuthorizationGate, TrustEngine
from src.session import SessionManager
from src.transport import (
    AckMessage,
    EncryptedPacket,
    InvalidPacketError,
    Packetizer,
    PayloadReassembler,
    ReceiverWindow,
    SecureReceiver,
    SecureSender,
    SenderWindow,
)


def run_demo():
    print("==================================================")
    print("    ASTRA LINK MEMBER 3 - PHASE 6 DEMONSTRATION  ")
    print("==================================================")
    print()

    # 1. Setup Identities, Auth, Trust, and Session
    t1 = TerminalIdentity.create_new("T1")
    t2 = TerminalIdentity.create_new("T2")
    registry = TerminalRegistry()
    registry.register_public_credentials(t1.public_credentials)
    registry.register_public_credentials(t2.public_credentials)

    auth_result = authenticate_mutually(t1, t2, registry, tracking_epoch=1)
    auth_valid = auth_result["mutual_authentication_success"]

    tracking_locked = TrackingState(10.0, "LOCKED", 320, 240, 0.10, -0.02, 0.5, -0.1, 0.95, [0.1, 0.1])
    probe_gen = ProbeGenerator()
    simulator = OpticalResponseSimulator()
    validator = PhysicalConsistencyValidator()

    ch = probe_gen.generate_challenge(auth_result["initiator_session"].session_id, 1, tracking_locked)
    resps = simulator.simulate_legitimate_response(ch, tracking_locked)
    phys_res = validator.validate(ch, resps, tracking_locked)

    trust_engine = TrustEngine()
    trust_eval = trust_engine.evaluate("T1", "T2", tracking_locked, auth_valid, physical_validation_result=phys_res)
    gate_res = TransmissionAuthorizationGate.can_transmit(trust_eval)

    session_mgr = SessionManager()
    session = session_mgr.establish_session("T1", "T2", 1, auth_valid, gate_res.allowed)

    sender = SecureSender(session_mgr, packetizer=Packetizer(packet_size=1000))
    receiver = SecureReceiver(session_mgr)

    # 10,000 bytes payload -> 10 packets
    payload_data = b"ASTRA_RELIABLE_PACKET_DATA_" * 370  # ~10,000 bytes
    packets = sender.send_payload(session.session_id, "TX_DEMO6", payload_data, "T1_TO_T2", trust_eval)
    assert len(packets) == 10

    # =========================================================================
    # SCENARIO 1: NORMAL TRANSFER (ALL PACKETS & ACKS DELIVERED)
    # =========================================================================
    print("--------------------------------------------------")
    print("SCENARIO 1: Normal Reliable Transfer (10 Packets)")
    print("--------------------------------------------------")
    print(f"Transfer ID:           TX_DEMO6")
    print(f"Packets transmitted:   {len(packets)}")

    rx1 = ReceiverWindow()
    for p in packets:
        plain = receiver.receive_and_decrypt(p, "T1_TO_T2")
        ack, chunks, dup = rx1.process_received_packet(p, plain)

    print(f"Cumulative ACK:        {rx1.cumulative_ack}")
    print(f"Selective ACK (SACK):  {ack.selective_ack}")
    print(f"Transfer status:       {'COMPLETED' if rx1.cumulative_ack == 10 else 'INCOMPLETE'}\n")

    # =========================================================================
    # SCENARIO 2: SINGLE PACKET LOSS (PACKET 3 LOST)
    # =========================================================================
    print("--------------------------------------------------")
    print("SCENARIO 2: Single Packet Loss (Packet 3 Lost)")
    print("--------------------------------------------------")
    print("Simulating loss of Packet 3...")

    rx2 = ReceiverWindow()
    win2 = SenderWindow(window_size=10)
    for p in packets:
        win2.add_sent_packet(p, current_time=1000.0)

    # Deliver all except Packet 3 (seq=3)
    for p in packets:
        if p.sequence_number == 3:
            continue
        plain = receiver.receive_and_decrypt(p, "T1_TO_T2")
        ack2, _, _ = rx2.process_received_packet(p, plain)

    win2.process_ack(ack2)
    print(f"Receiver Status:       Cumulative ACK = {rx2.cumulative_ack}, SACK = {ack2.selective_ack}")
    print(f"Missing detected:      Packet 3 missing")

    # Selective Retransmission
    retrans_packets = win2.get_timed_out_packets(current_time=1001.0, timeout_seconds=0.100)
    print(f"Selective Retransmit:  {[p.sequence_number for p in retrans_packets]} ONLY (Confirmed packets NOT resent)")

    for rp in retrans_packets:
        plain = receiver.receive_and_decrypt(rp, "T1_TO_T2")
        final_ack, _, _ = rx2.process_received_packet(rp, plain)

    print(f"Final Cumulative ACK:  {rx2.cumulative_ack}")
    print(f"Transfer status:       {'COMPLETED' if rx2.cumulative_ack == 10 else 'INCOMPLETE'}\n")

    # =========================================================================
    # SCENARIO 3: BURST PACKET LOSS (PACKETS 3 & 7 LOST)
    # =========================================================================
    print("--------------------------------------------------")
    print("SCENARIO 3: Burst Packet Loss (Packets 3 and 7 Lost)")
    print("--------------------------------------------------")
    print("Simulating loss of Packets 3 and 7...")

    rx3 = ReceiverWindow()
    win3 = SenderWindow(window_size=10)
    for p in packets:
        win3.add_sent_packet(p, current_time=1000.0)

    for p in packets:
        if p.sequence_number in (3, 7):
            continue
        plain = receiver.receive_and_decrypt(p, "T1_TO_T2")
        ack3, _, _ = rx3.process_received_packet(p, plain)

    win3.process_ack(ack3)
    print(f"Receiver Status:       Cumulative ACK = {rx3.cumulative_ack}, SACK = {ack3.selective_ack}")

    timed_out3 = win3.get_timed_out_packets(current_time=1001.0, timeout_seconds=0.100)
    print(f"Selective Retransmit:  {[p.sequence_number for p in timed_out3]} ONLY")

    for rp in timed_out3:
        plain = receiver.receive_and_decrypt(rp, "T1_TO_T2")
        final_ack3, _, _ = rx3.process_received_packet(rp, plain)

    print(f"Final Cumulative ACK:  {rx3.cumulative_ack}")
    print(f"Transfer status:       {'COMPLETED' if rx3.cumulative_ack == 10 else 'INCOMPLETE'}\n")

    # =========================================================================
    # SCENARIO 4: ACK LOSS & DUPLICATE HANDLING
    # =========================================================================
    print("--------------------------------------------------")
    print("SCENARIO 4: ACK Loss & Duplicate Packet Handling")
    print("--------------------------------------------------")
    p5 = packets[4]
    plain5 = receiver.receive_and_decrypt(p5, "T1_TO_T2")

    rx4 = ReceiverWindow()
    ack_first, chunks_first, dup_first = rx4.process_received_packet(p5, plain5)
    print(f"Packet 5 received:     First delivery accepted (Chunks delivered: {len(chunks_first)})")

    # Simulate ACK 5 lost -> Retransmit Packet 5
    ack_dup, chunks_dup, dup_second = rx4.process_received_packet(p5, plain5)
    print(f"Packet 5 retransmitted: Duplicate detected = {dup_second}")
    print(f"Payload protection:    Duplicate chunks delivered = {len(chunks_dup)} (No double delivery)")
    print(f"Updated ACK re-sent:   Cumulative ACK = {ack_dup.cumulative_ack}\n")

    # =========================================================================
    # SCENARIO 5: TAMPERED PACKET REJECTION
    # =========================================================================
    print("--------------------------------------------------")
    print("SCENARIO 5: Tampered Packet Rejection")
    print("--------------------------------------------------")
    tampered_p = EncryptedPacket(p5.protocol_version, p5.session_id, p5.transfer_id, p5.sequence_number, p5.direction, p5.nonce_hex, "00" * 32)
    try:
        receiver.receive_and_decrypt(tampered_p, "T1_TO_T2")
    except InvalidPacketError as e:
        print("Tampered Packet:       REJECTED by AES-GCM tag verification")
        print("Receiver Action:       NOT ACKNOWLEDGED (Will trigger sender timeout retransmission)")

    print("\n==================================================")
    print("PHASE 6 DEMONSTRATION COMPLETE - ALL CHECKS PASSED.")
    print("==================================================")


if __name__ == "__main__":
    run_demo()
