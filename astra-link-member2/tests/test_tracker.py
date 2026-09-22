"""Unit and integration tests for Member 2 runtime Tracker component."""

import pytest
import numpy as np

from astra_link_tracking.models.config import TrackingSystemConfig
from astra_link_tracking.models.interfaces import DetectionResult, TrackingMode, TrackingState, CameraCommand
from astra_link_tracking.tracking.tracker import Tracker
from astra_link_integration.adapter import TrackingAdapter


def create_detection(
    frame_id: int = 1,
    centroid_x: float = 320.0,
    centroid_y: float = 240.0,
    confidence: float = 0.95,
    visible: bool = True,
    timestamp: float = 0.05
) -> DetectionResult:
    """Helper to create test DetectionResult objects."""
    return DetectionResult(
        timestamp=timestamp,
        frame_id=frame_id,
        centroid_x=centroid_x,
        centroid_y=centroid_y,
        confidence=confidence,
        visible=visible
    )


def test_tracker_initialization():
    """Verify Tracker initializes with default configuration cleanly."""
    tracker = Tracker()
    assert tracker.state_machine.get_mode() == TrackingMode.SEARCH
    assert tracker.current_time == 0.0
    assert tracker.frame_id == 0


def test_tracker_valid_detection_locked_transition():
    """Verify consecutive valid detections transition state machine from SEARCH to LOCKED."""
    tracker = Tracker()
    
    # Process confirmation_frames (default 3) valid detections
    states = []
    for i in range(1, 5):
        detection = create_detection(frame_id=i, timestamp=0.05 * i)
        state, cmd = tracker.update(detection)
        states.append(state)

    assert isinstance(states[-1], TrackingState)
    assert isinstance(cmd, CameraCommand)
    assert states[-1].state == TrackingMode.LOCKED
    assert states[-1].motion_consistency is True


def test_tracker_prediction_during_missing_detection_coasting():
    """Verify missing detection triggers LOCKED -> COASTING transition."""
    tracker = Tracker()
    
    # Establish LOCKED state
    for i in range(1, 4):
        tracker.update(create_detection(frame_id=i, timestamp=0.05 * i))
    
    assert tracker.state_machine.get_mode() == TrackingMode.LOCKED

    # Send None detection (missing frame)
    state, cmd = tracker.update(None, dt=0.05)

    assert state.state == TrackingMode.COASTING
    assert state.measurement_accepted is False


def test_tracker_extended_missing_detection_lost():
    """Verify extended missing frames trigger COASTING -> LOST transition."""
    tracker = Tracker()
    
    # Establish LOCKED state
    for i in range(1, 4):
        tracker.update(create_detection(frame_id=i, timestamp=0.05 * i))

    # Send missing frames until LOST
    last_state = None
    for i in range(1, 15):
        last_state, _ = tracker.update(None, dt=0.05)

    assert last_state.state == TrackingMode.LOST


def test_tracker_reacquisition_recovery():
    """Verify detection during LOST triggers reacquisition search and recovers LOCKED state."""
    tracker = Tracker()
    
    # Establish LOCKED state
    for i in range(1, 4):
        tracker.update(create_detection(frame_id=i, timestamp=0.05 * i))

    # Push into LOST state
    for _ in range(12):
        tracker.update(None, dt=0.05)
    
    assert tracker.state_machine.get_mode() == TrackingMode.LOST

    # Send valid detections during reacquisition
    recovered_state = None
    for i in range(1, 5):
        det = create_detection(frame_id=100 + i, centroid_x=320.0, centroid_y=240.0, timestamp=1.0 + 0.05 * i)
        recovered_state, _ = tracker.update(det)

    assert recovered_state.state == TrackingMode.LOCKED


def test_tracker_invalid_measurement_rejection():
    """Verify invalid / non-visible detections are rejected."""
    tracker = Tracker()
    
    invalid_det = create_detection(visible=False, confidence=0.0)
    state, cmd = tracker.update(invalid_det)

    assert state.measurement_accepted is False
    assert state.state == TrackingMode.SEARCH


def test_tracker_camera_command_and_tracking_state_generation():
    """Verify exact output data structure of TrackingState and CameraCommand."""
    tracker = Tracker()
    detection = create_detection(centroid_x=340.0, centroid_y=260.0, timestamp=0.1)
    
    state, cmd = tracker.update(detection)

    assert isinstance(state.timestamp, float)
    assert isinstance(state.predicted_x, float)
    assert isinstance(state.predicted_y, float)
    assert isinstance(state.angular_x, float)
    assert isinstance(state.angular_y, float)
    assert isinstance(state.velocity_x, float)
    assert isinstance(state.velocity_y, float)
    assert isinstance(cmd.pan_command, float)
    assert isinstance(cmd.tilt_command, float)


def test_tracker_member3_adapter_compatibility():
    """Verify that Tracker output maps cleanly into Member 3 TrackingAdapter."""
    tracker = Tracker()
    
    # Establish LOCKED state
    m2_state = None
    for i in range(1, 4):
        m2_state, _ = tracker.update(create_detection(frame_id=i, timestamp=0.05 * i))

    # Adapt into Member 3 TrackingState
    m3_state = TrackingAdapter.adapt(m2_state)

    assert m3_state.tracking_state == "LOCKED"
    assert m3_state.is_locked is True
    assert m3_state.motion_consistency > 0.80
    assert isinstance(m3_state.prediction_covariance, list)
