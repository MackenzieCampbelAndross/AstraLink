"""Phase 8: End-to-End System Pipeline & Attack Resilience Integration Test."""

import hashlib
import os
import shutil
import tempfile
import time
import pytest

from src.attacks import FakeBeaconAttack, PacketTamperingAttack
from src.authentication import AuthenticationController
from src.identity import TerminalIdentity, TerminalRegistry, generate_credentials
from src.recovery import CheckpointManager, RecoveryController, RecoveryError, RecoveryState, ResumeProtocolHandler
from src.session import SessionManager
from src.tracking import TrackingState
from src.transport.cipher import InvalidPacketError, PacketCipher
from src.transport.packetizer import Packetizer, PayloadReassembler
from src.transport.selective_repeat import ReceiverWindow, SenderWindow
from src.trust import SecurityLogger, TransmissionAuthorizationGate, TrustEngine


@pytest.fixture
def test_dir():
    d = tempfile.mkdtemp(prefix="astralink_test_e2e_")
    yield d
    shutil.rmtree(d, ignore_errors=True)


def test_end_to_end_legitimate_pipeline(test_dir):
    """End-to-End test of full Astra Link system pipeline (Phase 1 through Phase 7)."""

    # 1. IDENTITY & REGISTRY (Phase 1)
    t1_creds = generate_credentials("T1")
    t2_creds = generate_credentials("T2")

    registry = TerminalRegistry()
    registry.register_public_credentials(t1_creds.public_credentials)
    registry.register_public_credentials(t2_creds.public_credentials)

    # 2. MUTUAL AUTHENTICATION (Phase 2)
    auth_ctrl = AuthenticationController(registry=registry)
    auth_res = auth_ctrl.execute_mutual_authentication(t1_creds, t2_creds, tracking_epoch=1)
    assert auth_res.authenticated is True

    # 3. TRUST EVALUATION & TRANSMISSION AUTHORIZATION (Phase 3)
    locked_tracking = TrackingState(
        timestamp=time.time(),
        tracking_state="LOCKED",
        predicted_x=10.0,
        predicted_y=20.0,
        angular_x=0.01,
        angular_y=0.02,
        velocity_x=0.1,
        velocity_y=0.2,
        motion_consistency=0.95,
    )
    te = TrustEngine()
    trust_res = te.evaluate("T1", "T2", tracking_state=locked_tracking, authentication_valid=True)
    gate = TransmissionAuthorizationGate.can_transmit(trust_res)
    assert gate.authorized is True

    # 4. SECURE SESSION ESTABLISHMENT (Phase 4)
    sm = SessionManager()
    sess1 = sm.establish_session("T1", "T2", tracking_epoch=1, authentication_valid=True, trust_authorized=True)
    assert sess1 is not None

    # 5. ENCRYPTED TRANSPORT & ARQ (Phase 5 & 6)
    raw_payload = b"AstraLink Full System Integration Payload Test " * 50
    payload_hash = hashlib.sha256(raw_payload).hexdigest()

    packetizer = Packetizer(packet_size=150)
    packets = packetizer.packetize(raw_payload, transfer_id="TX_E2E")
    total_packets = len(packets)

    rw1 = ReceiverWindow()
    reassembler = PayloadReassembler()

    # Transmit first 40% of packets
    cutoff = int(total_packets * 0.4)
    for seq, chunk in packets[:cutoff]:
        enc = PacketCipher.encrypt(sess1.derived_keys.initiator_to_responder_key, chunk, "1.0", sess1.session_id, "TX_E2E", seq, "T1_TO_T2")
        rw1.process_received_packet(enc, chunk)
        reassembler.accept_packet(seq, chunk)

    last_confirmed_before_loss = rw1.cumulative_ack
    assert last_confirmed_before_loss == cutoff

    # 6. LINK LOSS & PERSISTENT CHECKPOINT (Phase 7)
    ctrl = RecoveryController("TX_E2E", checkpoint_dir=test_dir)
    chk = ctrl.handle_link_interruption(
        total_packets=total_packets,
        last_confirmed=last_confirmed_before_loss,
        next_expected=last_confirmed_before_loss + 1,
        session_id=sess1.session_id,
        payload_hash=payload_hash,
    )
    assert chk.last_confirmed == cutoff
    assert ctrl.state_machine.transmission_allowed is False

    # 7. BEACON REACQUISITION & FRESH AUTHENTICATION & NEW SESSION (Phase 7)
    ctrl.handle_beacon_reacquisition(locked_tracking)
    assert ctrl.state_machine.security_status == "LOCKED_UNVERIFIED"

    sess2 = ctrl.execute_recovery(
        sender_creds=t1_creds,
        receiver_creds=t2_creds,
        registry=registry,
        tracking_state=locked_tracking,
        total_packets=total_packets,
        payload_hash=payload_hash,
        receiver_verified_checkpoint=last_confirmed_before_loss,
        session_manager=sm,
    )
    assert sess2.session_id != sess1.session_id
    assert ctrl.state_machine.transmission_allowed is True

    # 8. RESUME & COMPLETE TRANSMISSION (Phase 6 & 7)
    rw2 = ReceiverWindow()
    rw2.cumulative_ack = last_confirmed_before_loss

    for seq, chunk in packets[cutoff:]:
        enc = PacketCipher.encrypt(sess2.derived_keys.initiator_to_responder_key, chunk, "1.0", sess2.session_id, "TX_E2E", seq, "T1_TO_T2")
        dec = PacketCipher.decrypt(sess2.derived_keys.initiator_to_responder_key, enc)
        _, deliverable, _ = rw2.process_received_packet(enc, dec)
        for d_seq, d_bytes in deliverable:
            reassembler.accept_packet(d_seq, d_bytes)

    reconstructed = reassembler.reassemble()
    assert len(reconstructed) == len(raw_payload)
    assert reconstructed == raw_payload
    assert hashlib.sha256(reconstructed).hexdigest() == payload_hash


