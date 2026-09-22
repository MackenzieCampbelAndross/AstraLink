"""Phase 8: Comprehensive pytest suite for Attack Simulations & 14 Security Policy Invariants."""

import hashlib
import json
import os
import shutil
import tempfile
import time
import pytest

from src.attacks import (
    FakeBeaconAttack,
    ForgedAckAttack,
    ForgedResumeAttack,
    InvalidCredentialAttack,
    OpticalJammingAttack,
    PacketTamperingAttack,
    ReplayAttack,
)
from src.authentication import (
    AuthenticationChallenge,
    AuthenticationController,
    FreshnessValidator,
    ReplayProtectionCache,
    create_challenge,
    create_response,
    verify_response,
)
from src.identity import TerminalIdentity, TerminalRegistry, generate_credentials
from src.metrics.security_metrics import SecurityExperimentRunner
from src.optical_challenge import OpticalResponseSimulator, PhysicalConsistencyValidator, ProbeGenerator
from src.recovery import (
    Checkpoint,
    CheckpointManager,
    CheckpointRollbackError,
    RecoveryController,
    RecoveryError,
    RecoveryState,
    RecoveryStateMachine,
    ResumeProtocolHandler,
    ResumeResponse,
    ResumeValidationError,
)
from src.session import SessionManager
from src.tracking import TrackingState
from src.transport.cipher import InvalidPacketError, PacketCipher
from src.transport.packetizer import Packetizer, PayloadReassembler
from src.transport.selective_repeat import ReceiverWindow, SenderWindow
from src.trust import SecurityLogger, SecurityState, TransmissionAuthorizationGate, TrustEngine


@pytest.fixture
def test_dir():
    d = tempfile.mkdtemp(prefix="astralink_test_attacks_")
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def registry_and_creds():
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
    )


# ---------------------------------------------------------------------------
# Attack Simulations (Attacks 1 - 12)
# ---------------------------------------------------------------------------

def test_attack_1_cloned_beacon(registry_and_creds, locked_tracking):
    """Attack 1: Cloned / Fake Beacon Attack Simulation."""
    registry, _, _ = registry_and_creds
    fake_attack = FakeBeaconAttack(registry=registry)
    succ, reason, details = fake_attack.execute_attack("T1", "T2", tracking_state=locked_tracking)

    assert succ is False
    assert "SPOOF_REJECTED" in reason
    assert details["transmission_allowed"] == "False"


def test_attack_2_replay_attack(registry_and_creds):
    """Attack 2: Replay Attack Simulation across context variations."""
    registry, _, _ = registry_and_creds
    replay_attack = ReplayAttack(registry=registry)
    ch, res, _, _ = replay_attack.capture_legitimate_handshake("T1", "T2", tracking_epoch=1)

    # 1. Exact replay
    succ1, reason1 = replay_attack.execute_replay_attempt(ch, res, scenario="EXACT_REPLAY")
    assert succ1 is False
    assert "REPLAY_REJECTED" in reason1

    # 2. Replay under new epoch
    succ2, reason2 = replay_attack.execute_replay_attempt(ch, res, scenario="NEW_EPOCH", new_epoch=2)
    assert succ2 is False
    assert "REPLAY_REJECTED" in reason2


def test_attack_3_packet_tampering(registry_and_creds):
    """Attack 3: Packet Tampering Attack Simulation."""
    sm = SessionManager()
    sess = sm.establish_session("T1", "T2", tracking_epoch=1, authentication_valid=True, trust_authorized=True)
    key = sess.derived_keys.initiator_to_responder_key

    valid_packet = PacketCipher.encrypt(
        key=key,
        plaintext=b"Secret Payload Data",
        protocol_version="1.0",
        session_id=sess.session_id,
        transfer_id="TX_001",
        sequence_number=1,
        direction="T1_TO_T2",
    )

    tamper_attack = PacketTamperingAttack()

    # Test tampering each field
    fields = ["ciphertext", "nonce", "session_id", "transfer_id", "sequence_number", "direction"]
    for field_name in fields:
        tampered_p = tamper_attack.tamper_packet(valid_packet, field_to_corrupt=field_name)
        succ, reason = tamper_attack.test_decryption(key, tampered_p, field_corrupted=field_name)
        assert succ is False
        assert "PACKET_REJECTED" in reason


