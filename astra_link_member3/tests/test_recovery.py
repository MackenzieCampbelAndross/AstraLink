"""Phase 7: Comprehensive pytest suite for Link Recovery + Secure Resume."""

import hashlib
import json
import os
import shutil
import tempfile
import time
import pytest

from src.authentication import AuthenticationController
from src.identity import TerminalCredentials, TerminalRegistry, generate_credentials
from src.recovery.checkpoint import (
    Checkpoint,
    CheckpointManager,
    CheckpointRollbackError,
    CorruptedCheckpointError,
    InvalidCheckpointError,
)
from src.recovery.reconnect import (
    MaxRecoveryAttemptsExceededError,
    RecoveryController,
    RecoveryError,
)
from src.recovery.resume import (
    ResumeProtocolHandler,
    ResumeRequest,
    ResumeResponse,
    ResumeValidationError,
)
from src.recovery.session_recovery import RecoveryState, RecoveryStateMachine
from src.session.session_manager import SessionManager
from src.tracking.tracking_state import TrackingState
from src.transport.cipher import PacketCipher
from src.transport.packetizer import Packetizer, PayloadReassembler
from src.transport.receiver import SecureReceiver
from src.transport.selective_repeat import ReceiverWindow, SenderWindow
from src.transport.sender import SecureSender
from src.trust.trust_engine import TrustEngine


@pytest.fixture
def test_dir():
    d = tempfile.mkdtemp(prefix="astralink_test_recovery_")
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def registry_and_creds(test_dir):
    t1_creds = generate_credentials("T1")
    t2_creds = generate_credentials("T2")

    registry = TerminalRegistry()
    registry.register_public_credentials(t1_creds.public_credentials)
    registry.register_public_credentials(t2_creds.public_credentials)

    return registry, t1_creds, t2_creds


@pytest.fixture
def locked_tracking():
    return TrackingState(
        timestamp=time.time(),
        tracking_state="LOCKED",
        predicted_x=10.0,
        predicted_y=20.0,
        angular_x=0.01,
        angular_y=0.02,
        velocity_x=0.1,
        velocity_y=0.2,
        motion_consistency=0.95,
        prediction_covariance=[0.05, 0.05],
    )


@pytest.fixture
def lost_tracking():
    return TrackingState(
        timestamp=time.time(),
        tracking_state="LOST",
        predicted_x=0.0,
        predicted_y=0.0,
        angular_x=0.0,
        angular_y=0.0,
        velocity_x=0.0,
        velocity_y=0.0,
        motion_consistency=0.0,
        prediction_covariance=[10.0, 10.0],
    )


# ---------------------------------------------------------------------------
# Test Cases 1-8: Checkpointing & State Machine Fundamentals
# ---------------------------------------------------------------------------

def test_link_loss_changes_state(lost_tracking):
    """1. Link loss changes communication state to INTERRUPTED."""
    sm = RecoveryStateMachine(transfer_id="TX_001", initial_epoch=7)
    assert sm.state == RecoveryState.CONNECTED
    assert sm.transmission_allowed is True

    sm.handle_link_loss(reason="OPTICAL_BEACON_LOST")
    assert sm.state == RecoveryState.INTERRUPTED
    assert sm.transmission_allowed is False
    assert sm.security_status == "INTERRUPTED"


def test_transmission_blocked_during_interruption(locked_tracking):
    """2. Transmission is blocked during interruption and all intermediate recovery states."""
    sm = RecoveryStateMachine(transfer_id="TX_001", initial_epoch=7)
    sm.handle_link_loss()
    assert sm.transmission_allowed is False

    sm.handle_reacquisition(locked_tracking)
    assert sm.transmission_allowed is False

    sm.transition_to_authenticating()
    assert sm.transmission_allowed is False

    sm.handle_authentication_success()
    assert sm.transmission_allowed is False

    sm.handle_session_establishment(new_session_id="SESS_NEW_123")
    assert sm.transmission_allowed is False

    sm.transition_to_resuming()
    assert sm.transmission_allowed is False

    sm.handle_resume_validated()
    assert sm.transmission_allowed is True


