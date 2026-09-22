"""Unit tests for Phase 6: ACK and Selective Repeat ARQ."""

import time
import pytest

from src.identity import TerminalIdentity, TerminalRegistry
from src.authentication import authenticate_mutually
from src.tracking import TrackingState
from src.trust import SecurityState, TransmissionAuthorizationGate, TrustEngine, TrustEvaluationResult
from src.session import SessionManager
from src.transport import (
    AckMessage,
    EncryptedPacket,
    InvalidPacketError,
    MaxRetriesExceededError,
    PacketCipher,
    Packetizer,
    PayloadReassembler,
    ReceiverWindow,
    SecureReceiver,
    SecureSender,
    SenderWindow,
    TransportMetrics,
    generate_gcm_nonce,
)


@pytest.fixture
def session_setup():
    t1 = TerminalIdentity.create_new("T1")
    t2 = TerminalIdentity.create_new("T2")
    reg = TerminalRegistry()
    reg.register_public_credentials(t1.public_credentials)
    reg.register_public_credentials(t2.public_credentials)

    auth_res = authenticate_mutually(t1, t2, reg, tracking_epoch=1)
    auth_valid = auth_res["mutual_authentication_success"]

    tracking = TrackingState(10.0, "LOCKED", 320, 240, 0.10, -0.02, 0.5, -0.1, 0.95, [0.1, 0.1])
    trust_engine = TrustEngine()
    trust_res = trust_engine.evaluate("T1", "T2", tracking, auth_valid)

    mgr = SessionManager()
    session = mgr.establish_session("T1", "T2", 1, auth_valid, trust_res.trust_authorized)

    return {
        "manager": mgr,
        "session": session,
        "trust_res": trust_res,
        "sender": SecureSender(mgr),
        "receiver": SecureReceiver(mgr),
    }


# 1. Single packet ACK
def test_single_packet_ack():
    rx = ReceiverWindow()
    packet = EncryptedPacket("1.0", "s1", "tx1", 1, "T1_TO_T2", "11" * 12, "22" * 32)
    ack, chunks, dup = rx.process_received_packet(packet, b"Chunk1")

    assert ack.cumulative_ack == 1
    assert ack.selective_ack == []
    assert len(chunks) == 1
    assert dup is False


# 2. Cumulative ACK
def test_cumulative_ack():
    rx = ReceiverWindow()
    p1 = EncryptedPacket("1.0", "s1", "tx1", 1, "T1_TO_T2", "11" * 12, "22" * 32)
    p2 = EncryptedPacket("1.0", "s1", "tx1", 2, "T1_TO_T2", "11" * 12, "22" * 32)
    p3 = EncryptedPacket("1.0", "s1", "tx1", 3, "T1_TO_T2", "11" * 12, "22" * 32)

    rx.process_received_packet(p1, b"C1")
    rx.process_received_packet(p2, b"C2")
    ack, chunks, dup = rx.process_received_packet(p3, b"C3")

    assert ack.cumulative_ack == 3
    assert ack.selective_ack == []


# 3. Selective ACK
def test_selective_ack():
    rx = ReceiverWindow()
    p1 = EncryptedPacket("1.0", "s1", "tx1", 1, "T1_TO_T2", "11" * 12, "22" * 32)
    p2 = EncryptedPacket("1.0", "s1", "tx1", 2, "T1_TO_T2", "11" * 12, "22" * 32)
    p4 = EncryptedPacket("1.0", "s1", "tx1", 4, "T1_TO_T2", "11" * 12, "22" * 32)
    p5 = EncryptedPacket("1.0", "s1", "tx1", 5, "T1_TO_T2", "11" * 12, "22" * 32)

    rx.process_received_packet(p1, b"C1")
    rx.process_received_packet(p2, b"C2")
    rx.process_received_packet(p4, b"C4")
    ack, chunks, dup = rx.process_received_packet(p5, b"C5")

    assert ack.cumulative_ack == 2
    assert ack.selective_ack == [4, 5]


