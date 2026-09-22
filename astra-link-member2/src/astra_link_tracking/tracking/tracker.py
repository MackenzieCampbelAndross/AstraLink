"""Main tracker integrating coordinate transforms, Kalman filter, motion consistency, and state machine."""

from typing import Optional, Tuple
import numpy as np
import uuid

from astra_link_tracking.models.interfaces import (
    DetectionResult,
    CameraCommand,
    TrackingState,
)
from astra_link_tracking.tracking.coordinate_transform import CoordinateTransform
from astra_link_tracking.tracking.kalman import KalmanFilter
from astra_link_tracking.tracking.motion_consistency import MotionConsistencyChecker
from astra_link_tracking.tracking.state_machine import TrackingStateMachine


class Tracker:
    """Main tracker that integrates all tracking components."""
    
    def __init__(self, config: dict):
        """Initialize tracker with configuration.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
        
        # Initialize components
        coord_config = config.get("tracking", {}).get("coordinate_transform", {})
        self.coord_transform = CoordinateTransform(coord_config)
        
        kalman_config = config.get("tracking", {}).get("kalman", {})
        self.kalman = KalmanFilter(kalman_config)
        
        motion_config = config.get("tracking", {}).get("motion_consistency", {})
        self.motion_checker = MotionConsistencyChecker(motion_config)
        
        state_config = config.get("tracking", {}).get("state_machine", {})
        self.state_machine = TrackingStateMachine(state_config)
        
        # Generate unique tracking ID
        self.tracking_id = str(uuid.uuid4())
        
        # Last command timestamp
        self.last_command_time = 0.0
    
    def update(self, detection: Optional[DetectionResult]) -> Tuple[TrackingState, CameraCommand]:
        """Update tracker with new detection.
        
        Args:
            detection: Detection result from Member 1, or None if no detection
            
        Returns:
            (tracking_state, camera_command) tuple
        """
        # TODO: Implement full tracking pipeline
        # This is a stub that will be replaced with proper implementation
        
        if detection is None:
            # No detection - handle lost track
            tracking_state = self._create_tracking_state(None, None, detection)
            camera_command = self._create_camera_command(None, None)
            return tracking_state, camera_command
        
        # Transform pixel coordinates to world coordinates
        world_position = self.coord_transform.pixel_to_world(detection.centroid)
        
        # Check motion consistency
        is_consistent = self.motion_checker.check(
            world_position, 
            (0.0, 0.0),  # TODO: Get velocity from Kalman filter
            detection.timestamp
        )
        
        # Update Kalman filter
        self.kalman.update(world_position)
        
        # Get state estimates
        position_estimate = self.kalman.get_position()
        velocity_estimate = self.kalman.get_velocity()
        position_covariance = self.kalman.get_position_covariance()
        
        # Update state machine
        self.state_machine.update(detection.timestamp, is_consistent)
        
        # Create tracking state
        tracking_state = self._create_tracking_state(
            position_estimate,
            velocity_estimate,
            detection,
            position_covariance
        )
        
        # Create camera command
        camera_command = self._create_camera_command(
            position_estimate,
            velocity_estimate
        )
        
        return tracking_state, camera_command
    
    def _create_tracking_state(
        self,
        position_estimate: Optional[Tuple[float, float]],
        velocity_estimate: Optional[Tuple[float, float]],
        detection: Optional[DetectionResult],
        position_covariance: Optional[np.ndarray] = None
    ) -> TrackingState:
        """Create tracking state from current estimates.
        
        Args:
            position_estimate: Position estimate
            velocity_estimate: Velocity estimate
            detection: Detection result
            position_covariance: Position covariance matrix
            
        Returns:
            TrackingState object
        """
        timestamp = detection.timestamp if detection else 0.0
        
        if position_estimate is None:
            position_estimate = (0.0, 0.0)
        if velocity_estimate is None:
            velocity_estimate = (0.0, 0.0)
        if position_covariance is None:
            position_covariance = np.eye(2) * 10.0
        
        return TrackingState(
            timestamp=timestamp,
            mode=self.state_machine.get_mode(),
            position_estimate=position_estimate,
            velocity_estimate=velocity_estimate,
            position_covariance=position_covariance,
            confidence=0.5,  # TODO: Compute from covariance
            last_detection_time=timestamp,
            tracking_id=self.tracking_id
        )
    
    def _create_camera_command(
        self,
        position_estimate: Optional[Tuple[float, float]],
        velocity_estimate: Optional[Tuple[float, float]]
    ) -> CameraCommand:
        """Create camera command from current estimates.
        
        Args:
            position_estimate: Position estimate
            velocity_estimate: Velocity estimate
            
        Returns:
            CameraCommand object
        """
        if position_estimate is None:
            position_estimate = (0.0, 0.0)
        
        # Convert to angles
        azimuth, elevation = self.coord_transform.world_to_angles(position_estimate)
        
        return CameraCommand(
            timestamp=0.0,  # TODO: Use current time
            azimuth=azimuth,
            elevation=elevation,
            mode=self.state_machine.get_mode()
        )
    
    def reset(self):
        """Reset tracker to initial state."""
        self.kalman.reset((0.0, 0.0))
        self.motion_checker.reset()
        self.state_machine.reset()
        self.tracking_id = str(uuid.uuid4())