def test_checkpoint_is_saved(test_dir):
    """3. Checkpoint is saved persistently."""
    cm = CheckpointManager(checkpoint_dir=test_dir)
    chk = Checkpoint(
        transfer_id="TX_001",
        total_packets=10000,
        last_confirmed=6403,
        next_expected=6404,
        session_id="SESS_OLD_111",
        tracking_epoch=7,
        payload_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        checkpoint_timestamp=time.time(),
    )

    path = cm.save_checkpoint(chk)
    assert os.path.isfile(path)

    loaded = cm.load_checkpoint("TX_001")
    assert loaded is not None
    assert loaded.transfer_id == "TX_001"
    assert loaded.last_confirmed == 6403
    assert loaded.next_expected == 6404
    assert loaded.tracking_epoch == 7


def test_checkpoint_survives_process_state_recreation(test_dir):
    """4. Checkpoint survives process state recreation."""
    cm1 = CheckpointManager(checkpoint_dir=test_dir)
    chk = Checkpoint(
        transfer_id="TX_002",
        total_packets=5000,
        last_confirmed=2500,
        next_expected=2501,
        session_id="SESS_ABC",
        tracking_epoch=3,
        payload_hash="hash12345",
        checkpoint_timestamp=time.time(),
    )
    cm1.save_checkpoint(chk)

    # Recreate CheckpointManager instance
    cm2 = CheckpointManager(checkpoint_dir=test_dir)
    loaded = cm2.load_checkpoint("TX_002")
    assert loaded is not None
    assert loaded.last_confirmed == 2500


def test_corrupted_checkpoint_is_rejected(test_dir):
    """5. Corrupted checkpoint is rejected safely."""
    cm = CheckpointManager(checkpoint_dir=test_dir)
    chk_path = cm._get_checkpoint_path("TX_CORRUPT")
    with open(chk_path, "w", encoding="utf-8") as f:
        f.write("{ invalid json content ...")

    with pytest.raises(CorruptedCheckpointError):
        cm.load_checkpoint("TX_CORRUPT")


def test_invalid_checkpoint_is_rejected(test_dir):
    """6. Invalid checkpoint values (e.g. negative or next_expected mismatch) are rejected."""
    cm = CheckpointManager(checkpoint_dir=test_dir)

    # Negative last_confirmed
    chk_neg = Checkpoint(
        transfer_id="TX_BAD",
        total_packets=100,
        last_confirmed=-5,
        next_expected=-4,
        session_id="S1",
        tracking_epoch=1,
        payload_hash="h1",
        checkpoint_timestamp=time.time(),
    )
    with pytest.raises(InvalidCheckpointError):
        cm.validate_checkpoint(chk_neg)

    # Discontiguous next_expected
    chk_gap = Checkpoint(
        transfer_id="TX_BAD2",
        total_packets=100,
        last_confirmed=50,
        next_expected=52,
        session_id="S1",
        tracking_epoch=1,
        payload_hash="h1",
        checkpoint_timestamp=time.time(),
    )
    with pytest.raises(InvalidCheckpointError):
        cm.validate_checkpoint(chk_gap)


def test_checkpoint_atomic_write_behaviour(test_dir):
    """7. Checkpoint atomic write behavior uses tmp file replacement."""
    cm = CheckpointManager(checkpoint_dir=test_dir)
    chk = Checkpoint(
        transfer_id="TX_ATOMIC",
        total_packets=10,
        last_confirmed=5,
        next_expected=6,
        session_id="S_ATOMIC",
        tracking_epoch=1,
        payload_hash="h_atomic",
        checkpoint_timestamp=time.time(),
    )
    cm.save_checkpoint(chk)

    tmp_path = cm._get_tmp_path("TX_ATOMIC")
    target_path = cm._get_checkpoint_path("TX_ATOMIC")

    assert not os.path.exists(tmp_path)
    assert os.path.exists(target_path)


def test_tracking_epoch_increments_after_link_loss():
    """8. Tracking epoch increments after link loss."""
    sm = RecoveryStateMachine(transfer_id="TX_001", initial_epoch=7)
    assert sm.tracking_epoch == 7
    sm.handle_link_loss()
    assert sm.tracking_epoch == 8


# ---------------------------------------------------------------------------
# Test Cases 9-14: Reacquisition, Reauth & Session Separation
# ---------------------------------------------------------------------------