# 4. Missing packet detection
def test_missing_packet_detection():
    rx = ReceiverWindow()
    p1 = EncryptedPacket("1.0", "s1", "tx1", 1, "T1_TO_T2", "11" * 12, "22" * 32)
    p3 = EncryptedPacket("1.0", "s1", "tx1", 3, "T1_TO_T2", "11" * 12, "22" * 32)

    rx.process_received_packet(p1, b"C1")
    ack, chunks, dup = rx.process_received_packet(p3, b"C3")

    assert ack.cumulative_ack == 1
    assert ack.selective_ack == [3]  # Packet 2 missing!


# 5. Selective retransmission
def test_selective_retransmission():
    win = SenderWindow(window_size=10)
    p1 = EncryptedPacket("1.0", "s1", "tx1", 1, "T1_TO_T2", "11" * 12, "22" * 32)
    p2 = EncryptedPacket("1.0", "s1", "tx1", 2, "T1_TO_T2", "11" * 12, "22" * 32)
    p3 = EncryptedPacket("1.0", "s1", "tx1", 3, "T1_TO_T2", "11" * 12, "22" * 32)

    now = 1000.0
    win.add_sent_packet(p1, current_time=now)
    win.add_sent_packet(p2, current_time=now)
    win.add_sent_packet(p3, current_time=now)

    # ACK for 1 & 3 (2 missing)
    ack = AckMessage("1.0", "s1", "tx1", "T1_TO_T2", cumulative_ack=1, selective_ack=[3])
    win.process_ack(ack)

    # Check timeout for packet 2
    timed_out = win.get_timed_out_packets(current_time=now + 1.0, timeout_seconds=0.100)
    assert len(timed_out) == 1
    assert timed_out[0].sequence_number == 2  # Only packet 2 retransmitted!


# 6. Transmission window constraint
def test_transmission_window_constraint():
    win = SenderWindow(window_size=2)
    p1 = EncryptedPacket("1.0", "s1", "tx1", 1, "T1_TO_T2", "11" * 12, "22" * 32)
    p2 = EncryptedPacket("1.0", "s1", "tx1", 2, "T1_TO_T2", "11" * 12, "22" * 32)

    assert win.can_send_next() is True
    win.add_sent_packet(p1)
    assert win.can_send_next() is True
    win.add_sent_packet(p2)
    assert win.can_send_next() is False  # Window full!


# 7. Window advancement upon ACK
def test_window_advancement():
    win = SenderWindow(window_size=2)
    p1 = EncryptedPacket("1.0", "s1", "tx1", 1, "T1_TO_T2", "11" * 12, "22" * 32)
    p2 = EncryptedPacket("1.0", "s1", "tx1", 2, "T1_TO_T2", "11" * 12, "22" * 32)

    win.add_sent_packet(p1)
    win.add_sent_packet(p2)
    assert win.can_send_next() is False

    ack = AckMessage("1.0", "s1", "tx1", "T1_TO_T2", cumulative_ack=1, selective_ack=[])
    win.process_ack(ack)

    assert win.base_sequence == 2
    assert win.can_send_next() is True  # Window advanced!


# 8. Out of order packet buffering
def test_out_of_order_packet_buffering():
    rx = ReceiverWindow()
    p1 = EncryptedPacket("1.0", "s1", "tx1", 1, "T1_TO_T2", "11" * 12, "22" * 32)
    p3 = EncryptedPacket("1.0", "s1", "tx1", 3, "T1_TO_T2", "11" * 12, "22" * 32)

    rx.process_received_packet(p1, b"C1")
    ack1, chunks1, _ = rx.process_received_packet(p3, b"C3")
    assert ack1.cumulative_ack == 1
    assert chunks1 == []  # C3 buffered!

    p2 = EncryptedPacket("1.0", "s1", "tx1", 2, "T1_TO_T2", "11" * 12, "22" * 32)
    ack2, chunks2, _ = rx.process_received_packet(p2, b"C2")

    assert ack2.cumulative_ack == 3
    assert chunks2 == [(2, b"C2"), (3, b"C3")]  # C2 and C3 delivered contiguously!


