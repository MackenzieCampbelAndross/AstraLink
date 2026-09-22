"""Comprehensive tests for tracking state machine."""

import pytest

from astra_link_tracking.tracking.state_machine import TrackingStateMachine, StateMachineDiagnostics
from astra_link_tracking.models.interfaces import TrackingMode
from astra_link_tracking.models.config import TrackingConfig


class TestTrackingStateMachine:
    """Test suite for tracking state machine."""
    
    @pytest.fixture
    def tracking_config(self):
        """Create tracking configuration."""
        return TrackingConfig(
            confidence_threshold=0.5,
            process_noise=0.1,
            measurement_noise=1.0,
            mahalanobis_threshold=9.21,
            confirmation_frames=3,
            maximum_missed_frames=5,
            maximum_covariance_threshold=100.0
        )
    
    @pytest.fixture
    def state_machine(self, tracking_config):
        """Create state machine instance."""
        return TrackingStateMachine(tracking_config)
    
    def test_initialization(self, state_machine):
        """Test state machine initialization."""
        assert state_machine.get_mode() == TrackingMode.SEARCH
        assert state_machine.consecutive_valid_frames == 0
        assert state_machine.missed_frames == 0
        assert state_machine.last_detection_time == 0.0
        assert state_machine.lock_start_time is None
        assert state_machine.loss_start_time is None
    
    def test_get_mode(self, state_machine):
        """Test getting current mode."""
        mode = state_machine.get_mode()
        assert isinstance(mode, TrackingMode)
        assert mode == TrackingMode.SEARCH
    
    def test_reset(self, state_machine):
        """Test resetting state machine."""
        # Advance state
        for i in range(3):
            diagnostics = state_machine.update(
                timestamp=float(i),
                detection_visible=True,
                detection_valid=True,
                confidence=0.9,
                gate_passed=True,
                prediction_uncertainty=1.0
            )
        
        # Reset
        state_machine.reset()
        
        # Verify reset state
        assert state_machine.get_mode() == TrackingMode.SEARCH
        assert state_machine.consecutive_valid_frames == 0
        assert state_machine.missed_frames == 0
        assert state_machine.last_detection_time == 0.0
        assert state_machine.lock_start_time is None
        assert state_machine.loss_start_time is None
    
    def test_search_to_search_invalid_candidate(self, state_machine):
        """Test SEARCH -> SEARCH transition with invalid candidate."""
        # Invalid measurement
        diagnostics = state_machine.update(
            timestamp=1.0,
            detection_visible=False,
            detection_valid=False,
            confidence=0.0,
            gate_passed=False,
            prediction_uncertainty=1.0
        )
        
        # Should stay in SEARCH
        assert state_machine.get_mode() == TrackingMode.SEARCH
        assert diagnostics.consecutive_valid_frames == 0
        assert diagnostics.missed_frames == 1
    
    def test_search_to_locked_after_confirmation(self, state_machine):
        """Test SEARCH -> LOCKED transition after confirmation frames."""
        # Provide confirmation_frames consecutive valid measurements
        for i in range(3):
            diagnostics = state_machine.update(
                timestamp=float(i),
                detection_visible=True,
                detection_valid=True,
                confidence=0.9,
                gate_passed=True,
                prediction_uncertainty=1.0
            )
        
        # Should transition to LOCKED
        assert state_machine.get_mode() == TrackingMode.LOCKED
        assert diagnostics.consecutive_valid_frames == 3
        assert diagnostics.missed_frames == 0
        assert state_machine.lock_start_time == 2.0
    
    def test_search_to_locked_requires_confirmation(self, state_machine):
        """Test that SEARCH -> LOCKED requires full confirmation count."""
        # Provide fewer than confirmation_frames
        for i in range(2):
            state_machine.update(
                timestamp=float(i),
                detection_visible=True,
                detection_valid=True,
                confidence=0.9,
                gate_passed=True,
                prediction_uncertainty=1.0
            )
        
        # Should still be in SEARCH
        assert state_machine.get_mode() == TrackingMode.SEARCH
        assert state_machine.consecutive_valid_frames == 2
    
    def test_locked_to_coasting_missing_detection(self, state_machine):
        """Test LOCKED -> COASTING transition when detection missing."""
        # First acquire lock
        for i in range(3):
            state_machine.update(
                timestamp=float(i),
                detection_visible=True,
                detection_valid=True,
                confidence=0.9,
                gate_passed=True,
                prediction_uncertainty=1.0
            )
        
        # Missing detection
        diagnostics = state_machine.update(
            timestamp=3.0,
            detection_visible=False,
            detection_valid=False,
            confidence=0.0,
            gate_passed=False,
            prediction_uncertainty=1.0
        )
        
        # Should transition to COASTING
        assert state_machine.get_mode() == TrackingMode.COASTING
        assert diagnostics.missed_frames == 1
        assert state_machine.lock_start_time == 2.0  # Lock time preserved
    
    def test_locked_to_coasting_low_confidence(self, state_machine):
        """Test LOCKED -> COASTING transition with low confidence."""
        # First acquire lock
        for i in range(3):
            state_machine.update(
                timestamp=float(i),
                detection_visible=True,
                detection_valid=True,
                confidence=0.9,
                gate_passed=True,
                prediction_uncertainty=1.0
            )
        
        # Low confidence detection (but still valid)
        diagnostics = state_machine.update(
            timestamp=3.0,
            detection_visible=True,
            detection_valid=True,
            confidence=0.9,
            gate_passed=False,  # Gate fails
            prediction_uncertainty=1.0
        )
        
        # Should transition to COASTING
        assert state_machine.get_mode() == TrackingMode.COASTING
    
    def test_locked_stays_locked_with_valid_measurement(self, state_machine):
        """Test LOCKED -> LOCKED with valid measurement."""
        # First acquire lock
        for i in range(3):
            state_machine.update(
                timestamp=float(i),
                detection_visible=True,
                detection_valid=True,
                confidence=0.9,
                gate_passed=True,
                prediction_uncertainty=1.0
            )
        
        # Continue with valid measurement
        diagnostics = state_machine.update(
            timestamp=3.0,
            detection_visible=True,
            detection_valid=True,
            confidence=0.9,
            gate_passed=True,
            prediction_uncertainty=1.0
        )
        
        # Should stay LOCKED
        assert state_machine.get_mode() == TrackingMode.LOCKED
        assert diagnostics.consecutive_valid_frames == 4
    
    def test_coasting_to_locked_with_valid_measurement(self, state_machine):
        """Test COASTING -> LOCKED when valid measurement returns (with confirmation)."""
        # Acquire lock
        for i in range(3):
            state_machine.update(
                timestamp=float(i),
                detection_visible=True,
                detection_valid=True,
                confidence=0.9,
                gate_passed=True,
                prediction_uncertainty=1.0
            )
        
        # Go to COASTING
        state_machine.update(
            timestamp=3.0,
            detection_visible=False,
            detection_valid=False,
            confidence=0.0,
            gate_passed=False,
            prediction_uncertainty=1.0
        )
        
        # Valid measurement returns - need confirmation
        for i in range(3):
            diagnostics = state_machine.update(
                timestamp=4.0 + float(i),
                detection_visible=True,
                detection_valid=True,
                confidence=0.9,
                gate_passed=True,
                prediction_uncertainty=1.0
            )
        
        # Should transition back to LOCKED after confirmation
        assert state_machine.get_mode() == TrackingMode.LOCKED
        assert diagnostics.consecutive_valid_frames == 3
    
    def test_coasting_to_lost_missed_frames_timeout(self, state_machine):
        """Test COASTING -> LOST when missed frames exceed maximum."""
        # Acquire lock
        for i in range(3):
            state_machine.update(
                timestamp=float(i),
                detection_visible=True,
                detection_valid=True,
                confidence=0.9,
                gate_passed=True,
                prediction_uncertainty=1.0
            )
        
        # Go to COASTING (1 missed frame)
        state_machine.update(
            timestamp=3.0,
            detection_visible=False,
            detection_valid=False,
            confidence=0.0,
            gate_passed=False,
            prediction_uncertainty=1.0
        )
        
        # Add 4 more missed frames to reach total of 5 (maximum)
        for i in range(4):
            diagnostics = state_machine.update(
                timestamp=4.0 + float(i),
                detection_visible=False,
                detection_valid=False,
                confidence=0.0,
                gate_passed=False,
                prediction_uncertainty=1.0
            )
        
        # Should transition to LOST when missed_frames >= maximum_missed_frames (5)
        assert state_machine.get_mode() == TrackingMode.LOST
        assert diagnostics.missed_frames == 5
        assert state_machine.loss_start_time == 7.0
    
    def test_coasting_to_lost_uncertainty_threshold(self, state_machine):
        """Test COASTING -> LOST when prediction uncertainty exceeds threshold."""
        # Acquire lock
        for i in range(3):
            state_machine.update(
                timestamp=float(i),
                detection_visible=True,
                detection_valid=True,
                confidence=0.9,
                gate_passed=True,
                prediction_uncertainty=1.0
            )
        
        # Go to COASTING
        state_machine.update(
            timestamp=3.0,
            detection_visible=False,
            detection_valid=False,
            confidence=0.0,
            gate_passed=False,
            prediction_uncertainty=1.0
        )
        
        # High uncertainty
        diagnostics = state_machine.update(
            timestamp=4.0,
            detection_visible=False,
            detection_valid=False,
            confidence=0.0,
            gate_passed=False,
            prediction_uncertainty=200.0  # Exceeds threshold of 100
        )
        
        # Should transition to LOST
        assert state_machine.get_mode() == TrackingMode.LOST
        assert state_machine.loss_start_time == 4.0
    
    def test_coasting_stays_coasting_within_limits(self, state_machine):
        """Test COASTING -> COASTING within limits."""
        # Acquire lock
        for i in range(3):
            state_machine.update(
                timestamp=float(i),
                detection_visible=True,
                detection_valid=True,
                confidence=0.9,
                gate_passed=True,
                prediction_uncertainty=1.0
            )
        
        # Go to COASTING (1 missed frame)
        state_machine.update(
            timestamp=3.0,
            detection_visible=False,
            detection_valid=False,
            confidence=0.0,
            gate_passed=False,
            prediction_uncertainty=1.0
        )
        
        # Stay within limits (3 more missed frames to stay at 4 total < 5 maximum)
        for i in range(3):
            diagnostics = state_machine.update(
                timestamp=4.0 + float(i),
                detection_visible=False,
                detection_valid=False,
                confidence=0.0,
                gate_passed=False,
                prediction_uncertainty=50.0  # Below threshold
            )
        
        # Should stay in COASTING (4 missed frames < 5 maximum)
        assert state_machine.get_mode() == TrackingMode.COASTING
        assert diagnostics.missed_frames == 4
    
    def test_lost_to_locked_after_confirmation(self, state_machine):
        """Test LOST -> LOCKED after valid reacquisition and confirmation."""
        # Acquire lock
        for i in range(3):
            state_machine.update(
                timestamp=float(i),
                detection_visible=True,
                detection_valid=True,
                confidence=0.9,
                gate_passed=True,
                prediction_uncertainty=1.0
            )
        
        # Go to LOST (need 5 missed frames in COASTING)
        state_machine.update(
            timestamp=3.0,
            detection_visible=False,
            detection_valid=False,
            confidence=0.0,
            gate_passed=False,
            prediction_uncertainty=1.0
        )
        for i in range(5):
            state_machine.update(
                timestamp=4.0 + float(i),
                detection_visible=False,
                detection_valid=False,
                confidence=0.0,
                gate_passed=False,
                prediction_uncertainty=1.0
            )
        
        # Confirm LOST state
        assert state_machine.get_mode() == TrackingMode.LOST
        
        # Valid measurement returns, need confirmation
        for i in range(3):
            diagnostics = state_machine.update(
                timestamp=9.0 + float(i),
                detection_visible=True,
                detection_valid=True,
                confidence=0.9,
                gate_passed=True,
                prediction_uncertainty=1.0
            )
        
        # Should transition to LOCKED
        assert state_machine.get_mode() == TrackingMode.LOCKED
        assert diagnostics.consecutive_valid_frames == 3
        assert state_machine.lock_start_time == 11.0
    
    def test_lost_stays_lost_on_invalid(self, state_machine):
        """Test LOST -> LOST when reacquisition fails (stays in LOST)."""
        # Acquire lock
        for i in range(3):
            state_machine.update(
                timestamp=float(i),
                detection_visible=True,
                detection_valid=True,
                confidence=0.9,
                gate_passed=True,
                prediction_uncertainty=1.0
            )
        
        # Go to LOST
        state_machine.update(
            timestamp=3.0,
            detection_visible=False,
            detection_valid=False,
            confidence=0.0,
            gate_passed=False,
            prediction_uncertainty=1.0
        )
        for i in range(5):
            state_machine.update(
                timestamp=4.0 + float(i),
                detection_visible=False,
                detection_valid=False,
                confidence=0.0,
                gate_passed=False,
                prediction_uncertainty=1.0
            )
        
        # Still invalid, should stay in LOST
        diagnostics = state_machine.update(
            timestamp=9.0,
            detection_visible=False,
            detection_valid=False,
            confidence=0.0,
            gate_passed=False,
            prediction_uncertainty=1.0
        )
        
        # Should stay in LOST
        assert state_machine.get_mode() == TrackingMode.LOST
        assert state_machine.loss_start_time is not None
    
    def test_lost_requires_confirmation_for_lock(self, state_machine):
        """Test that LOST -> LOCKED requires full confirmation count."""
        # Acquire lock then lose
        for i in range(3):
            state_machine.update(
                timestamp=float(i),
                detection_visible=True,
                detection_valid=True,
                confidence=0.9,
                gate_passed=True,
                prediction_uncertainty=1.0
            )
        
        # Go to LOST
        state_machine.update(
            timestamp=3.0,
            detection_visible=False,
            detection_valid=False,
            confidence=0.0,
            gate_passed=False,
            prediction_uncertainty=1.0
        )
        for i in range(5):
            state_machine.update(
                timestamp=4.0 + float(i),
                detection_visible=False,
                detection_valid=False,
                confidence=0.0,
                gate_passed=False,
                prediction_uncertainty=1.0
            )
        
        # One valid measurement (not enough for confirmation)
        state_machine.update(
            timestamp=9.0,
            detection_visible=True,
            detection_valid=True,
            confidence=0.9,
            gate_passed=True,
            prediction_uncertainty=1.0
        )
        
        # Should still be in LOST
        assert state_machine.get_mode() == TrackingMode.LOST
        assert state_machine.consecutive_valid_frames == 1
    
    def test_diagnostics_structure(self, state_machine):
        """Test that diagnostics are properly structured."""
        diagnostics = state_machine.update(
            timestamp=1.0,
            detection_visible=True,
            detection_valid=True,
            confidence=0.9,
            gate_passed=True,
            prediction_uncertainty=1.0
        )
        
        # Check all fields
        assert isinstance(diagnostics, StateMachineDiagnostics)
        assert hasattr(diagnostics, 'consecutive_valid_frames')
        assert hasattr(diagnostics, 'missed_frames')
        assert hasattr(diagnostics, 'time_since_last_detection')
        assert hasattr(diagnostics, 'lock_start_time')
        assert hasattr(diagnostics, 'loss_start_time')
        assert hasattr(diagnostics, 'current_state_duration')
    
    def test_edge_case_exactly_n_frames_missing(self, state_machine):
        """Test detection disappears for exactly N frames (boundary)."""
        # Acquire lock
        for i in range(3):
            state_machine.update(
                timestamp=float(i),
                detection_visible=True,
                detection_valid=True,
                confidence=0.9,
                gate_passed=True,
                prediction_uncertainty=1.0
            )
        
        # Exactly maximum_missed_frames (5) - first one enters COASTING, then 4 more
        state_machine.update(
            timestamp=3.0,
            detection_visible=False,
            detection_valid=False,
            confidence=0.0,
            gate_passed=False,
            prediction_uncertainty=1.0
        )
        for i in range(4):
            diagnostics = state_machine.update(
                timestamp=4.0 + float(i),
                detection_visible=False,
                detection_valid=False,
                confidence=0.0,
                gate_passed=False,
                prediction_uncertainty=1.0
            )
        
        # Should transition to LOST on the 5th missed frame
        assert state_machine.get_mode() == TrackingMode.LOST
        assert diagnostics.missed_frames == 5
    
    def test_edge_case_return_after_timeout(self, state_machine):
        """Test detection returns after being LOST."""
        # Acquire lock
        for i in range(3):
            state_machine.update(
                timestamp=float(i),
                detection_visible=True,
                detection_valid=True,
                confidence=0.9,
                gate_passed=True,
                prediction_uncertainty=1.0
            )
        
        # Go to LOST
        state_machine.update(
            timestamp=3.0,
            detection_visible=False,
            detection_valid=False,
            confidence=0.0,
            gate_passed=False,
            prediction_uncertainty=1.0
        )
        for i in range(5):
            state_machine.update(
                timestamp=4.0 + float(i),
                detection_visible=False,
                detection_valid=False,
                confidence=0.0,
                gate_passed=False,
                prediction_uncertainty=1.0
            )
        
        # Detection returns from LOST
        for i in range(3):
            diagnostics = state_machine.update(
                timestamp=9.0 + float(i),
                detection_visible=True,
                detection_valid=True,
                confidence=0.9,
                gate_passed=True,
                prediction_uncertainty=1.0
            )
        
        # Should lock again after confirmation
        assert state_machine.get_mode() == TrackingMode.LOCKED
    
    def test_edge_case_outlier_while_locked(self, state_machine):
        """Test outlier occurs while LOCKED (hysteresis)."""
        # Acquire lock
        for i in range(3):
            state_machine.update(
                timestamp=float(i),
                detection_visible=True,
                detection_valid=True,
                confidence=0.9,
                gate_passed=True,
                prediction_uncertainty=1.0
            )
        
        # Outlier (gate fails)
        diagnostics = state_machine.update(
            timestamp=3.0,
            detection_visible=True,
            detection_valid=True,
            confidence=0.9,
            gate_passed=False,  # Outlier
            prediction_uncertainty=1.0
        )
        
        # Should go to COASTING, not directly to LOST (hysteresis)
        assert state_machine.get_mode() == TrackingMode.COASTING
        assert diagnostics.missed_frames == 1
    
    def test_edge_case_low_confidence_sequence(self, state_machine):
        """Test sequence of low confidence measurements."""
        # Acquire lock
        for i in range(3):
            state_machine.update(
                timestamp=float(i),
                detection_visible=True,
                detection_valid=True,
                confidence=0.9,
                gate_passed=True,
                prediction_uncertainty=1.0
            )
        
        # Low confidence sequence - first goes to COASTING, then need 4 more to reach 5 total
        for i in range(5):
            diagnostics = state_machine.update(
                timestamp=3.0 + float(i),
                detection_visible=True,
                detection_valid=True,
                confidence=0.9,
                gate_passed=False,  # Gate fails
                prediction_uncertainty=1.0
            )
        
        # Should be in COASTING after first, then transition to LOST after 5 total missed
        assert state_machine.get_mode() == TrackingMode.LOST
        assert diagnostics.missed_frames == 5
    
    def test_edge_case_repeated_invalid_measurements(self, state_machine):
        """Test repeated invalid measurements in SEARCH."""
        # Many invalid measurements
        for i in range(10):
            diagnostics = state_machine.update(
                timestamp=float(i),
                detection_visible=False,
                detection_valid=False,
                confidence=0.0,
                gate_passed=False,
                prediction_uncertainty=1.0
            )
        
        # Should stay in SEARCH
        assert state_machine.get_mode() == TrackingMode.SEARCH
        assert diagnostics.consecutive_valid_frames == 0
        assert diagnostics.missed_frames == 10
    
    def test_hysteresis_prevents_oscillation(self, state_machine):
        """Test that hysteresis prevents rapid oscillation."""
        # Acquire lock
        for i in range(3):
            state_machine.update(
                timestamp=float(i),
                detection_visible=True,
                detection_valid=True,
                confidence=0.9,
                gate_passed=True,
                prediction_uncertainty=1.0
            )
        
        # Oscillating pattern: valid, invalid, valid, invalid
        states = []
        for i in range(10):
            visible = (i % 2 == 0)
            diagnostics = state_machine.update(
                timestamp=3.0 + float(i),
                detection_visible=visible,
                detection_valid=visible,
                confidence=0.9 if visible else 0.0,
                gate_passed=visible,
                prediction_uncertainty=1.0
            )
            states.append(state_machine.get_mode())
        
        # Should not oscillate rapidly between LOCKED and COASTING
        # With confirmation requirement, should stay in COASTING after first invalid
        # Count transitions
        transitions = sum(1 for i in range(1, len(states)) if states[i] != states[i-1])
        # Should have: LOCKED -> COASTING (1 transition), then stay in COASTING
        # With confirmation, won't rapidly oscillate back to LOCKED
        assert transitions <= 2  # Should not oscillate on every frame
    
    def test_time_since_last_detection(self, state_machine):
        """Test time_since_last_detection tracking."""
        # First detection
        state_machine.update(
            timestamp=1.0,
            detection_visible=True,
            detection_valid=True,
            confidence=0.9,
            gate_passed=True,
            prediction_uncertainty=1.0
        )
        
        # Wait
        diagnostics = state_machine.update(
            timestamp=3.0,
            detection_visible=False,
            detection_valid=False,
            confidence=0.0,
            gate_passed=False,
            prediction_uncertainty=1.0
        )
        
        # Should track time correctly
        assert diagnostics.time_since_last_detection == 2.0
    
    def test_current_state_duration(self, state_machine):
        """Test current_state_duration tracking."""
        # Acquire lock
        for i in range(3):
            state_machine.update(
                timestamp=float(i),
                detection_visible=True,
                detection_valid=True,
                confidence=0.9,
                gate_passed=True,
                prediction_uncertainty=1.0
            )
        
        # Wait
        diagnostics = state_machine.update(
            timestamp=5.0,
            detection_visible=True,
            detection_valid=True,
            confidence=0.9,
            gate_passed=True,
            prediction_uncertainty=1.0
        )
        
        # Should track duration correctly
        assert diagnostics.current_state_duration == 3.0  # Entered at 2.0, now at 5.0
    
    def test_gate_fail_prevents_acceptance(self, state_machine):
        """Test that gate failure prevents measurement acceptance."""
        # Try to acquire with gate failure
        for i in range(5):
            diagnostics = state_machine.update(
                timestamp=float(i),
                detection_visible=True,
                detection_valid=True,
                confidence=0.9,
                gate_passed=False,  # Gate fails
                prediction_uncertainty=1.0
            )
        
        # Should not lock
        assert state_machine.get_mode() == TrackingMode.SEARCH
        assert diagnostics.consecutive_valid_frames == 0
    
    def test_invisible_prevents_acceptance(self, state_machine):
        """Test that invisible detection prevents acceptance."""
        # Try to acquire with invisible detection
        for i in range(5):
            diagnostics = state_machine.update(
                timestamp=float(i),
                detection_visible=False,  # Invisible
                detection_valid=True,
                confidence=0.9,
                gate_passed=True,
                prediction_uncertainty=1.0
            )
        
        # Should not lock
        assert state_machine.get_mode() == TrackingMode.SEARCH
        assert diagnostics.consecutive_valid_frames == 0
    
    def test_custom_confirmation_frames(self, tracking_config):
        """Test with custom confirmation_frames."""
        tracking_config.confirmation_frames = 5
        state_machine = TrackingStateMachine(tracking_config)
        
        # Provide 4 valid measurements (not enough)
        for i in range(4):
            state_machine.update(
                timestamp=float(i),
                detection_visible=True,
                detection_valid=True,
                confidence=0.9,
                gate_passed=True,
                prediction_uncertainty=1.0
            )
        
        # Should still be in SEARCH
        assert state_machine.get_mode() == TrackingMode.SEARCH
        
        # One more (enough)
        state_machine.update(
            timestamp=4.0,
            detection_visible=True,
            detection_valid=True,
            confidence=0.9,
            gate_passed=True,
            prediction_uncertainty=1.0
        )
        
        # Should lock
        assert state_machine.get_mode() == TrackingMode.LOCKED
    
    def test_custom_max_missed_frames(self, tracking_config):
        """Test with custom maximum_missed_frames."""
        tracking_config.maximum_missed_frames = 10
        state_machine = TrackingStateMachine(tracking_config)
        
        # Acquire lock
        for i in range(3):
            state_machine.update(
                timestamp=float(i),
                detection_visible=True,
                detection_valid=True,
                confidence=0.9,
                gate_passed=True,
                prediction_uncertainty=1.0
            )
        
        # Go to COASTING (1 missed)
        state_machine.update(
            timestamp=3.0,
            detection_visible=False,
            detection_valid=False,
            confidence=0.0,
            gate_passed=False,
            prediction_uncertainty=1.0
        )
        
        # Miss 8 more frames (9 total, within limit of 10)
        for i in range(8):
            state_machine.update(
                timestamp=4.0 + float(i),
                detection_visible=False,
                detection_valid=False,
                confidence=0.0,
                gate_passed=False,
                prediction_uncertainty=1.0
            )
        
        # Should still be in COASTING
        assert state_machine.get_mode() == TrackingMode.COASTING
        
        # One more (exceeds limit - 10 total)
        state_machine.update(
            timestamp=12.0,
            detection_visible=False,
            detection_valid=False,
            confidence=0.0,
            gate_passed=False,
            prediction_uncertainty=1.0
        )
        
        # Should transition to LOST
        assert state_machine.get_mode() == TrackingMode.LOST