def test_reacquired_beacon_becomes_locked_unverified(locked_tracking):
    """9. Reacquired beacon becomes LOCKED_UNVERIFIED."""
    sm = RecoveryStateMachine(transfer_id="TX_001", initial_epoch=7)
    sm.handle_link_loss()
    sm.handle_reacquisition(locked_tracking)

    assert sm.state == RecoveryState.REACQUIRING
    assert sm.security_status == "LOCKED_UNVERIFIED"
    assert sm.transmission_allowed is False


def test_fresh_authentication_is_required(registry_and_creds, locked_tracking, test_dir):
    """10. Fresh authentication is required after reacquisition."""
    registry, t1_creds, t2_creds = registry_and_creds
    ctrl = RecoveryController("TX_001", checkpoint_dir=test_dir)

    ctrl.handle_link_interruption(100, 50, 51, "SESS_OLD", "hash")
    ctrl.handle_beacon_reacquisition(locked_tracking)

    new_sess = ctrl.execute_recovery(
        sender_creds=t1_creds,
        receiver_creds=t2_creds,
        registry=registry,
        tracking_state=locked_tracking,
        total_packets=100,
        payload_hash="hash",
        receiver_verified_checkpoint=50,
    )
    assert new_sess is not None
    assert ctrl.state_machine.state == RecoveryState.CONNECTED
    assert ctrl.state_machine.transmission_allowed is True


def test_old_authentication_cannot_restore_transmission(registry_and_creds, locked_tracking, test_dir):
    """11. Old authentication cannot restore transmission without fresh authentication."""
    registry, t1_creds, t2_creds = registry_and_creds
    ctrl = RecoveryController("TX_001", checkpoint_dir=test_dir)

    ctrl.handle_link_interruption(100, 50, 51, "SESS_OLD", "hash")
    ctrl.handle_beacon_reacquisition(locked_tracking)

    # Create unauthenticated terminal with wrong key
    fake_t2 = generate_credentials("T2")

    with pytest.raises(RecoveryError, match="Fresh reauthentication failed"):
        ctrl.execute_recovery(
            sender_creds=t1_creds,
            receiver_creds=fake_t2,
            registry=registry,
            tracking_state=locked_tracking,
            total_packets=100,
            payload_hash="hash",
            receiver_verified_checkpoint=50,
        )

    assert ctrl.state_machine.transmission_allowed is False
    assert ctrl.state_machine.state == RecoveryState.FAILED


def test_new_secure_session_is_established(registry_and_creds, locked_tracking, test_dir):
    """12. New secure session is established after reauth."""
    registry, t1_creds, t2_creds = registry_and_creds
    ctrl = RecoveryController("TX_001", checkpoint_dir=test_dir)
    ctrl.handle_link_interruption(100, 50, 51, "SESS_OLD_999", "hash")

    new_sess = ctrl.execute_recovery(
        sender_creds=t1_creds,
        receiver_creds=t2_creds,
        registry=registry,
        tracking_state=locked_tracking,
        total_packets=100,
        payload_hash="hash",
        receiver_verified_checkpoint=50,
    )
    assert new_sess.session_id != "SESS_OLD_999"


def test_new_session_keys_differ_from_old_session_keys(registry_and_creds):
    """13. New session keys differ from old session keys."""
    sm = SessionManager()
    old_sess = sm.establish_session("T1", "T2", tracking_epoch=7, authentication_valid=True, trust_authorized=True)
    new_sess = sm.establish_session("T1", "T2", tracking_epoch=8, authentication_valid=True, trust_authorized=True)

    assert old_sess.session_id != new_sess.session_id
    assert old_sess.derived_keys.initiator_to_responder_key != new_sess.derived_keys.initiator_to_responder_key
    assert old_sess.derived_keys.responder_to_initiator_key != new_sess.derived_keys.responder_to_initiator_key


def test_same_transfer_continues_across_new_session(registry_and_creds, locked_tracking, test_dir):
    """14. Same transfer continues across new session."""
    registry, t1_creds, t2_creds = registry_and_creds
    ctrl = RecoveryController("TX_TRANSFER_123", checkpoint_dir=test_dir)
    ctrl.handle_link_interruption(100, 64, 65, "SESS_1", "hash_abc")

    new_sess = ctrl.execute_recovery(
        sender_creds=t1_creds,
        receiver_creds=t2_creds,
        registry=registry,
        tracking_state=locked_tracking,
        total_packets=100,
        payload_hash="hash_abc",
        receiver_verified_checkpoint=64,
    )
    assert ctrl.transfer_id == "TX_TRANSFER_123"
    assert ctrl.current_checkpoint.last_confirmed == 64