# 9. Duplicate packet handling
def test_duplicate_packet_handling():
    rx = ReceiverWindow()
    p1 = EncryptedPacket("1.0", "s1", "tx1", 1, "T1_TO_T2", "11" * 12, "22" * 32)

    ack1, chunks1, dup1 = rx.process_received_packet(p1, b"C1")
    assert dup1 is False
    assert len(chunks1) == 1

    ack2, chunks2, dup2 = rx.process_received_packet(p1, b"C1")
    assert dup2 is True
    assert chunks2 == []  # No double delivery!
    assert ack2.cumulative_ack == 1


# 10. Duplicate ACK handling
def test_duplicate_ack_handling():
    win = SenderWindow(window_size=5)
    p1 = EncryptedPacket("1.0", "s1", "tx1", 1, "T1_TO_T2", "11" * 12, "22" * 32)
    win.add_sent_packet(p1)

    ack = AckMessage("1.0", "s1", "tx1", "T1_TO_T2", cumulative_ack=1, selective_ack=[])
    win.process_ack(ack)
    b1 = win.base_sequence

    # Process exact duplicate ACK
    win.process_ack(ack)
    assert win.base_sequence == b1  # No corruption!


# 11. Lost packet recovery
def test_lost_packet_recovery():
    rx = ReceiverWindow()
    p1 = EncryptedPacket("1.0", "s1", "tx1", 1, "T1_TO_T2", "11" * 12, "22" * 32)
    p3 = EncryptedPacket("1.0", "s1", "tx1", 3, "T1_TO_T2", "11" * 12, "22" * 32)

    rx.process_received_packet(p1, b"C1")
    rx.process_received_packet(p3, b"C3")

    p2 = EncryptedPacket("1.0", "s1", "tx1", 2, "T1_TO_T2", "11" * 12, "22" * 32)
    ack, chunks, _ = rx.process_received_packet(p2, b"C2")

    assert ack.cumulative_ack == 3
    assert [c[1] for c in chunks] == [b"C2", b"C3"]


# 12. Multiple lost packets (burst loss)
def test_multiple_lost_packets_burst_loss():
    win = SenderWindow(window_size=10)
    for i in range(1, 10):
        p = EncryptedPacket("1.0", "s1", "tx1", i, "T1_TO_T2", "11" * 12, "22" * 32)
        win.add_sent_packet(p, current_time=1000.0)

    # Packets 3 and 7 lost (SACK reports 1, 2, 4, 5, 6, 8, 9)
    ack = AckMessage("1.0", "s1", "tx1", "T1_TO_T2", cumulative_ack=2, selective_ack=[4, 5, 6, 8, 9])
    win.process_ack(ack)

    timed_out = win.get_timed_out_packets(current_time=1001.0, timeout_seconds=0.100)
    retrans_seqs = [p.sequence_number for p in timed_out]
    assert retrans_seqs == [3, 7]  # Only 3 and 7 retransmitted!


# 13. ACK loss recovery
def test_ack_loss_recovery():
    rx = ReceiverWindow()
    p1 = EncryptedPacket("1.0", "s1", "tx1", 1, "T1_TO_T2", "11" * 12, "22" * 32)
    rx.process_received_packet(p1, b"C1")

    # Re-receive p1 because ACK was lost
    ack2, chunks2, dup2 = rx.process_received_packet(p1, b"C1")
    assert dup2 is True
    assert chunks2 == []
    assert ack2.cumulative_ack == 1


# 14. Delayed packet arrival
def test_delayed_packet_arrival():
    rx = ReceiverWindow()
    p1 = EncryptedPacket("1.0", "s1", "tx1", 1, "T1_TO_T2", "11" * 12, "22" * 32)
    p2 = EncryptedPacket("1.0", "s1", "tx1", 2, "T1_TO_T2", "11" * 12, "22" * 32)
    p4 = EncryptedPacket("1.0", "s1", "tx1", 4, "T1_TO_T2", "11" * 12, "22" * 32)
    p5 = EncryptedPacket("1.0", "s1", "tx1", 5, "T1_TO_T2", "11" * 12, "22" * 32)

    rx.process_received_packet(p1, b"C1")
    rx.process_received_packet(p2, b"C2")
    rx.process_received_packet(p4, b"C4")
    rx.process_received_packet(p5, b"C5")

    p3 = EncryptedPacket("1.0", "s1", "tx1", 3, "T1_TO_T2", "11" * 12, "22" * 32)
    ack, chunks, _ = rx.process_received_packet(p3, b"C3")

    assert ack.cumulative_ack == 5
    assert [c[1] for c in chunks] == [b"C3", b"C4", b"C5"]


