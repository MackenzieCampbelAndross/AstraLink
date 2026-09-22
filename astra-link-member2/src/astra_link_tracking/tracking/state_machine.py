"""State machine for tracking modes.

Implements deterministic state transitions with hysteresis to prevent
rapid oscillation between states. The state machine is independent from
security/authentication to allow Member 3 to extend with security states.
"""

from dataclasses import dataclass
from typing import Optional

from astra_link_tracking.models.interfaces import TrackingMode
from astra_link_tracking.models.config import TrackingConfig


@dataclass
class StateMachineDiagnostics:
    """Diagnostics from state machine for monitoring and debugging."""
    consecutive_valid_frames: int  # Current count of consecutive valid frames
    missed_frames: int  # Current count of missed frames
    time_since_last_detection: float  # Time since last valid detection (seconds)
    lock_start_time: Optional[float]  # Timestamp when entered LOCKED state
    loss_start_time: Optional[float]  # Timestamp when entered LOST state
    current_state_duration: float  # Time spent in current state (seconds)


class TrackingStateMachine:
    """State machine for tracking mode transitions.
    
    Implements hysteresis to prevent rapid oscillation between states.
    Designed to be extensible for future security states without rewriting
    Kalman or control code.
    
    States:
    - SEARCH: Actively searching for beacon
    - LOCKED: Beacon locked and tracking with high confidence
    - COASTING: Predicting without recent detections (temporary gap)
    - LOST: Beacon lost, reacquisition needed
    
    Transitions:
    - SEARCH -> LOCKED: After configurable consecutive valid observations
    - SEARCH -> SEARCH: If candidate is invalid
    - LOCKED -> COASTING: When detection is temporarily missing or low confidence
    - COASTING -> LOCKED: When valid consistent measurement returns
    - COASTING -> LOST: When missing duration exceeds timeout OR uncertainty too large
    - LOST -> LOCKED: After valid reacquisition and confirmation
    - LOST -> SEARCH: If appropriate for architecture
    """
    
    def __init__(self, tracking_config: TrackingConfig):
        """Initialize state machine with configuration.
        
        Args:
            tracking_config: Tracking configuration with state machine parameters
        """
        self.confirmation_frames = tracking_config.confirmation_frames
        self.maximum_missed_frames = tracking_config.maximum_missed_frames
        self.maximum_covariance_threshold = tracking_config.maximum_covariance_threshold
        
        # State tracking
        self.current_mode = TrackingMode.SEARCH
        self.consecutive_valid_frames = 0
        self.missed_frames = 0
        self.last_detection_time = 0.0
        self.lock_start_time: Optional[float] = None
        self.loss_start_time: Optional[float] = None
        self.state_entry_time = 0.0
        self.last_timestamp = 0.0
    
    def update(
        self,
        timestamp: float,
        detection_visible: bool,
        detection_valid: bool,
        confidence: float,
        gate_passed: bool,
        prediction_uncertainty: float
    ) -> StateMachineDiagnostics:
        """Update state machine based on detection and filter status.
        
        Args:
            timestamp: Current timestamp (seconds)
            detection_visible: Whether detection is visible
            detection_valid: Whether detection is valid (not None, finite values)
            confidence: Detection confidence [0, 1]
            gate_passed: Whether Mahalanobis gate passed
            prediction_uncertainty: Current prediction uncertainty (variance)
            
        Returns:
            StateMachineDiagnostics with current state information
        """
        # Update time tracking
        dt = timestamp - self.last_timestamp if self.last_timestamp > 0 else 0.0
        self.last_timestamp = timestamp
        
        # Determine if measurement is acceptable for state transitions
        measurement_accepted = self._is_measurement_acceptable(
            detection_visible, detection_valid, confidence, gate_passed
        )
        
        # Update counters
        if measurement_accepted:
            self.consecutive_valid_frames += 1
            self.missed_frames = 0
            self.last_detection_time = timestamp
        else:
            self.consecutive_valid_frames = 0
            self.missed_frames += 1
        
        # State transition logic
        old_mode = self.current_mode
        self._transit_state(timestamp, measurement_accepted, prediction_uncertainty)
        
        # Update state entry time if state changed
        if self.current_mode != old_mode:
            self.state_entry_time = timestamp
            self._on_state_entry(self.current_mode, timestamp)
        
        # Return diagnostics
        return self._get_diagnostics(timestamp)
    
    def _is_measurement_acceptable(
        self,
        detection_visible: bool,
        detection_valid: bool,
        confidence: float,
        gate_passed: bool
    ) -> bool:
        """Determine if measurement is acceptable for state transitions.
        
        Args:
            detection_visible: Whether detection is visible
            detection_valid: Whether detection is valid
            confidence: Detection confidence
            gate_passed: Whether Mahalanobis gate passed
            
        Returns:
            True if measurement is acceptable
        """
        # Must be visible, valid, and pass gate
        if not detection_visible or not detection_valid:
            return False
        
        if not gate_passed:
            return False
        
        return True
    
    def _transit_state(
        self,
        timestamp: float,
        measurement_accepted: bool,
        prediction_uncertainty: float
    ):
        """Execute state transition logic.
        
        Args:
            timestamp: Current timestamp
            measurement_accepted: Whether measurement was accepted
            prediction_uncertainty: Current prediction uncertainty
        """
        time_since_last_detection = timestamp - self.last_detection_time if self.last_detection_time > 0 else float('inf')
        
        if self.current_mode == TrackingMode.SEARCH:
            self._transit_from_search(measurement_accepted)
        
        elif self.current_mode == TrackingMode.LOCKED:
            self._transit_from_locked(measurement_accepted, time_since_last_detection)
        
        elif self.current_mode == TrackingMode.COASTING:
            self._transit_from_coasting(
                measurement_accepted,
                time_since_last_detection,
                prediction_uncertainty
            )
        
        elif self.current_mode == TrackingMode.LOST:
            self._transit_from_lost(measurement_accepted, time_since_last_detection)
    
    def _transit_from_search(self, measurement_accepted: bool):
        """Transition logic from SEARCH state.
        
        SEARCH -> LOCKED: After confirmation_frames consecutive valid observations
        SEARCH -> SEARCH: If candidate is invalid
        """
        if measurement_accepted:
            if self.consecutive_valid_frames >= self.confirmation_frames:
                self.current_mode = TrackingMode.LOCKED
            # Otherwise stay in SEARCH
        else:
            # Invalid measurement, stay in SEARCH
            self.consecutive_valid_frames = 0
    
    def _transit_from_locked(self, measurement_accepted: bool, time_since_last_detection: float):
        """Transition logic from LOCKED state.
        
        LOCKED -> COASTING: When detection is temporarily missing or low confidence
        LOCKED -> LOCKED: Continue tracking with valid measurements
        """
        if measurement_accepted:
            # Valid measurement, stay LOCKED
            pass
        else:
            # Missing or invalid measurement, transition to COASTING
            self.current_mode = TrackingMode.COASTING
    
    def _transit_from_coasting(
        self,
        measurement_accepted: bool,
        time_since_last_detection: float,
        prediction_uncertainty: float
    ):
        """Transition logic from COASTING state.
        
        COASTING -> LOCKED: When valid consistent measurement returns (requires confirmation)
        COASTING -> LOST: When missing duration exceeds timeout OR uncertainty too large
        """
        if measurement_accepted:
            # Valid measurement returned - require confirmation to prevent oscillation
            if self.consecutive_valid_frames >= self.confirmation_frames:
                # Confirmed return to LOCKED
                self.current_mode = TrackingMode.LOCKED
            # Otherwise stay in COASTING (hysteresis)
        else:
            # Still missing
            # Check if exceeded maximum missed frames
            if self.missed_frames >= self.maximum_missed_frames:
                self.current_mode = TrackingMode.LOST
            # Check if prediction uncertainty is too large
            elif prediction_uncertainty > self.maximum_covariance_threshold:
                self.current_mode = TrackingMode.LOST
            # Otherwise stay in COASTING
    
    def _transit_from_lost(self, measurement_accepted: bool, time_since_last_detection: float):
        """Transition logic from LOST state.
        
        LOST -> LOCKED: After valid reacquisition and confirmation
        LOST -> SEARCH: If appropriate for architecture (currently stays in LOST)
        """
        if measurement_accepted:
            # Valid measurement returned
            if self.consecutive_valid_frames >= self.confirmation_frames:
                # Confirmed reacquisition
                self.current_mode = TrackingMode.LOCKED
            # Otherwise need more confirmations, stay in LOST
        else:
            # Still lost, stay in LOST to wait for reacquisition
            # Don't immediately go to SEARCH - wait for external decision or timeout
            pass
    
    def _on_state_entry(self, new_mode: TrackingMode, timestamp: float):
        """Handle state entry events.
        
        Args:
            new_mode: New state being entered
            timestamp: Current timestamp
        """
        if new_mode == TrackingMode.LOCKED:
            self.lock_start_time = timestamp
            self.loss_start_time = None
        elif new_mode == TrackingMode.LOST:
            self.loss_start_time = timestamp
        elif new_mode == TrackingMode.SEARCH:
            self.lock_start_time = None
        elif new_mode == TrackingMode.COASTING:
            # Keep lock_start_time (we still have lock, just coasting)
            pass
    
    def _get_diagnostics(self, timestamp: float) -> StateMachineDiagnostics:
        """Get current state machine diagnostics.
        
        Args:
            timestamp: Current timestamp
            
        Returns:
            StateMachineDiagnostics with current state information
        """
        time_since_last_detection = timestamp - self.last_detection_time if self.last_detection_time > 0 else float('inf')
        current_state_duration = timestamp - self.state_entry_time if self.state_entry_time > 0 else 0.0
        
        return StateMachineDiagnostics(
            consecutive_valid_frames=self.consecutive_valid_frames,
            missed_frames=self.missed_frames,
            time_since_last_detection=time_since_last_detection,
            lock_start_time=self.lock_start_time,
            loss_start_time=self.loss_start_time,
            current_state_duration=current_state_duration
        )
    
    def get_mode(self) -> TrackingMode:
        """Get current tracking mode.
        
        Returns:
            Current TrackingMode
        """
        return self.current_mode
    
    def reset(self):
        """Reset state machine to initial state (SEARCH)."""
        self.current_mode = TrackingMode.SEARCH
        self.consecutive_valid_frames = 0
        self.missed_frames = 0
        self.last_detection_time = 0.0
        self.lock_start_time = None
        self.loss_start_time = None
        self.state_entry_time = 0.0
        self.last_timestamp = 0.0