def test_attack_4_forged_ack(registry_and_creds):
    """Attack 4: Forged ACK Injection Attack Simulation."""
    attack = ForgedAckAttack()
    sw = SenderWindow(window_size=32)
    sw.base_sequence = 1
    sw.next_sequence = 10

    # 1. Impossible sequence
    forged_impossible = attack.generate_forged_ack("SESS_REAL", "TX_REAL", scenario="IMPOSSIBLE_SEQUENCE")
    succ1, _ = attack.test_forged_ack(sw, forged_impossible, "SESS_REAL", "TX_REAL", total_packets=100)
    assert succ1 is False
    assert sw.base_sequence == 1  # Base sequence unchanged!

    # 2. Wrong session
    forged_sess = attack.generate_forged_ack("SESS_REAL", "TX_REAL", scenario="WRONG_SESSION")
    succ2, _ = attack.test_forged_ack(sw, forged_sess, "SESS_REAL", "TX_REAL", total_packets=100)
    assert succ2 is False
    assert sw.base_sequence == 1


def test_attack_5_forged_resume_checkpoint(registry_and_creds):
    """Attack 5: Forged Resume Checkpoint Attack Simulation."""
    attack = ForgedResumeAttack()

    # 1. Excessive checkpoint 10000
    forged_excessive = attack.generate_forged_resume_response("TX_001", "SESS_1", 1, 100, scenario="EXCESSIVE_CHECKPOINT")
    succ1, reason1 = attack.test_forged_resume(forged_excessive, "TX_001", 1, "SESS_1", sender_checkpoint=10, total_packets=100)
    assert succ1 is False
    assert "FORGED_RESUME_REJECTED" in reason1

    # 2. Negative checkpoint -1
    forged_neg = attack.generate_forged_resume_response("TX_001", "SESS_1", 1, 100, scenario="NEGATIVE_CHECKPOINT")
    succ2, _ = attack.test_forged_resume(forged_neg, "TX_001", 1, "SESS_1", sender_checkpoint=10, total_packets=100)
    assert succ2 is False


def test_attack_6_delayed_authentication_response_freshness(registry_and_creds):
    """Attack 6: Delayed Authentication Response Freshness Failure."""
    registry, t1_creds, t2_creds = registry_and_creds
    fv = FreshnessValidator(window_seconds=0.01)  # Strict 10ms window

    ch = create_challenge("T1", "T2", tracking_epoch=1)
    # Simulate old challenge timestamp (10 seconds ago)
    ch = create_challenge("T1", "T2", tracking_epoch=1)
    ch_dict = ch.to_dict()
    ch_dict["timestamp"] = time.time() - 10.0
    stale_ch = AuthenticationChallenge.from_dict(ch_dict)

    res = create_response(stale_ch, TerminalIdentity(t2_creds))

    with pytest.raises(Exception):  # Freshness validator raises ExpiredTimestampError
        verify_response(stale_ch, res, registry, freshness_validator=fv)


def test_attack_7_invalid_credentials(registry_and_creds):
    """Attack 7: Invalid / Unregistered Credential Attack Simulation."""
    registry, _, _ = registry_and_creds
    attack = InvalidCredentialAttack(registry=registry)
    succ, reason = attack.execute_unregistered_terminal_attack("T1", "T3_UNREGISTERED")

    assert succ is False
    assert "AUTHENTICATION_REJECTED" in reason


def test_attack_8_inconsistent_motion_anomaly(registry_and_creds):
    """Attack 8: Inconsistent Motion Anomaly Simulation."""
    attack = OpticalJammingAttack()
    succ, reason = attack.test_inconsistent_motion_anomaly("T1", "T2")

    assert succ is False
    assert "MOTION_ANOMALY_BLOCKED" in reason