# ---------------------------------------------------------------------------
# Test Cases 15-22: Resume Protocol & Anti-Rollback Validation
# ---------------------------------------------------------------------------

def test_secure_resume_request_works():
    """15. Secure resume request works and serializes correctly."""
    req = ResumeProtocolHandler.create_request(
        transfer_id="TX_001",
        total_packets=1000,
        tracking_epoch=8,
        session_id="SESS_NEW",
        sender_checkpoint=6403,
        payload_hash="hash",
    )
    b = req.to_bytes()
    parsed = ResumeRequest.from_bytes(b)
    assert parsed == req


def test_resume_response_is_authenticated(registry_and_creds):
    """16. Resume response is authenticated using active session keys."""
    sm = SessionManager()
    sess = sm.establish_session("T1", "T2", tracking_epoch=8, authentication_valid=True, trust_authorized=True)

    resp = ResumeResponse(
        transfer_id="TX_001",
        receiver_verified_checkpoint=6403,
        total_packets=1000,
        tracking_epoch=8,
        session_id=sess.session_id,
        timestamp=time.time(),
        status="ACCEPTED",
        reason="RESUME_AUTHORIZED",
    )

    packet = ResumeProtocolHandler.encrypt_message(
        msg_bytes=resp.to_bytes(),
        session_key=sess.derived_keys.responder_to_initiator_key,
        protocol_version="1.0",
        session_id=sess.session_id,
        transfer_id="TX_001",
        sequence_number=1,
        direction="T2_TO_T1",
    )

    decrypted = ResumeProtocolHandler.decrypt_message(
        packet=packet,
        session_key=sess.derived_keys.responder_to_initiator_key,
    )
    parsed = ResumeResponse.from_bytes(decrypted)
    assert parsed.receiver_verified_checkpoint == 6403


def test_wrong_transfer_id_is_rejected():
    """17. Wrong transfer ID is rejected during resume response processing."""
    req = ResumeProtocolHandler.create_request("TX_001", 100, 8, "S1", 50, "hash")
    resp = ResumeProtocolHandler.process_request(
        request=req,
        expected_transfer_id="TX_DIFFERENT",
        expected_epoch=8,
        expected_session_id="S1",
        expected_payload_hash="hash",
        receiver_verified_checkpoint=50,
    )
    assert resp.status == "REJECTED"
    assert "TRANSFER_ID_MISMATCH" in resp.reason


def test_wrong_session_id_is_rejected():
    """18. Wrong session ID is rejected."""
    req = ResumeProtocolHandler.create_request("TX_001", 100, 8, "S1_BAD", 50, "hash")
    resp = ResumeProtocolHandler.process_request(
        request=req,
        expected_transfer_id="TX_001",
        expected_epoch=8,
        expected_session_id="S1_REAL",
        expected_payload_hash="hash",
        receiver_verified_checkpoint=50,
    )
    assert resp.status == "REJECTED"
    assert "SESSION_ID_MISMATCH" in resp.reason


def test_wrong_epoch_is_rejected():
    """19. Wrong epoch is rejected."""
    req = ResumeProtocolHandler.create_request("TX_001", 100, 7, "S1", 50, "hash")
    resp = ResumeProtocolHandler.process_request(
        request=req,
        expected_transfer_id="TX_001",
        expected_epoch=8,
        expected_session_id="S1",
        expected_payload_hash="hash",
        receiver_verified_checkpoint=50,
    )
    assert resp.status == "REJECTED"
    assert "EPOCH_MISMATCH" in resp.reason


def test_invalid_checkpoint_value_is_rejected():
    """20. Invalid checkpoint value in response is rejected."""
    resp = ResumeResponse(
        transfer_id="TX_001",
        receiver_verified_checkpoint=-10,
        total_packets=100,
        tracking_epoch=8,
        session_id="S1",
        timestamp=time.time(),
        status="ACCEPTED",
        reason="OK",
    )
    with pytest.raises(ResumeValidationError, match="Invalid negative receiver checkpoint"):
        ResumeProtocolHandler.validate_response(resp, "TX_001", 8, "S1", 0, 100)