def test_end_to_end_with_interleaved_attacks(test_dir):
    """End-to-End pipeline with fake beacon attack and packet tampering injection."""
    registry = TerminalRegistry()
    t1_creds = generate_credentials("T1")
    t2_creds = generate_credentials("T2")
    registry.register_public_credentials(t1_creds.public_credentials)
    registry.register_public_credentials(t2_creds.public_credentials)

    # 1. Fake beacon attack attempt during recovery
    ctrl = RecoveryController("TX_ATTACK", checkpoint_dir=test_dir)
    ctrl.handle_link_interruption(100, 10, 11, "SESS_OLD", "hash")

    locked_tracking = TrackingState(100.0, "LOCKED", 10.0, 20.0, 0.01, 0.02, 0.1, 0.2, 0.95)
    ctrl.handle_beacon_reacquisition(locked_tracking)

    fake_t2 = generate_credentials("T2")

    # Fake beacon attempt fails
    with pytest.raises(RecoveryError):
        ctrl.execute_recovery(t1_creds, fake_t2, registry, locked_tracking, 100, "hash", 10)

    assert ctrl.state_machine.transmission_allowed is False

    # 2. Legitimate recovery succeeds
    sess2 = ctrl.execute_recovery(t1_creds, t2_creds, registry, locked_tracking, 100, "hash", 10)
    assert ctrl.state_machine.transmission_allowed is True

    # 3. Packet tampering attempt during transmission
    valid_p = PacketCipher.encrypt(
        sess2.derived_keys.initiator_to_responder_key, b"Payload Chunk", "1.0", sess2.session_id, "TX_ATTACK", 11, "T1_TO_T2"
    )

    tamper_attack = PacketTamperingAttack()
    tampered_p = tamper_attack.tamper_packet(valid_p, "ciphertext")

    with pytest.raises(InvalidPacketError):
        PacketCipher.decrypt(sess2.derived_keys.initiator_to_responder_key, tampered_p)