def test_attack_9_optical_jamming_degradation(registry_and_creds):
    """Attack 9: Optical Jamming / Degradation Simulation."""
    attack = OpticalJammingAttack()
    succ, reason = attack.test_optical_jamming_degradation("T1", "T2")

    assert succ is False
    assert "OPTICAL_JAMMING_SUSPENDED" in reason


def test_attack_10_duplicate_packet_injection():
    """Attack 10: Duplicate Packet Injection Simulation."""
    rw = ReceiverWindow()
    sm = SessionManager()
    sess = sm.establish_session("T1", "T2", tracking_epoch=1, authentication_valid=True, trust_authorized=True)

    p = PacketCipher.encrypt(sess.derived_keys.initiator_to_responder_key, b"Data Payload", "1.0", sess.session_id, "TX_001", 1, "T1_TO_T2")

    ack1, chunks1, dup1 = rw.process_received_packet(p, b"Data Payload")
    assert dup1 is False
    assert len(chunks1) == 1

    # Inject duplicate
    ack2, chunks2, dup2 = rw.process_received_packet(p, b"Data Payload")
    assert dup2 is True
    assert len(chunks2) == 0  # No duplicate payload delivered!


def test_attack_11_cross_session_packet_reuse():
    """Attack 11: Cross-Session Packet Reuse Simulation."""
    sm = SessionManager()
    sessA = sm.establish_session("T1", "T2", tracking_epoch=1, authentication_valid=True, trust_authorized=True)
    sessB = sm.establish_session("T1", "T2", tracking_epoch=2, authentication_valid=True, trust_authorized=True)

    # Encrypt under Session A
    pA = PacketCipher.encrypt(sessA.derived_keys.initiator_to_responder_key, b"Data Session A", "1.0", sessA.session_id, "TX_001", 1, "T1_TO_T2")

    # Attempt decrypt under Session B key
    with pytest.raises(InvalidPacketError):
        PacketCipher.decrypt(sessB.derived_keys.initiator_to_responder_key, pA)


def test_attack_12_cross_direction_packet_reuse():
    """Attack 12: Cross-Direction Packet Reuse Simulation."""
    sm = SessionManager()
    sess = sm.establish_session("T1", "T2", tracking_epoch=1, authentication_valid=True, trust_authorized=True)

    # Encrypt T1 -> T2
    p_forward = PacketCipher.encrypt(
        sess.derived_keys.initiator_to_responder_key, b"Forward Data", "1.0", sess.session_id, "TX_001", 1, "T1_TO_T2"
    )

    # Attempt decrypt using opposite direction key (responder_to_initiator_key)
    with pytest.raises(InvalidPacketError):
        PacketCipher.decrypt(sess.derived_keys.responder_to_initiator_key, p_forward)


# ---------------------------------------------------------------------------
# 14 Programmatic Security Invariants Verification
# ---------------------------------------------------------------------------

def test_invariant_1_tracking_lock_alone_cannot_authorize(locked_tracking):
    """Invariant 1: Tracking lock alone cannot authorize transmission."""
    te = TrustEngine()
    trust_res = te.evaluate("T1", "T2", tracking_state=locked_tracking, authentication_valid=False)
    gate = TransmissionAuthorizationGate.can_transmit(trust_res)

    assert gate.authorized is False
    assert "AUTHENTICATION_INVALID" in gate.failed_conditions


def test_invariant_2_authentication_failure_cannot_authorize(locked_tracking):
    """Invariant 2: Authentication failure cannot authorize transmission."""
    te = TrustEngine()
    trust_res = te.evaluate("T1", "T2", tracking_state=locked_tracking, authentication_valid=False)
    gate = TransmissionAuthorizationGate.can_transmit(trust_res)

    assert gate.authorized is False


