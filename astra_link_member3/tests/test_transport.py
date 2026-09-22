"""Unit tests for Phase 5: Secure Data Transmission."""

import pytest

from src.identity import TerminalIdentity, TerminalRegistry
from src.authentication import authenticate_mutually
from src.tracking import TrackingState
from src.trust import SecurityState, TransmissionAuthorizationGate, TrustEngine, TrustEvaluationResult
from src.session import SessionManager, SessionState
from src.transport import (
    EncryptedPacket,
    InvalidPacketError,
    PacketCipher,
    Packetizer,
    PayloadReassembler,
    SecureReceiver,
    SecureSender,
    UnauthorizedTransmissionError,
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


# 1. Payload encryption succeeds for authorized session
def test_payload_encryption_succeeds(session_setup):
    sender = session_setup["sender"]
    session = session_setup["session"]
    trust_res = session_setup["trust_res"]

    packets = sender.send_payload(
        session_id=session.session_id,
        transfer_id="TX_001",
        payload=b"Astra Link secret data",
        direction="T1_TO_T2",
        trust_result=trust_res,
    )

    assert len(packets) == 1
    assert packets[0].sequence_number == 1
    assert packets[0].transfer_id == "TX_001"
    assert packets[0].direction == "T1_TO_T2"


# 2. Valid encrypted packet decrypts successfully
def test_valid_encrypted_packet_decrypts(session_setup):
    sender = session_setup["sender"]
    receiver = session_setup["receiver"]
    session = session_setup["session"]
    trust_res = session_setup["trust_res"]
    payload = b"Top secret optical transmission"

    packets = sender.send_payload(session.session_id, "TX_001", payload, "T1_TO_T2", trust_res)
    decrypted = receiver.receive_and_decrypt(packets[0], expected_direction="T1_TO_T2")

    assert decrypted == payload


# 3. Wrong key cannot decrypt packet
def test_wrong_key_cannot_decrypt():
    wrong_key = b"W" * 32
    packet = PacketCipher.encrypt(b"K" * 32, b"Data", "1.0", "s1", "tx1", 1, "T1_TO_T2")

    with pytest.raises(InvalidPacketError):
        PacketCipher.decrypt(wrong_key, packet)


# 4. Modified ciphertext is rejected
def test_modified_ciphertext_rejected(session_setup):
    sender = session_setup["sender"]
    receiver = session_setup["receiver"]
    session = session_setup["session"]
    trust_res = session_setup["trust_res"]

    packets = sender.send_payload(session.session_id, "TX_001", b"Data", "T1_TO_T2", trust_res)
    orig = packets[0]

    # Modify ciphertext hex
    tampered_hex = orig.ciphertext_hex[:-4] + "0000"
    tampered_packet = EncryptedPacket(
        orig.protocol_version, orig.session_id, orig.transfer_id, orig.sequence_number, orig.direction, orig.nonce_hex, tampered_hex
    )

    with pytest.raises(InvalidPacketError):
        receiver.receive_and_decrypt(tampered_packet, expected_direction="T1_TO_T2")


# 5. Modified nonce is rejected
def test_modified_nonce_rejected(session_setup):
    sender = session_setup["sender"]
    receiver = session_setup["receiver"]
    session = session_setup["session"]
    trust_res = session_setup["trust_res"]

    packets = sender.send_payload(session.session_id, "TX_001", b"Data", "T1_TO_T2", trust_res)
    orig = packets[0]

    tampered_nonce = "00" * 12
    tampered_packet = EncryptedPacket(
        orig.protocol_version, orig.session_id, orig.transfer_id, orig.sequence_number, orig.direction, tampered_nonce, orig.ciphertext_hex
    )

    with pytest.raises(InvalidPacketError):
        receiver.receive_and_decrypt(tampered_packet, expected_direction="T1_TO_T2")


# 6. Modified session ID is rejected
def test_modified_session_id_rejected(session_setup):
    sender = session_setup["sender"]
    receiver = session_setup["receiver"]
    session = session_setup["session"]
    trust_res = session_setup["trust_res"]

    packets = sender.send_payload(session.session_id, "TX_001", b"Data", "T1_TO_T2", trust_res)
    orig = packets[0]

    tampered_packet = EncryptedPacket(
        orig.protocol_version, "wrong_session", orig.transfer_id, orig.sequence_number, orig.direction, orig.nonce_hex, orig.ciphertext_hex
    )

    with pytest.raises(InvalidPacketError):
        receiver.receive_and_decrypt(tampered_packet, expected_direction="T1_TO_T2")


# 7. Modified transfer ID is rejected
def test_modified_transfer_id_rejected(session_setup):
    sender = session_setup["sender"]
    receiver = session_setup["receiver"]
    session = session_setup["session"]
    trust_res = session_setup["trust_res"]

    packets = sender.send_payload(session.session_id, "TX_001", b"Data", "T1_TO_T2", trust_res)
    orig = packets[0]

    tampered_packet = EncryptedPacket(
        orig.protocol_version, orig.session_id, "TX_999", orig.sequence_number, orig.direction, orig.nonce_hex, orig.ciphertext_hex
    )

    with pytest.raises(InvalidPacketError):
        receiver.receive_and_decrypt(tampered_packet, expected_direction="T1_TO_T2")


# 8. Modified sequence number is rejected
def test_modified_sequence_number_rejected(session_setup):
    sender = session_setup["sender"]
    receiver = session_setup["receiver"]
    session = session_setup["session"]
    trust_res = session_setup["trust_res"]

    packets = sender.send_payload(session.session_id, "TX_001", b"Data", "T1_TO_T2", trust_res)
    orig = packets[0]

    tampered_packet = EncryptedPacket(
        orig.protocol_version, orig.session_id, orig.transfer_id, 999, orig.direction, orig.nonce_hex, orig.ciphertext_hex
    )

    with pytest.raises(InvalidPacketError):
        receiver.receive_and_decrypt(tampered_packet, expected_direction="T1_TO_T2")


# 9. Modified direction is rejected
def test_modified_direction_rejected(session_setup):
    sender = session_setup["sender"]
    receiver = session_setup["receiver"]
    session = session_setup["session"]
    trust_res = session_setup["trust_res"]

    packets = sender.send_payload(session.session_id, "TX_001", b"Data", "T1_TO_T2", trust_res)
    orig = packets[0]

    tampered_packet = EncryptedPacket(
        orig.protocol_version, orig.session_id, orig.transfer_id, orig.sequence_number, "T2_TO_T1", orig.nonce_hex, orig.ciphertext_hex
    )

    with pytest.raises(InvalidPacketError):
        receiver.receive_and_decrypt(tampered_packet, expected_direction="T2_TO_T1")


# 10. Expired session cannot send
def test_expired_session_cannot_send(session_setup):
    sender = session_setup["sender"]
    session = session_setup["session"]
    trust_res = session_setup["trust_res"]
    mgr = session_setup["manager"]

    mgr.expire_session(session.session_id)

    with pytest.raises(UnauthorizedTransmissionError) as exc:
        sender.send_payload(session.session_id, "TX_001", b"Data", "T1_TO_T2", trust_res)
    assert "inactive or expired" in str(exc.value)


# 11. Terminated session cannot send
def test_terminated_session_cannot_send(session_setup):
    sender = session_setup["sender"]
    session = session_setup["session"]
    trust_res = session_setup["trust_res"]
    mgr = session_setup["manager"]

    mgr.terminate_session(session.session_id)

    with pytest.raises(UnauthorizedTransmissionError):
        sender.send_payload(session.session_id, "TX_001", b"Data", "T1_TO_T2", trust_res)


# 12. Unauthenticated state cannot send
def test_unauthenticated_state_cannot_send(session_setup):
    sender = session_setup["sender"]
    session = session_setup["session"]

    unauth_trust = TrustEvaluationResult(
        security_state=SecurityState.UNTRUSTED,
        trust_authorized=False,
        tracking_valid=True,
        motion_consistent=True,
        authentication_valid=False,  # Unauthenticated!
        freshness_valid=True,
        physical_valid=True,
        reason="UNAUTHENTICATED",
        details={},
    )

    with pytest.raises(UnauthorizedTransmissionError):
        sender.send_payload(session.session_id, "TX_001", b"Data", "T1_TO_T2", unauth_trust)


# 13. Unauthorized state cannot send
def test_unauthorized_state_cannot_send(session_setup):
    sender = session_setup["sender"]
    session = session_setup["session"]

    unauth_trust = TrustEvaluationResult(
        security_state=SecurityState.DEGRADED,
        trust_authorized=False,  # Unauthorized!
        tracking_valid=True,
        motion_consistent=False,
        authentication_valid=True,
        freshness_valid=True,
        physical_valid=True,
        reason="MOTION_INCONSISTENT",
        details={},
    )

    with pytest.raises(UnauthorizedTransmissionError):
        sender.send_payload(session.session_id, "TX_001", b"Data", "T1_TO_T2", unauth_trust)


# 14. Session establishment is required
def test_session_establishment_required(session_setup):
    sender = session_setup["sender"]
    trust_res = session_setup["trust_res"]

    with pytest.raises(UnauthorizedTransmissionError):
        sender.send_payload("nonexistent_session", "TX_001", b"Data", "T1_TO_T2", trust_res)


# 15. T1 -> T2 uses correct directional key
def test_t1_to_t2_directional_key_enforced(session_setup):
    sender = session_setup["sender"]
    receiver = session_setup["receiver"]
    session = session_setup["session"]
    trust_res = session_setup["trust_res"]

    packets = sender.send_payload(session.session_id, "TX_001", b"T1 Payload", "T1_TO_T2", trust_res)
    decrypted = receiver.receive_and_decrypt(packets[0], expected_direction="T1_TO_T2")
    assert decrypted == b"T1 Payload"


# 16. T2 -> T1 uses correct directional key
def test_t2_to_t1_directional_key_enforced(session_setup):
    sender = session_setup["sender"]
    receiver = session_setup["receiver"]
    session = session_setup["session"]
    trust_res = session_setup["trust_res"]

    packets = sender.send_payload(session.session_id, "TX_002", b"T2 Payload", "T2_TO_T1", trust_res)
    decrypted = receiver.receive_and_decrypt(packets[0], expected_direction="T2_TO_T1")
    assert decrypted == b"T2 Payload"


# 17. Cross direction packet reuse is rejected
def test_cross_direction_packet_reuse_rejected(session_setup):
    sender = session_setup["sender"]
    receiver = session_setup["receiver"]
    session = session_setup["session"]
    trust_res = session_setup["trust_res"]

    packets = sender.send_payload(session.session_id, "TX_001", b"T1 Payload", "T1_TO_T2", trust_res)
    
    # Receiver expects T2_TO_T1 but packet is T1_TO_T2
    with pytest.raises(InvalidPacketError) as exc:
        receiver.receive_and_decrypt(packets[0], expected_direction="T2_TO_T1")
    assert "Cross-direction packet reuse rejected" in str(exc.value)


# 18. Different packets receive unique nonces
def test_different_packets_receive_unique_nonces(session_setup):
    sender = session_setup["sender"]
    session = session_setup["session"]
    trust_res = session_setup["trust_res"]

    packets = sender.send_payload(session.session_id, "TX_001", b"A" * 10000, "T1_TO_T2", trust_res)
    assert len(packets) > 1

    nonces = [p.nonce_hex for p in packets]
    assert len(nonces) == len(set(nonces))  # All nonces unique


# 19. Sequence numbers are monotonic
def test_sequence_numbers_are_monotonic(session_setup):
    sender = session_setup["sender"]
    session = session_setup["session"]
    trust_res = session_setup["trust_res"]

    packets = sender.send_payload(session.session_id, "TX_001", b"B" * 10000, "T1_TO_T2", trust_res)
    seqs = [p.sequence_number for p in packets]
    assert seqs == [1, 2, 3]


# 20. Different transfer IDs remain distinct
def test_different_transfer_ids_distinct(session_setup):
    sender = session_setup["sender"]
    receiver = session_setup["receiver"]
    session = session_setup["session"]
    trust_res = session_setup["trust_res"]

    p1 = sender.send_payload(session.session_id, "TX_001", b"Trans 1", "T1_TO_T2", trust_res)[0]
    p2 = sender.send_payload(session.session_id, "TX_002", b"Trans 2", "T1_TO_T2", trust_res)[0]

    assert p1.transfer_id != p2.transfer_id
    assert receiver.receive_and_decrypt(p1, "T1_TO_T2") == b"Trans 1"
    assert receiver.receive_and_decrypt(p2, "T1_TO_T2") == b"Trans 2"


# 21. Packetization works for small payloads
def test_packetization_small_payload():
    pz = Packetizer(packet_size=4096)
    chunks = pz.packetize(b"Hello", "TX_001")
    assert len(chunks) == 1
    assert chunks[0] == (1, b"Hello")


# 22. Packetization works for large payloads
def test_packetization_large_payload():
    pz = Packetizer(packet_size=100)
    data = b"X" * 250
    chunks = pz.packetize(data, "TX_001")
    assert len(chunks) == 3
    assert chunks[0] == (1, b"X" * 100)
    assert chunks[1] == (2, b"X" * 100)
    assert chunks[2] == (3, b"X" * 50)


# 23. Receiver reassembles valid packets
def test_receiver_reassembles_valid_packets():
    reassembler = PayloadReassembler()
    assert reassembler.accept_packet(1, b"Chunk 1 ") is True
    assert reassembler.accept_packet(2, b"Chunk 2") is True
    assert reassembler.reassemble() == b"Chunk 1 Chunk 2"


# 24. Duplicate packet does not duplicate delivered payload
def test_duplicate_packet_does_not_duplicate_payload():
    reassembler = PayloadReassembler()
    assert reassembler.accept_packet(1, b"Chunk 1") is True
    assert reassembler.accept_packet(1, b"Chunk 1") is False  # Duplicate ignored!
    assert reassembler.reassemble() == b"Chunk 1"


# 25. Invalid packet is never delivered
def test_invalid_packet_never_delivered(session_setup):
    receiver = session_setup["receiver"]
    corrupt_packet = EncryptedPacket("1.0", "s1", "tx1", 1, "T1_TO_T2", "00" * 12, "00" * 32)

    with pytest.raises(InvalidPacketError):
        receiver.receive_and_decrypt(corrupt_packet, expected_direction="T1_TO_T2")


# 26. Rekeyed session uses new key material
def test_rekeyed_session_uses_new_key_material(session_setup):
    sender = session_setup["sender"]
    receiver = session_setup["receiver"]
    session = session_setup["session"]
    trust_res = session_setup["trust_res"]
    mgr = session_setup["manager"]

    p1 = sender.send_payload(session.session_id, "TX_001", b"Pre-rekey data", "T1_TO_T2", trust_res)[0]

    # Execute Rekey
    mgr.rekey_session(session.session_id)

    p2 = sender.send_payload(session.session_id, "TX_001", b"Post-rekey data", "T1_TO_T2", trust_res)[0]

    assert receiver.receive_and_decrypt(p2, expected_direction="T1_TO_T2") == b"Post-rekey data"


# 27. Old session packet is rejected under new session context
def test_old_session_packet_rejected_under_new_context(session_setup):
    sender = session_setup["sender"]
    receiver = session_setup["receiver"]
    session = session_setup["session"]
    trust_res = session_setup["trust_res"]
    mgr = session_setup["manager"]

    # Send packet before rekey
    old_packet = sender.send_payload(session.session_id, "TX_001", b"Pre-rekey data", "T1_TO_T2", trust_res)[0]

    # Execute Rekey (changes directional key)
    mgr.rekey_session(session.session_id)

    # Attempt to decrypt pre-rekey packet with new key -> Must be rejected!
    with pytest.raises(InvalidPacketError):
        receiver.receive_and_decrypt(old_packet, expected_direction="T1_TO_T2")


# 28. Private and session secret material is not exposed
def test_packet_repr_does_not_leak_secrets():
    packet = EncryptedPacket("1.0", "s1", "tx1", 1, "T1_TO_T2", "11" * 12, "22" * 32)
    p_str = str(packet)
    assert "PrivateKey" not in p_str
    assert "secret" not in p_str.lower()


# 29. Boundary test: empty payload
def test_boundary_empty_payload(session_setup):
    sender = session_setup["sender"]
    receiver = session_setup["receiver"]
    session = session_setup["session"]
    trust_res = session_setup["trust_res"]

    packets = sender.send_payload(session.session_id, "TX_EMPTY", b"", "T1_TO_T2", trust_res)
    assert len(packets) == 1
    decrypted = receiver.receive_and_decrypt(packets[0], "T1_TO_T2")
    assert decrypted == b""


# 30. Boundary test: one byte payload
def test_boundary_one_byte_payload(session_setup):
    sender = session_setup["sender"]
    receiver = session_setup["receiver"]
    session = session_setup["session"]
    trust_res = session_setup["trust_res"]

    packets = sender.send_payload(session.session_id, "TX_1BYTE", b"A", "T1_TO_T2", trust_res)
    assert len(packets) == 1
    decrypted = receiver.receive_and_decrypt(packets[0], "T1_TO_T2")
    assert decrypted == b"A"


# 31. Boundary test: exact packet size payload
def test_boundary_exact_packet_size_payload(session_setup):
    pz = Packetizer(packet_size=100)
    chunks = pz.packetize(b"B" * 100, "TX_EXACT")
    assert len(chunks) == 1
    assert chunks[0][0] == 1


# 32. Boundary test: packet size plus one byte payload
def test_boundary_packet_size_plus_one_payload(session_setup):
    pz = Packetizer(packet_size=100)
    chunks = pz.packetize(b"C" * 101, "TX_OVER")
    assert len(chunks) == 2
    assert chunks[0][0] == 1
    assert chunks[1][0] == 2