# 15. Invalid packet not acknowledged
def test_invalid_packet_not_acknowledged(session_setup):
    receiver = session_setup["receiver"]
    corrupt_packet = EncryptedPacket("1.0", "s1", "tx1", 1, "T1_TO_T2", "00" * 12, "00" * 32)

    with pytest.raises(InvalidPacketError):
        receiver.receive_and_decrypt(corrupt_packet, expected_direction="T1_TO_T2")

    # Receiver window remained at 0
    assert receiver.receiver_window.cumulative_ack == 0


# 16. Invalid ACK rejected
def test_invalid_ack_rejected():
    with pytest.raises(ValueError):
        AckMessage.from_bytes(b"INVALID_JSON_DATA")


# 17. Wrong transfer ACK rejected
def test_wrong_transfer_ack_rejected(session_setup):
    receiver = session_setup["receiver"]
    session = session_setup["session"]

    ack_control = EncryptedPacket("1.0", session.session_id, "TX_999", 0, "T1_TO_T2", "11" * 12, "22" * 32)

    with pytest.raises(InvalidPacketError):
        receiver.decrypt_ack_control_packet(ack_control, expected_direction="T1_TO_T2")


# 18. Wrong session ACK rejected
def test_wrong_session_ack_rejected(session_setup):
    receiver = session_setup["receiver"]

    ack_control = EncryptedPacket("1.0", "wrong_session", "TX_001", 0, "T1_TO_T2", "11" * 12, "22" * 32)

    with pytest.raises(InvalidPacketError):
        receiver.decrypt_ack_control_packet(ack_control, expected_direction="T1_TO_T2")


# 19. Retry timeout
def test_retry_timeout():
    win = SenderWindow(window_size=5)
    p1 = EncryptedPacket("1.0", "s1", "tx1", 1, "T1_TO_T2", "11" * 12, "22" * 32)
    win.add_sent_packet(p1, current_time=1000.0)

    # Check timeout before threshold
    assert len(win.get_timed_out_packets(current_time=1000.05, timeout_seconds=0.100)) == 0

    # Check timeout after threshold
    timed_out = win.get_timed_out_packets(current_time=1000.20, timeout_seconds=0.100)
    assert len(timed_out) == 1


# 20. Maximum retry failure
def test_maximum_retry_failure():
    win = SenderWindow(window_size=5, max_retries=2)
    p1 = EncryptedPacket("1.0", "s1", "tx1", 1, "T1_TO_T2", "11" * 12, "22" * 32)
    win.add_sent_packet(p1, current_time=1000.0)

    win.get_timed_out_packets(current_time=1001.0, timeout_seconds=0.100)  # Retry 1
    win.get_timed_out_packets(current_time=1002.0, timeout_seconds=0.100)  # Retry 2

    with pytest.raises(MaxRetriesExceededError):
        win.get_timed_out_packets(current_time=1003.0, timeout_seconds=0.100)  # Retry 3 exceeds max 2!


# 21. Complete transfer
def test_complete_transfer_detection():
    rx = ReceiverWindow()
    for i in range(1, 6):
        p = EncryptedPacket("1.0", "s1", "tx1", i, "T1_TO_T2", "11" * 12, "22" * 32)
        rx.process_received_packet(p, f"C{i}".encode("utf-8"))

    assert rx.cumulative_ack == 5
    assert len(rx.received_out_of_order) == 0


# 22. Incomplete transfer does not report completion
def test_incomplete_transfer_state():
    rx = ReceiverWindow()
    p1 = EncryptedPacket("1.0", "s1", "tx1", 1, "T1_TO_T2", "11" * 12, "22" * 32)
    p3 = EncryptedPacket("1.0", "s1", "tx1", 3, "T1_TO_T2", "11" * 12, "22" * 32)

    rx.process_received_packet(p1, b"C1")
    rx.process_received_packet(p3, b"C3")

    assert rx.cumulative_ack == 1  # 2 missing, incomplete!