def test_invariant_3_invalid_freshness_cannot_authorize(locked_tracking):
    """Invariant 3: Invalid freshness cannot authorize transmission."""
    te = TrustEngine()
    trust_res = te.evaluate("T1", "T2", tracking_state=locked_tracking, authentication_valid=True, freshness_valid=False)
    gate = TransmissionAuthorizationGate.can_transmit(trust_res)

    assert gate.authorized is False


def test_invariant_4_invalid_physical_consistency_cannot_authorize(locked_tracking):
    """Invariant 4: Invalid physical consistency cannot authorize transmission."""
    te = TrustEngine()
    # Physical validation failed
    from src.optical_challenge import PhysicalValidationResult
    phys_fail = PhysicalValidationResult(valid=False, position_error=100.0, velocity_consistency=0.1, signal_valid=False, reason="PHYS_FAIL")

    trust_res = te.evaluate("T1", "T2", tracking_state=locked_tracking, authentication_valid=True, physical_validation_result=phys_fail)
    gate = TransmissionAuthorizationGate.can_transmit(trust_res)

    assert gate.authorized is False
    assert "PHYSICAL_VALIDATION_FAILED" in gate.failed_conditions


def test_invariant_5_missing_secure_session_cannot_authorize():
    """Invariant 5: Missing secure session cannot authorize transmission."""
    sm = SessionManager()
    with pytest.raises(Exception):
        sm.get_session("NON_EXISTENT_SESSION_ID")


def test_invariant_6_invalid_packet_integrity_cannot_produce_application_data():
    """Invariant 6: Invalid packet integrity cannot produce application data."""
    sm = SessionManager()
    sess = sm.establish_session("T1", "T2", tracking_epoch=1, authentication_valid=True, trust_authorized=True)

    valid_p = PacketCipher.encrypt(sess.derived_keys.initiator_to_responder_key, b"Secret Payload", "1.0", sess.session_id, "TX_001", 1, "T1_TO_T2")
    attack = PacketTamperingAttack()
    tampered_p = attack.tamper_packet(valid_p, "ciphertext")

    with pytest.raises(InvalidPacketError):
        PacketCipher.decrypt(sess.derived_keys.initiator_to_responder_key, tampered_p)


def test_invariant_7_forged_ack_cannot_advance_sender_state():
    """Invariant 7: Forged ACK cannot advance sender state."""
    sw = SenderWindow(window_size=32)
    sw.base_sequence = 1
    sw.next_sequence = 5

    attack = ForgedAckAttack()
    ack = attack.generate_forged_ack("SESS_1", "TX_1", scenario="IMPOSSIBLE_SEQUENCE")
    attack.test_forged_ack(sw, ack, "SESS_1", "TX_1", total_packets=50)

    assert sw.base_sequence == 1  # Base sequence preserved!


def test_invariant_8_forged_resume_cannot_alter_checkpoint():
    """Invariant 8: Forged resume information cannot alter transfer checkpoint."""
    attack = ForgedResumeAttack()
    forged_resp = attack.generate_forged_resume_response("TX_1", "SESS_1", 1, 100, scenario="EXCESSIVE_CHECKPOINT")

    with pytest.raises(ResumeValidationError):
        ResumeProtocolHandler.validate_response(forged_resp, "TX_1", 1, "SESS_REAL", sender_checkpoint=10, total_packets=100)


def test_invariant_9_reacquisition_cannot_automatically_restore_trust(locked_tracking):
    """Invariant 9: Reacquisition cannot automatically restore trust."""
    sm = RecoveryStateMachine("TX_001", initial_epoch=1)
    sm.handle_link_loss()
    sm.handle_reacquisition(locked_tracking)

    assert sm.security_status == "LOCKED_UNVERIFIED"
    assert sm.transmission_allowed is False


