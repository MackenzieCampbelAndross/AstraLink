"""Main reacquisition controller integrating all search strategies."""

from typing import Tuple, Optional
import numpy as np

from astra_link_tracking.reacquisition.predictor import TrajectoryPredictor
from astra_link_tracking.reacquisition.levy_search import LevySearch
from astra_link_tracking.reacquisition.raster_search import RasterSearch
from astra_link_tracking.models.config import ReacquisitionConfig, ControlConfig
from astra_link_tracking.models.interfaces import DetectionResult, TrackingMode
from astra_link_tracking.tracking.motion_consistency import MotionConsistencyChecker


class ReacquisitionController:
    """Main reacquisition controller for finding lost targets.
    
    Architecture:
    LOST → Kalman predicted position → prediction covariance → search region
    → local search → Lévy-style expansion → fallback raster/spiral
    → candidate detected → motion consistency gate → confirmation → LOCKED
    
    The search controller obeys camera pan/tilt speed constraints and
    does not allow search commands to teleport the camera.
    """
    
    def __init__(
        self,
        config: ReacquisitionConfig,
        control_config: ControlConfig,
        tracking_config,
        seed: Optional[int] = None
    ):
        """Initialize reacquisition controller.
        
        Args:
            config: Reacquisition configuration
            control_config: Control configuration with slew limits
            tracking_config: Tracking configuration for thresholds
            seed: Random seed for reproducibility
        """
        self.config = config
        self.control_config = control_config
        self.tracking_config = tracking_config
        self.seed = seed
        
        # Initialize components
        self.predictor = TrajectoryPredictor(config)
        self.levy_search = LevySearch(config, seed)
        self.raster_search = RasterSearch(config)
        self.motion_consistency = MotionConsistencyChecker(tracking_config)
        
        # Search state
        self.active = False
        self.search_start_time: Optional[float] = None
        self.current_search_position: Tuple[float, float] = (0.0, 0.0)
        self.search_mode = "local"  # local, levy, raster
        self.confirmation_count = 0
        self.reacquisition_time: Optional[float] = None
        
        # Kalman state at loss
        self.last_position: Optional[Tuple[float, float]] = None
        self.last_velocity: Optional[Tuple[float, float]] = None
        self.last_covariance: Optional[np.ndarray] = None
    
    def start(
        self,
        position: Tuple[float, float],
        velocity: Tuple[float, float],
        covariance: np.ndarray,
        timestamp: float
    ):
        """Start reacquisition search.
        
        Args:
            position: Last known position (theta_x, theta_y) in degrees
            velocity: Last known velocity (v_x, v_y) in degrees/second
            covariance: Position covariance matrix
            timestamp: Current timestamp in seconds
        """
        self.active = True
        self.search_start_time = timestamp
        self.confirmation_count = 0
        self.reacquisition_time = None
        
        # Store Kalman state
        self.last_position = position
        self.last_velocity = velocity
        self.last_covariance = covariance
        
        # Update predictor
        self.predictor.update_state(position, velocity, timestamp)
        
        # Start with local search at predicted position
        self.search_mode = "local"
        self.current_search_position = self.predictor.predict_position(0.5)
        
        # Reset search strategies
        self.levy_search.reset(self.current_search_position)
        self.raster_search.reset(self.current_search_position)
    
    def step(
        self,
        dt: float,
        camera_position: Tuple[float, float]
    ) -> Tuple[float, float]:
        """Execute one search step.
        
        Args:
            dt: Time step in seconds
            camera_position: Current camera position (pan, tilt) in degrees
            
        Returns:
            (target_pan, target_tilt) search target in degrees
        """
        if not self.active:
            return camera_position
        
        # Calculate search region based on prediction uncertainty
        if self.last_covariance is not None:
            search_region = self.predictor.get_search_region(self.last_covariance)
        else:
            # Default search region if no covariance
            search_region = ((-1.0, -1.0), (1.0, 1.0))
        
        # Get next search position based on mode
        if self.search_mode == "local":
            # Stay at predicted position initially
            target = self.current_search_position
            # Transition to Lévy after brief local search
            self.search_mode = "levy"
        elif self.search_mode == "levy":
            # Lévy-style expansion
            target = self.levy_search.get_next_position(self.current_search_position)
            # Clamp to search region
            target = self._clamp_to_region(target, search_region)
            # Check if we should transition to raster
            if self.levy_search.get_step_count() > 50:  # Arbitrary threshold
                self.search_mode = "raster"
                self.raster_search.reset(self.current_search_position)
        elif self.search_mode == "raster":
            # Deterministic raster fallback
            target = self.raster_search.get_next_position()
            # Clamp to search region
            target = self._clamp_to_region(target, search_region)
        
        self.current_search_position = target
        
        # Apply slew limiting to prevent teleporting
        target = self._apply_slew_limit(camera_position, target, dt)
        
        return target
    
    def process_detection(
        self,
        detection: DetectionResult,
        estimated_state: np.ndarray,
        estimated_covariance: np.ndarray,
        timestamp: float
    ) -> bool:
        """Process a detection during reacquisition.
        
        A valid reacquisition candidate must satisfy:
        - visible
        - confidence threshold
        - Mahalanobis/motion consistency gate
        - configurable confirmation frames
        
        Args:
            detection: Detection result
            estimated_state: Current Kalman state estimate
            estimated_covariance: Current Kalman covariance
            timestamp: Current timestamp
            
        Returns:
            True if reacquisition is confirmed (ready to return to LOCKED)
        """
        if not self.active:
            return False
        
        # Check visibility
        if not detection.visible:
            return False
        
        # Check confidence threshold
        if detection.confidence < self.tracking_config.confidence_threshold:
            return False
        
        # Check motion consistency gate
        if detection.centroid_x is None or detection.centroid_y is None:
            return False
        
        # Motion consistency check
        measurement_covariance = np.eye(2) * self.tracking_config.measurement_noise
        consistency_result = self.motion_consistency.check(
            (estimated_state[0], estimated_state[1]),
            estimated_state,
            estimated_covariance,
            measurement_covariance,
            detection.visible,
            detection.confidence
        )
        
        if not consistency_result.gate_passed:
            return False
        
        # Increment confirmation count
        self.confirmation_count += 1
        
        # Check if confirmation requirement met
        if self.confirmation_count >= self.tracking_config.confirmation_frames:
            self.reacquisition_time = timestamp - self.search_start_time
            return True
        
        return False
    
    def reset(self):
        """Reset reacquisition controller state."""
        self.active = False
        self.search_start_time = None
        self.current_search_position = (0.0, 0.0)
        self.search_mode = "local"
        self.confirmation_count = 0
        self.reacquisition_time = None
        self.last_position = None
        self.last_velocity = None
        self.last_covariance = None
        
        self.predictor.reset()
        self.levy_search.reset()
        self.raster_search.reset()
    
    def get_current_search_position(self) -> Tuple[float, float]:
        """Get current search position.
        
        Returns:
            Current search position (pan, tilt) in degrees
        """
        return self.current_search_position
    
    def is_complete(self) -> bool:
        """Check if reacquisition is complete.
        
        Returns:
            True if reacquisition is confirmed
        """
        return self.reacquisition_time is not None
    
    def is_active(self) -> bool:
        """Check if reacquisition is active.
        
        Returns:
            True if reacquisition is in progress
        """
        return self.active
    
    def get_reacquisition_time(self) -> Optional[float]:
        """Get time taken for reacquisition.
        
        Returns:
            Reacquisition time in seconds, or None if not complete
        """
        return self.reacquisition_time
    
    def _clamp_to_region(
        self,
        position: Tuple[float, float],
        region: Tuple[Tuple[float, float], Tuple[float, float]]
    ) -> Tuple[float, float]:
        """Clamp position to search region.
        
        Args:
            position: Position to clamp
            region: ((min_x, min_y), (max_x, max_y)) search region
            
        Returns:
            Clamped position
        """
        (min_x, min_y), (max_x, max_y) = region
        x = max(min_x, min(max_x, position[0]))
        y = max(min_y, min(max_y, position[1]))
        return (x, y)
    
    def _apply_slew_limit(
        self,
        current: Tuple[float, float],
        target: Tuple[float, float],
        dt: float
    ) -> Tuple[float, float]:
        """Apply slew limiting to prevent teleporting.
        
        Args:
            current: Current position (pan, tilt) in degrees
            target: Target position (pan, tilt) in degrees
            dt: Time step in seconds
            
        Returns:
            Slew-limited target position
        """
        max_pan_delta = self.control_config.max_pan_speed_deg_per_sec * dt
        max_tilt_delta = self.control_config.max_tilt_speed_deg_per_sec * dt
        
        pan_delta = target[0] - current[0]
        tilt_delta = target[1] - current[1]
        
        pan_delta_clamped = max(-max_pan_delta, min(max_pan_delta, pan_delta))
        tilt_delta_clamped = max(-max_tilt_delta, min(max_tilt_delta, tilt_delta))
        
        return (current[0] + pan_delta_clamped, current[1] + tilt_delta_clamped)