# 23. Large multi packet transfer
def test_large_multi_packet_transfer(session_setup):
    sender = session_setup["sender"]
    receiver = session_setup["receiver"]
    session = session_setup["session"]
    trust_res = session_setup["trust_res"]

    data = b"LARGE_PAYLOAD_DATA_" * 1000  # 19,000 bytes
    packets = sender.send_payload(session.session_id, "TX_LARGE", data, "T1_TO_T2", trust_res)
    assert len(packets) == 5

    reassembler = PayloadReassembler()
    for p in packets:
        plain = receiver.receive_and_decrypt(p, "T1_TO_T2")
        reassembler.accept_packet(p.sequence_number, plain)

    assert reassembler.reassemble() == data


# 24. Receiver reassembly
def test_receiver_reassembly():
    reassembler = PayloadReassembler()
    reassembler.accept_packet(1, b"A")
    reassembler.accept_packet(2, b"B")
    reassembler.accept_packet(3, b"C")
    assert reassembler.reassemble() == b"ABC"


# 25. No duplicate application delivery
def test_no_duplicate_application_delivery():
    reassembler = PayloadReassembler()
    reassembler.accept_packet(1, b"A")
    reassembler.accept_packet(1, b"A")  # Duplicate!
    assert reassembler.reassemble() == b"A"


# 26. Selective retransmission does not resend confirmed packets
def test_selective_retrans_skips_confirmed():
    win = SenderWindow(window_size=10)
    for i in range(1, 6):
        p = EncryptedPacket("1.0", "s1", "tx1", i, "T1_TO_T2", "11" * 12, "22" * 32)
        win.add_sent_packet(p, current_time=1000.0)

    # ACK 1, 2, 4, 5 (3 missing)
    ack = AckMessage("1.0", "s1", "tx1", "T1_TO_T2", cumulative_ack=2, selective_ack=[4, 5])
    win.process_ack(ack)

    timed_out = win.get_timed_out_packets(current_time=1001.0, timeout_seconds=0.100)
    assert len(timed_out) == 1
    assert timed_out[0].sequence_number == 3


# 27. Window cannot exceed configured size
def test_window_cannot_exceed_configured_size():
    win = SenderWindow(window_size=3)
    for i in range(1, 4):
        p = EncryptedPacket("1.0", "s1", "tx1", i, "T1_TO_T2", "11" * 12, "22" * 32)
        win.add_sent_packet(p)

    assert win.can_send_next() is False


# 28. Phase 5 encryption remains functional
def test_phase5_encryption_functional(session_setup):
    sender = session_setup["sender"]
    receiver = session_setup["receiver"]
    session = session_setup["session"]
    trust_res = session_setup["trust_res"]

    packets = sender.send_payload(session.session_id, "TX_001", b"Secret", "T1_TO_T2", trust_res)
    assert receiver.receive_and_decrypt(packets[0], "T1_TO_T2") == b"Secret"


# 29. Phase 5 authorization gate remains functional
def test_phase5_authorization_gate_functional(session_setup):
    sender = session_setup["sender"]
    session = session_setup["session"]

    unauth_trust = TrustEvaluationResult(
        security_state=SecurityState.BLOCKED,
        trust_authorized=False,
        tracking_valid=False,
        motion_consistent=False,
        authentication_valid=False,
        freshness_valid=False,
        physical_valid=False,
        reason="BLOCKED",
        details={},
    )

    with pytest.raises(Exception):
        sender.send_payload(session.session_id, "TX_001", b"Secret", "T1_TO_T2", unauth_trust)


# 30. Phase 4 rekey compatibility
def test_phase4_rekey_compatibility(session_setup):
    sender = session_setup["sender"]
    receiver = session_setup["receiver"]
    session = session_setup["session"]
    trust_res = session_setup["trust_res"]
    mgr = session_setup["manager"]

    p1 = sender.send_payload(session.session_id, "TX_001", b"Data 1", "T1_TO_T2", trust_res)[0]
    mgr.rekey_session(session.session_id)
    p2 = sender.send_payload(session.session_id, "TX_001", b"Data 2", "T1_TO_T2", trust_res)[0]

    assert receiver.receive_and_decrypt(p2, "T1_TO_T2") == b"Data 2"