def test_checkpoint_rollback_is_handled_safely():
    """21. Checkpoint rollback is handled safely."""
    cm = CheckpointManager()
    chk = Checkpoint("TX_001", 10000, 4000, 4001, "S1", 8, "hash", time.time())
    with pytest.raises(CheckpointRollbackError):
        cm.validate_checkpoint(chk, expected_total_packets=10000, verified_last_confirmed=6403)


def test_higher_unauthenticated_checkpoint_cannot_be_injected(registry_and_creds, locked_tracking, test_dir):
    """22. Higher unauthenticated checkpoint cannot be injected."""
    registry, t1_creds, t2_creds = registry_and_creds
    ctrl = RecoveryController("TX_001", checkpoint_dir=test_dir)
    ctrl.handle_link_interruption(10000, 6403, 6404, "SESS_OLD", "hash")

    # Unauthenticated fake response attempting last_confirmed=9999
    fake_resp = ResumeResponse(
        transfer_id="TX_001",
        receiver_verified_checkpoint=9999,
        total_packets=10000,
        tracking_epoch=8,
        session_id="SESS_FAKE",
        timestamp=time.time(),
        status="ACCEPTED",
        reason="OK",
    )

    with pytest.raises(ResumeValidationError, match="Session ID mismatch"):
        ResumeProtocolHandler.validate_response(fake_resp, "TX_001", 8, "SESS_REAL", 6403, 10000)


# ---------------------------------------------------------------------------
# Test Cases 23-27: Transport ARQ Integration & Duplicate Safety
# ---------------------------------------------------------------------------

def test_resume_starts_from_last_verified_packet():
    """23. Resume starts from last verified packet + 1."""
    sw = SenderWindow(window_size=32)
    # Set confirmed checkpoint at 6403
    sw.base_sequence = 6404
    sw.next_sequence = 6404

    assert sw.base_sequence == 6404
    assert sw.can_send_next() is True


def test_packets_before_checkpoint_are_not_unnecessarily_resent():
    """24. Packets before checkpoint are not unnecessarily resent."""
    sw = SenderWindow(window_size=32)
    sw.base_sequence = 6404
    sw.next_sequence = 6404

    timed_out = sw.get_timed_out_packets(timeout_seconds=0.01)
    assert len(timed_out) == 0


def test_required_missing_packets_are_retransmitted(registry_and_creds):
    """25. Required missing packets are retransmitted via SenderWindow ARQ."""
    sm = SessionManager()
    sess = sm.establish_session("T1", "T2", tracking_epoch=8, authentication_valid=True, trust_authorized=True)

    sw = SenderWindow()
    packet = PacketCipher.encrypt(
        key=sess.derived_keys.initiator_to_responder_key,
        plaintext=b"Packet 6404 data chunk",
        protocol_version="1.0",
        session_id=sess.session_id,
        transfer_id="TX_001",
        sequence_number=6404,
        direction="T1_TO_T2",
    )
    sw.add_sent_packet(packet, current_time=time.time() - 1.0)

    timed_out = sw.get_timed_out_packets(timeout_seconds=0.100)
    assert len(timed_out) == 1
    assert timed_out[0].sequence_number == 6404


def test_duplicate_packets_after_recovery_are_safely_handled(registry_and_creds):
    """26. Duplicate packets after recovery are safely handled by ReceiverWindow without double delivery."""
    sm = SessionManager()
    sess = sm.establish_session("T1", "T2", tracking_epoch=8, authentication_valid=True, trust_authorized=True)

    rw = ReceiverWindow()
    rw.cumulative_ack = 6403

    packet = PacketCipher.encrypt(
        key=sess.derived_keys.initiator_to_responder_key,
        plaintext=b"Data 6404",
        protocol_version="1.0",
        session_id=sess.session_id,
        transfer_id="TX_001",
        sequence_number=6404,
        direction="T1_TO_T2",
    )

    ack1, chunks1, dup1 = rw.process_received_packet(packet, b"Data 6404")
    assert dup1 is False
    assert len(chunks1) == 1

    # Retransmitted duplicate 6404 after recovery
    ack2, chunks2, dup2 = rw.process_received_packet(packet, b"Data 6404")
    assert dup2 is True
    assert len(chunks2) == 0  # Application payload not duplicated!


