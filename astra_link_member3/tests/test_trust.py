"""Unit tests for Phase 3: Trust, Optical Challenge, and Transmission Authorization."""

import time
import pytest

from src.identity import TerminalIdentity, TerminalRegistry
from src.authentication import authenticate_mutually, create_challenge, create_response
from src.tracking import TrackingState, TrackingValidityEvaluator
from src.optical_challenge import (
    OpticalChallenge,
    OpticalResponse,
    OpticalResponseSimulator,
    PhysicalConsistencyValidator,
    PhysicalValidationResult,
    ProbeGenerator,
)
from src.trust import (
    SecurityLogger,
    SecurityState,
    TransmissionAuthorizationGate,
    TrustEngine,
    TrustEvaluationResult,
)


@pytest.fixture
def sample_tracking_locked() -> TrackingState:
    return TrackingState(
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


@pytest.fixture
def sample_tracking_lost() -> TrackingState:
    return TrackingState(
        timestamp=10.0,
        tracking_state="LOST",
        predicted_x=320.0,
        predicted_y=240.0,
        angular_x=0.10,
        angular_y=-0.02,
        velocity_x=0.0,
        velocity_y=0.0,
        motion_consistency=0.0,
        prediction_covariance=[0.1, 0.1],
    )


# 1. LOCKED tracking state accepted for evaluation
def test_locked_tracking_state_accepted(sample_tracking_locked: TrackingState):
    evaluator = TrackingValidityEvaluator(min_motion_consistency=0.80)
    valid, reason = evaluator.evaluate(sample_tracking_locked)
    assert valid is True
    assert reason == "TRACKING_VALID_LOCKED"


# 2. LOST tracking state rejected for transmission
def test_lost_tracking_state_rejected(sample_tracking_lost: TrackingState):
    evaluator = TrackingValidityEvaluator(min_motion_consistency=0.80)
    valid, reason = evaluator.evaluate(sample_tracking_lost)
    assert valid is False
    assert "TARGET_NOT_LOCKED" in reason

    trust_engine = TrustEngine()
    result = trust_engine.evaluate(
        terminal_id="T1",
        remote_terminal_id="T2",
        tracking_state=sample_tracking_lost,
        authentication_valid=True,
    )
    assert result.trust_authorized is False
    assert result.security_state == SecurityState.BLOCKED

    auth_gate = TransmissionAuthorizationGate.can_transmit(result)
    assert auth_gate.allowed is False


# 3. Fresh optical challenge generated
def test_fresh_optical_challenge_generated(sample_tracking_locked: TrackingState):
    gen = ProbeGenerator(probe_count=4, probe_offset_angle=0.02)
    ch1 = gen.generate_challenge("session_abc", 1, sample_tracking_locked)
    ch2 = gen.generate_challenge("session_abc", 1, sample_tracking_locked)

    assert ch1.challenge_id != ch2.challenge_id  # Fresh IDs
    assert ch1.session_id == "session_abc"
    assert ch1.tracking_epoch == 1


# 4. Probe sequence generated correctly
def test_probe_sequence_generated_correctly(sample_tracking_locked: TrackingState):
    gen = ProbeGenerator(probe_count=4, probe_offset_angle=0.02)
    ch = gen.generate_challenge("session_abc", 1, sample_tracking_locked)
    assert len(ch.probes) == 4
    
    p1 = ch.probes[0]
    assert pytest.approx(p1.expected_angular_x, 0.001) == sample_tracking_locked.angular_x + 0.02
    assert pytest.approx(p1.expected_angular_y, 0.001) == sample_tracking_locked.angular_y


# 5. Legitimate optical response accepted
def test_legitimate_optical_response_accepted(sample_tracking_locked: TrackingState):
    gen = ProbeGenerator()
    sim = OpticalResponseSimulator()
    val = PhysicalConsistencyValidator()

    ch = gen.generate_challenge("session_abc", 1, sample_tracking_locked)
    resps = sim.simulate_legitimate_response(ch, sample_tracking_locked)
    res = val.validate(ch, resps, sample_tracking_locked)

    assert res.valid is True
    assert res.reason == "PHYSICAL_VALIDATION_SUCCESS"


# 6. Inconsistent optical response rejected
def test_inconsistent_optical_response_rejected(sample_tracking_locked: TrackingState):
    gen = ProbeGenerator()
    sim = OpticalResponseSimulator()
    val = PhysicalConsistencyValidator()

    ch = gen.generate_challenge("session_abc", 1, sample_tracking_locked)
    resps = sim.simulate_inconsistent_response(ch, sample_tracking_locked)
    res = val.validate(ch, resps, sample_tracking_locked)

    assert res.valid is False
    assert "POSITION_ERROR_EXCEEDS_UNCERTAINTY" in res.reason


# 7. Optical response outside uncertainty rejected
def test_optical_response_outside_uncertainty_rejected():
    gen = ProbeGenerator()
    sim = OpticalResponseSimulator()
    val = PhysicalConsistencyValidator(uncertainty_sigma_threshold=1.0)  # Tight threshold

    tight_tracking = TrackingState(
        timestamp=10.0,
        tracking_state="LOCKED",
        predicted_x=320.0,
        predicted_y=240.0,
        angular_x=0.10,
        angular_y=-0.02,
        velocity_x=0.50,
        velocity_y=-0.10,
        motion_consistency=0.95,
        prediction_covariance=[0.001, 0.001],  # Tight covariance
    )

    ch = gen.generate_challenge("session_abc", 1, tight_tracking)
    resps = sim.simulate_legitimate_response(ch, tight_tracking, noise_std=0.20)
    res = val.validate(ch, resps, tight_tracking)

    assert res.valid is False


# 8. Authentication failure blocks authorization
def test_authentication_failure_blocks_authorization(sample_tracking_locked: TrackingState):
    trust_engine = TrustEngine()
    result = trust_engine.evaluate(
        terminal_id="T1",
        remote_terminal_id="T2",
        tracking_state=sample_tracking_locked,
        authentication_valid=False,  # AUTH FAILED
    )

    assert result.trust_authorized is False
    assert result.security_state == SecurityState.UNTRUSTED

    gate_res = TransmissionAuthorizationGate.can_transmit(result)
    assert gate_res.allowed is False
    assert "AUTHENTICATION_INVALID" in gate_res.failed_conditions


# 9. Valid authentication plus valid tracking allows authorization
def test_valid_auth_and_tracking_allows_authorization(sample_tracking_locked: TrackingState):
    gen = ProbeGenerator()
    sim = OpticalResponseSimulator()
    val = PhysicalConsistencyValidator()

    ch = gen.generate_challenge("session_abc", 1, sample_tracking_locked)
    resps = sim.simulate_legitimate_response(ch, sample_tracking_locked)
    phys_res = val.validate(ch, resps, sample_tracking_locked)

    trust_engine = TrustEngine()
    result = trust_engine.evaluate(
        terminal_id="T1",
        remote_terminal_id="T2",
        tracking_state=sample_tracking_locked,
        authentication_valid=True,
        freshness_valid=True,
        physical_validation_result=phys_res,
    )

    assert result.trust_authorized is True
    assert result.security_state == SecurityState.AUTHORIZED

    gate_res = TransmissionAuthorizationGate.can_transmit(result)
    assert gate_res.allowed is True


# 10. Low motion consistency causes degradation
def test_low_motion_consistency_causes_degradation():
    degraded_tracking = TrackingState(
        timestamp=10.0,
        tracking_state="LOCKED",
        predicted_x=320.0,
        predicted_y=240.0,
        angular_x=0.10,
        angular_y=-0.02,
        velocity_x=0.50,
        velocity_y=-0.10,
        motion_consistency=0.60,  # Below 0.80
        prediction_covariance=[0.1, 0.1],
    )
    trust_engine = TrustEngine(min_motion_consistency=0.80)
    result = trust_engine.evaluate(
        terminal_id="T1",
        remote_terminal_id="T2",
        tracking_state=degraded_tracking,
        authentication_valid=True,
    )

    assert result.trust_authorized is False
    assert result.security_state == SecurityState.DEGRADED

    gate_res = TransmissionAuthorizationGate.can_transmit(result)
    assert gate_res.allowed is False
    assert "MOTION_INCONSISTENT" in gate_res.failed_conditions


# 11. Invalid freshness blocks authorization
def test_invalid_freshness_blocks_authorization(sample_tracking_locked: TrackingState):
    trust_engine = TrustEngine()
    result = trust_engine.evaluate(
        terminal_id="T1",
        remote_terminal_id="T2",
        tracking_state=sample_tracking_locked,
        authentication_valid=True,
        freshness_valid=False,  # Freshness failed
    )

    assert result.trust_authorized is False
    assert result.security_state == SecurityState.UNTRUSTED

    gate_res = TransmissionAuthorizationGate.can_transmit(result)
    assert gate_res.allowed is False
    assert "FRESHNESS_INVALID" in gate_res.failed_conditions


# 12. Fake beacon fails authorization
def test_fake_beacon_fails_authorization(sample_tracking_locked: TrackingState):
    gen = ProbeGenerator()
    sim = OpticalResponseSimulator()
    val = PhysicalConsistencyValidator()

    ch = gen.generate_challenge("session_abc", 1, sample_tracking_locked)
    fake_resps = sim.simulate_fake_response(ch)
    phys_res = val.validate(ch, fake_resps, sample_tracking_locked)

    assert phys_res.valid is False

    trust_engine = TrustEngine()
    result = trust_engine.evaluate(
        terminal_id="T1",
        remote_terminal_id="T2",
        tracking_state=sample_tracking_locked,
        authentication_valid=True,
        physical_validation_result=phys_res,
    )

    assert result.trust_authorized is False
    assert result.security_state == SecurityState.DEGRADED

    gate_res = TransmissionAuthorizationGate.can_transmit(result)
    assert gate_res.allowed is False


# 13. Optical challenge ID mismatch rejected
def test_optical_challenge_id_mismatch_rejected(sample_tracking_locked: TrackingState):
    gen = ProbeGenerator()
    sim = OpticalResponseSimulator()
    val = PhysicalConsistencyValidator()

    ch = gen.generate_challenge("session_abc", 1, sample_tracking_locked)
    resps = sim.simulate_legitimate_response(ch, sample_tracking_locked)

    mismatched_resps = [
        OpticalResponse(
            challenge_id="WRONG_ID",
            probe_id=r.probe_id,
            angular_response_x=r.angular_response_x,
            angular_response_y=r.angular_response_y,
            received_signal=r.received_signal,
            timestamp=r.timestamp,
            signal_quality=r.signal_quality,
        )
        for r in resps
    ]

    res = val.validate(ch, mismatched_resps, sample_tracking_locked)
    assert res.valid is False
    assert res.reason == "CHALLENGE_ID_MISMATCH"


# 14. Optical response from wrong challenge rejected
def test_wrong_challenge_response_rejected(sample_tracking_locked: TrackingState):
    gen = ProbeGenerator()
    sim = OpticalResponseSimulator()
    val = PhysicalConsistencyValidator()

    ch1 = gen.generate_challenge("session_1", 1, sample_tracking_locked)
    ch2 = gen.generate_challenge("session_2", 1, sample_tracking_locked)

    resps2 = sim.simulate_legitimate_response(ch2, sample_tracking_locked)
    res = val.validate(ch1, resps2, sample_tracking_locked)

    assert res.valid is False
    assert res.reason == "CHALLENGE_ID_MISMATCH"


# 15. Stale optical response rejected
def test_stale_optical_response_rejected(sample_tracking_locked: TrackingState):
    gen = ProbeGenerator()
    val = PhysicalConsistencyValidator()

    ch = gen.generate_challenge("session_abc", 1, sample_tracking_locked)
    stale_timestamp = ch.creation_timestamp + 2.0  # 2 seconds later (> 0.500s timeout)

    stale_resps = [
        OpticalResponse(
            challenge_id=ch.challenge_id,
            probe_id=p.probe_id,
            angular_response_x=p.expected_angular_x,
            angular_response_y=p.expected_angular_y,
            received_signal=0.90,
            timestamp=stale_timestamp,
            signal_quality=0.95,
        )
        for p in ch.probes
    ]

    res = val.validate(ch, stale_resps, sample_tracking_locked, timeout_seconds=0.500)
    assert res.valid is False
    assert res.reason == "OPTICAL_CHALLENGE_TIMEOUT"


# 16. Trust state transitions work
def test_trust_state_transitions():
    logger = SecurityLogger()
    engine = TrustEngine()

    state = TrackingState(1.0, "LOCKED", 0, 0, 0, 0, 0, 0, 0.95)
    r1 = engine.evaluate("T1", "T2", state, authentication_valid=False, logger=logger)
    assert r1.security_state == SecurityState.UNTRUSTED

    r2 = engine.evaluate("T1", "T2", state, authentication_valid=True, logger=logger)
    assert r2.security_state == SecurityState.AUTHORIZED

    events = [e.event_type for e in logger.get_events()]
    assert "TRACKING_LOCKED" in events
    assert "TRUST_AUTHORIZED" in events


# 17. Transmission gate cannot be bypassed
def test_transmission_gate_cannot_be_bypassed(sample_tracking_locked: TrackingState):
    engine = TrustEngine()
    unauthorized_trust = engine.evaluate(
        terminal_id="T1",
        remote_terminal_id="T2",
        tracking_state=sample_tracking_locked,
        authentication_valid=False,
    )
    assert unauthorized_trust.trust_authorized is False

    # Ensure TransmissionAuthorizationGate rejects transmission
    gate_res = TransmissionAuthorizationGate.can_transmit(unauthorized_trust)
    assert gate_res.allowed is False
    assert gate_res.authorized is False
