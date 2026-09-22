"""Trajectory prediction for reacquisition."""

from typing import Tuple, Optional
import numpy as np

from astra_link_tracking.models.config import ReacquisitionConfig


class TrajectoryPredictor:
    """Predicts future beacon positions for reacquisition using Kalman state.
    
    Uses the last Kalman state and covariance to predict where the target
    is likely to be after loss. Search region size scales with prediction
    uncertainty.
    """
    
    def __init__(self, config: ReacquisitionConfig):
        """Initialize trajectory predictor with configuration.
        
        Args:
            config: Reacquisition configuration
        """
        self.config = config
        self.last_position: Optional[Tuple[float, float]] = None
        self.last_velocity: Optional[Tuple[float, float]] = None
        self.last_timestamp: Optional[float] = None
    
    def update_state(
        self,
        position: Tuple[float, float],
        velocity: Tuple[float, float],
        timestamp: float
    ):
        """Update predictor with latest Kalman state.
        
        Args:
            position: Current position (theta_x, theta_y) in degrees
            velocity: Current velocity (v_x, v_y) in degrees/second
            timestamp: Current timestamp in seconds
        """
        self.last_position = position
        self.last_velocity = velocity
        self.last_timestamp = timestamp
    
    def predict_position(
        self,
        time_ahead: float
    ) -> Tuple[float, float]:
        """Predict position at future time using constant velocity model.
        
        Args:
            time_ahead: Time to predict forward in seconds
            
        Returns:
            (predicted_x, predicted_y) in degrees
        """
        if self.last_position is None or self.last_velocity is None:
            return (0.0, 0.0)
        
        # Constant velocity prediction
        pred_x = self.last_position[0] + self.last_velocity[0] * time_ahead
        pred_y = self.last_position[1] + self.last_velocity[1] * time_ahead
        
        return (pred_x, pred_y)
    
    def get_search_region(
        self,
        position_covariance: np.ndarray,
        prediction_time: float = 0.5
    ) -> Tuple[Tuple[float, float], Tuple[float, float]]:
        """Get search region bounds based on prediction and uncertainty.
        
        Search region size increases with prediction uncertainty.
        Does not immediately search the entire camera range.
        
        Args:
            position_covariance: 2x2 position covariance matrix from Kalman
            prediction_time: Time to predict forward (default 0.5s)
            
        Returns:
            ((min_x, min_y), (max_x, max_y)) search region bounds in degrees
        """
        # Predict position
        pred_pos = self.predict_position(prediction_time)
        
        # Extract position uncertainty from covariance
        # Use 3-sigma region (99.7% confidence for Gaussian)
        std_x = np.sqrt(position_covariance[0, 0]) * 3.0
        std_y = np.sqrt(position_covariance[1, 1]) * 3.0
        
        # Apply minimum search radius (don't search too small)
        min_radius = self.config.initial_search_radius
        std_x = max(std_x, min_radius)
        std_y = max(std_y, min_radius)
        
        # Apply maximum search radius (don't search entire camera range immediately)
        max_radius = self.config.maximum_search_radius
        std_x = min(std_x, max_radius)
        std_y = min(std_y, max_radius)
        
        # Calculate bounds
        min_x = pred_pos[0] - std_x
        max_x = pred_pos[0] + std_x
        min_y = pred_pos[1] - std_y
        max_y = pred_pos[1] + std_y
        
        return ((min_x, min_y), (max_x, max_y))
    
    def reset(self):
        """Reset predictor state."""
        self.last_position = None
        self.last_velocity = None
        self.last_timestamp = None