def test_ack_loss_before_link_failure_handled_correctly(registry_and_creds):
    """27. ACK loss before link failure is handled correctly upon recovery."""
    sm = SessionManager()
    sess = sm.establish_session("T1", "T2", tracking_epoch=8, authentication_valid=True, trust_authorized=True)

    rw = ReceiverWindow()
    rw.cumulative_ack = 6402

    packet = PacketCipher.encrypt(
        key=sess.derived_keys.initiator_to_responder_key,
        plaintext=b"Data 6403",
        protocol_version="1.0",
        session_id=sess.session_id,
        transfer_id="TX_001",
        sequence_number=6403,
        direction="T1_TO_T2",
    )

    ack1, chunks1, dup1 = rw.process_received_packet(packet, b"Data 6403")
    assert dup1 is False
    assert rw.cumulative_ack == 6403

    # Link fails, sender retransmits 6403
    ack2, chunks2, dup2 = rw.process_received_packet(packet, b"Data 6403")
    assert dup2 is True
    assert ack2.cumulative_ack == 6403


# ---------------------------------------------------------------------------
# Test Cases 28-32: End-to-End Recovery Scenarios & Retry Limits
# ---------------------------------------------------------------------------

def test_temporary_interruption_recovery_works(registry_and_creds, locked_tracking, test_dir):
    """28. Temporary interruption recovery flow works end-to-end."""
    registry, t1_creds, t2_creds = registry_and_creds
    ctrl = RecoveryController("TX_TEMP", checkpoint_dir=test_dir)

    # Link loss at packet 6403
    chk = ctrl.handle_link_interruption(
        total_packets=10000,
        last_confirmed=6403,
        next_expected=6404,
        session_id="SESS_OLD",
        payload_hash="hash_temp",
    )
    assert chk.last_confirmed == 6403

    # Reacquire beacon
    ctrl.handle_beacon_reacquisition(locked_tracking)

    # Execute secure recovery
    new_sess = ctrl.execute_recovery(
        sender_creds=t1_creds,
        receiver_creds=t2_creds,
        registry=registry,
        tracking_state=locked_tracking,
        total_packets=10000,
        payload_hash="hash_temp",
        receiver_verified_checkpoint=6403,
    )
    assert new_sess is not None
    assert ctrl.state_machine.state == RecoveryState.CONNECTED
    assert ctrl.state_machine.transmission_allowed is True
    assert ctrl.metrics.total_secure_recovery_time_sec >= 0.0


def test_session_expiry_recovery_works(registry_and_creds, locked_tracking, test_dir):
    """29. Session expiry during long interruption works and recovers transfer."""
    registry, t1_creds, t2_creds = registry_and_creds

    sm = SessionManager(session_lifetime_seconds=0.01)
    old_sess = sm.establish_session("T1", "T2", tracking_epoch=1, authentication_valid=True, trust_authorized=True)

    time.sleep(0.02)
    assert sm.is_session_valid(old_sess.session_id) is False  # Expired!

    # Execute recovery with fresh session
    ctrl = RecoveryController("TX_EXPIRE", checkpoint_dir=test_dir)
    ctrl.handle_link_interruption(1000, 500, 501, old_sess.session_id, "hash_exp")
    ctrl.handle_beacon_reacquisition(locked_tracking)

    new_sess = ctrl.execute_recovery(
        sender_creds=t1_creds,
        receiver_creds=t2_creds,
        registry=registry,
        tracking_state=locked_tracking,
        total_packets=1000,
        payload_hash="hash_exp",
        receiver_verified_checkpoint=500,
        session_manager=sm,
    )

    assert new_sess.session_id != old_sess.session_id
    assert sm.is_session_valid(new_sess.session_id) is True
    assert ctrl.state_machine.transmission_allowed is True