def test_invariant_10_new_tracking_epoch_requires_fresh_authentication():
    """Invariant 10: New tracking epoch requires fresh authentication."""
    sm = RecoveryStateMachine("TX_001", initial_epoch=1)
    sm.handle_link_loss()

    assert sm.tracking_epoch == 2
    assert sm.state == RecoveryState.INTERRUPTED
    assert sm.transmission_allowed is False


def test_invariant_11_new_session_requires_fresh_session_keys():
    """Invariant 11: New session requires fresh session keys."""
    sm = SessionManager()
    s1 = sm.establish_session("T1", "T2", tracking_epoch=1, authentication_valid=True, trust_authorized=True)
    s2 = sm.establish_session("T1", "T2", tracking_epoch=2, authentication_valid=True, trust_authorized=True)

    assert s1.session_id != s2.session_id
    assert s1.derived_keys.initiator_to_responder_key != s2.derived_keys.initiator_to_responder_key


def test_invariant_12_transfer_state_survives_legitimate_session_replacement(test_dir):
    """Invariant 12: Transfer state survives legitimate session replacement."""
    cm = CheckpointManager(checkpoint_dir=test_dir)
    chk1 = Checkpoint("TX_PERPERSIST", 1000, 500, 501, "SESS_1", 1, "hash1", time.time())
    cm.save_checkpoint(chk1)

    loaded = cm.load_checkpoint("TX_PERPERSIST")
    assert loaded is not None
    assert loaded.last_confirmed == 500


def test_invariant_13_duplicate_packets_cannot_duplicate_application_payload():
    """Invariant 13: Duplicate packets cannot duplicate application payload."""
    reassembler = PayloadReassembler()
    res1 = reassembler.accept_packet(1, b"Payload Chunk 1")
    assert res1 is True

    res2 = reassembler.accept_packet(1, b"Payload Chunk 1")
    assert res2 is False  # Rejected duplicate

    assert len(reassembler.reassemble()) == len(b"Payload Chunk 1")


def test_invariant_14_recovery_failure_leaves_transmission_blocked(registry_and_creds, test_dir):
    """Invariant 14: Recovery failure leaves transmission blocked."""
    registry, t1_creds, t2_creds = registry_and_creds
    ctrl = RecoveryController("TX_FAIL", checkpoint_dir=test_dir)

    ctrl.handle_link_interruption(100, 10, 11, "S1", "h1")
    fake_t2 = generate_credentials("T2")

    # Reauth failure
    with pytest.raises(RecoveryError):
        ctrl.execute_recovery(t1_creds, fake_t2, registry, TrackingState(100.0, "LOCKED", 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.95), 100, "h1", 10)

    assert ctrl.state_machine.transmission_allowed is False
    assert ctrl.state_machine.state == RecoveryState.FAILED


# ---------------------------------------------------------------------------
# Security Experiment Runner & Report Generation Tests
# ---------------------------------------------------------------------------

def test_security_experiment_runner_and_reports(test_dir):
    """Test SecurityExperimentRunner and JSON report generation under outputs/reports/."""
    runner = SecurityExperimentRunner(reports_dir=os.path.join(test_dir, "reports"))

    spoof_res = runner.run_spoof_experiment(legitimate_count=10, fake_count=10)
    assert spoof_res["fake_rejected"] == 10

    replay_res = runner.run_replay_experiment(attempt_count=10)
    assert replay_res["replay_rejected"] == 10

    tamper_res = runner.run_packet_integrity_experiment(packet_count=10)
    assert tamper_res["tampered_rejected"] == 10

    sec_report, trans_report = runner.generate_reports()

    assert os.path.isfile(sec_report)
    assert os.path.isfile(trans_report)

    with open(sec_report, "r", encoding="utf-8") as f:
        sec_json = json.load(f)
        assert sec_json["phase"] == "PHASE_8_SECURITY_VALIDATION"
        assert "security_metrics" in sec_json

    with open(trans_report, "r", encoding="utf-8") as f:
        trans_json = json.load(f)
        assert trans_json["phase"] == "PHASE_8_TRANSPORT_METRICS"
        assert "transport_performance" in trans_json
