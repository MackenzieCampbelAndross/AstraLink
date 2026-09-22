"""Integration Tests: Member 2 Optical Tracking → TrackingAdapter → Member 3 Security Gate.

Proves:
1. LOCKED + valid motion state reaches Member 3 correctly and passes transmission authorization.
2. COASTING state is rejected for transmission.
3. LOST state is rejected for transmission.
4. Low motion consistency (motion_consistency=False) is degraded/rejected for transmission.
5. Malformed TrackingState (missing fields / bad types) raises explicit errors and fails safely.
6. Member 2 output fields map accurately to Member 3 security inputs without loss of fidelity.
7. Security rules cannot be bypassed by adapter manipulation.
"""

import pytest
import numpy as np
from dataclasses import dataclass
from typing import Optional, Dict, Any

from astra_link_tracking.models.interfaces import TrackingState as M2TrackingState, TrackingMode
from astra_link_integration.adapter import TrackingAdapter
from astra_link_integration.pipeline import IntegratedTrackingSecurityPipeline
from src.trust.security_state import SecurityState


def create_valid_m2_state(
    state: TrackingMode = TrackingMode.LOCKED,
    motion_consistency: bool = True,
    confidence: float = 0.95,
    prediction_uncertainty: float = 0.05,
    timestamp: float = 100.0,
) -> M2TrackingState:
    """Helper to construct a valid Member 2 TrackingState telemetry object."""
    return M2TrackingState(
        timestamp=timestamp,
        state=state,
        predicted_x=320.0,
        predicted_y=240.0,
        angular_x=0.015,
        angular_y=-0.008,
        velocity_x=1.2,
        velocity_y=-0.5,
        motion_consistency=motion_consistency,
        prediction_uncertainty=prediction_uncertainty,
        measurement_accepted=True,
        confidence=confidence,
        time_since_last_detection=0.01,
        position_covariance=np.array([[0.04, 0.0], [0.0, 0.04]]),
        tracking_id="TRACK_001",
    )


def test_locked_valid_motion_reaches_member3_and_authorizes():
    """Prove LOCKED state + valid motion passes adapter and reaches AUTHORIZED transmission state."""
    pipeline = IntegratedTrackingSecurityPipeline(min_motion_consistency=0.80)
    m2_state = create_valid_m2_state(state=TrackingMode.LOCKED, motion_consistency=True, confidence=0.95)

    m3_state, trust_result, decision = pipeline.process_telemetry(
        m2_tracking_state=m2_state,
        terminal_id="T1",
        remote_terminal_id="T2",
        authentication_valid=True,
        freshness_valid=True,
    )

    # Verify adapter field mapping
    assert m3_state.tracking_state == "LOCKED"
    assert m3_state.is_locked is True
    assert m3_state.motion_consistency == 0.95
    assert m3_state.predicted_x == 320.0
    assert m3_state.predicted_y == 240.0

    # Verify security evaluation
    assert trust_result.security_state == SecurityState.AUTHORIZED
    assert trust_result.trust_authorized is True
    assert decision.authorized is True
    assert decision.allowed is True
    assert decision.reason == "TRANSMISSION_PERMITTED"


def test_coasting_state_rejected_for_transmission():
    """Prove COASTING state is rejected by Member 3 transmission authorization gate."""
    pipeline = IntegratedTrackingSecurityPipeline()
    m2_state = create_valid_m2_state(state=TrackingMode.COASTING, motion_consistency=True, confidence=0.90)

    m3_state, trust_result, decision = pipeline.process_telemetry(
        m2_tracking_state=m2_state,
        terminal_id="T1",
        remote_terminal_id="T2",
        authentication_valid=True,
    )

    assert m3_state.tracking_state == "COASTING"
    assert m3_state.is_locked is False
    assert trust_result.security_state == SecurityState.BLOCKED
    assert trust_result.trust_authorized is False
    assert decision.authorized is False
    assert decision.allowed is False