def test_recovery_retry_limit_works(registry_and_creds, locked_tracking, test_dir):
    """30. Recovery retry limit stops after max_recovery_attempts."""
    registry, t1_creds, t2_creds = registry_and_creds
    ctrl = RecoveryController("TX_RETRY", max_recovery_attempts=2, checkpoint_dir=test_dir)

    ctrl.handle_link_interruption(100, 10, 11, "S1", "h1")
    ctrl.handle_beacon_reacquisition(locked_tracking)

    fake_t2 = generate_credentials("T2")

    # Attempt 1 -> fails reauth
    with pytest.raises(RecoveryError):
        ctrl.execute_recovery(t1_creds, fake_t2, registry, locked_tracking, 100, "h1", 10)

    # Attempt 2 -> fails reauth
    with pytest.raises(RecoveryError):
        ctrl.execute_recovery(t1_creds, fake_t2, registry, locked_tracking, 100, "h1", 10)

    # Attempt 3 -> exceeds max_recovery_attempts (2)
    with pytest.raises(MaxRecoveryAttemptsExceededError):
        ctrl.execute_recovery(t1_creds, t2_creds, registry, locked_tracking, 100, "h1", 10)

    assert ctrl.state_machine.state == RecoveryState.FAILED
    assert ctrl.state_machine.transmission_allowed is False


def test_recovery_failure_blocks_transmission(registry_and_creds, lost_tracking, test_dir):
    """31. Recovery failure blocks transmission."""
    registry, t1_creds, t2_creds = registry_and_creds
    ctrl = RecoveryController("TX_FAIL", checkpoint_dir=test_dir)

    ctrl.handle_link_interruption(100, 10, 11, "S1", "h1")

    # Attempt recovery while lost
    with pytest.raises(RecoveryError, match="Target optical beacon is not locked"):
        ctrl.execute_recovery(t1_creds, t2_creds, registry, lost_tracking, 100, "h1", 10)

    assert ctrl.state_machine.transmission_allowed is False


def test_complete_transfer_after_recovery_works(registry_and_creds, locked_tracking, test_dir):
    """32. Complete payload reconstructed after link interruption & recovery."""
    registry, t1_creds, t2_creds = registry_and_creds

    # Original payload
    raw_payload = b"AstraLink Phase 7 Full Transfer Payload Verification " * 100
    payload_hash = hashlib.sha256(raw_payload).hexdigest()

    packetizer = Packetizer(packet_size=200)
    packets = packetizer.packetize(raw_payload, transfer_id="TX_FULL_REC")
    total_packets = len(packets)

    sm = SessionManager()
    sess1 = sm.establish_session("T1", "T2", tracking_epoch=1, authentication_valid=True, trust_authorized=True)

    rw1 = ReceiverWindow()

    # Transmit first half of packets
    cutoff = total_packets // 2
    for seq, chunk_bytes in packets[:cutoff]:
        enc = PacketCipher.encrypt(sess1.derived_keys.initiator_to_responder_key, chunk_bytes, "1.0", sess1.session_id, "TX_FULL_REC", seq, "T1_TO_T2")
        rw1.process_received_packet(enc, chunk_bytes)

    last_confirmed_before_loss = rw1.cumulative_ack
    assert last_confirmed_before_loss == cutoff

    # LINK LOSS!
    ctrl = RecoveryController("TX_FULL_REC", checkpoint_dir=test_dir)
    ctrl.handle_link_interruption(total_packets, last_confirmed_before_loss, last_confirmed_before_loss + 1, sess1.session_id, payload_hash)
    ctrl.handle_beacon_reacquisition(locked_tracking)

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

    reassembler = PayloadReassembler()
    for seq, chunk_bytes in packets[:cutoff]:
        reassembler.accept_packet(seq, chunk_bytes)

    rw2 = ReceiverWindow()
    rw2.cumulative_ack = rw1.cumulative_ack

    for seq, chunk_bytes in packets[cutoff:]:
        enc = PacketCipher.encrypt(sess2.derived_keys.initiator_to_responder_key, chunk_bytes, "1.0", sess2.session_id, "TX_FULL_REC", seq, "T1_TO_T2")
        dec = PacketCipher.decrypt(sess2.derived_keys.initiator_to_responder_key, enc)
        _, deliverable, _ = rw2.process_received_packet(enc, dec)
        for d_seq, d_bytes in deliverable:
            reassembler.accept_packet(d_seq, d_bytes)

    reconstructed = reassembler.reassemble()
    assert len(reconstructed) == len(raw_payload)
    assert reconstructed == raw_payload
    assert hashlib.sha256(reconstructed).hexdigest() == payload_hash