def test_lost_state_rejected_for_transmission():
    """Prove LOST state is rejected for transmission."""
    pipeline = IntegratedTrackingSecurityPipeline()
    m2_state = create_valid_m2_state(state=TrackingMode.LOST, motion_consistency=False, confidence=0.0)

    m3_state, trust_result, decision = pipeline.process_telemetry(
        m2_tracking_state=m2_state,
        terminal_id="T1",
        remote_terminal_id="T2",
        authentication_valid=True,
    )

    assert m3_state.tracking_state == "LOST"
    assert m3_state.is_locked is False
    assert trust_result.security_state == SecurityState.BLOCKED
    assert decision.authorized is False
    assert decision.allowed is False


def test_low_motion_consistency_degrades_and_blocks():
    """Prove low motion consistency (motion_consistency=False in M2) degrades trust and blocks transmission."""
    pipeline = IntegratedTrackingSecurityPipeline(min_motion_consistency=0.80)
    m2_state = create_valid_m2_state(state=TrackingMode.LOCKED, motion_consistency=False, confidence=0.90)

    m3_state, trust_result, decision = pipeline.process_telemetry(
        m2_tracking_state=m2_state,
        terminal_id="T1",
        remote_terminal_id="T2",
        authentication_valid=True,
    )

    assert m3_state.tracking_state == "LOCKED"
    assert m3_state.motion_consistency == 0.0  # False mapped to 0.0
    assert trust_result.security_state == SecurityState.DEGRADED
    assert trust_result.motion_consistent is False
    assert decision.authorized is False
    assert decision.allowed is False
    assert "MOTION_CONSISTENCY_TOO_LOW" in trust_result.reason


def test_malformed_tracking_state_raises_and_blocks():
    """Prove malformed tracking state input is safely rejected with ValueError."""
    pipeline = IntegratedTrackingSecurityPipeline()

    # None state
    with pytest.raises(ValueError, match="TrackingState cannot be None"):
        pipeline.process_telemetry(None, "T1", "T2")

    # Incomplete object
    @dataclass
    class IncompleteState:
        timestamp: float = 1.0

    with pytest.raises(ValueError, match="missing attribute"):
        pipeline.process_telemetry(IncompleteState(), "T1", "T2")


def test_member2_to_member3_field_mapping_fidelity():
    """Verify exact numerical and structural fidelity when converting M2 state to M3 state."""
    m2_state = M2TrackingState(
        timestamp=123.456,
        state=TrackingMode.LOCKED,
        predicted_x=100.5,
        predicted_y=200.25,
        angular_x=0.012,
        angular_y=-0.034,
        velocity_x=5.5,
        velocity_y=-2.3,
        motion_consistency=True,
        prediction_uncertainty=0.15,
        measurement_accepted=True,
        confidence=0.88,
        time_since_last_detection=0.02,
        position_covariance=np.array([[0.25, 0.01], [0.01, 0.36]]),
    )

    m3_state = TrackingAdapter.adapt(m2_state)

    assert m3_state.timestamp == 123.456
    assert m3_state.tracking_state == "LOCKED"
    assert m3_state.predicted_x == 100.5
    assert m3_state.predicted_y == 200.25
    assert m3_state.angular_x == 0.012
    assert m3_state.angular_y == -0.034
    assert m3_state.velocity_x == 5.5
    assert m3_state.velocity_y == -2.3
    assert m3_state.motion_consistency == 0.88
    assert m3_state.prediction_covariance == [0.25, 0.36]


def test_security_rules_cannot_be_bypassed_by_adapter():
    """Prove cryptographic authentication failure blocks transmission even if tracking is valid."""
    pipeline = IntegratedTrackingSecurityPipeline()
    m2_state = create_valid_m2_state(state=TrackingMode.LOCKED, motion_consistency=True)

    # Valid tracking state, BUT authentication_valid = False
    m3_state, trust_result, decision = pipeline.process_telemetry(
        m2_tracking_state=m2_state,
        terminal_id="T1",
        remote_terminal_id="T2",
        authentication_valid=False,  # Unauthenticated
    )

    assert m3_state.is_locked is True
    assert trust_result.security_state == SecurityState.UNTRUSTED
    assert trust_result.authentication_valid is False
    assert decision.authorized is False
    assert decision.allowed is False
    assert decision.reason == "CRYPTOGRAPHIC_AUTHENTICATION_FAILED"
