"""Velocity feedforward controller implementation."""

from typing import Tuple


class VelocityFeedforward:
    """Velocity feedforward controller based on estimated velocity.
    
    Provides predictive control based on the Kalman filter's velocity estimate
    to improve tracking performance for moving targets.
    """
    
    def __init__(self, gain: float = 0.5):
        """Initialize velocity feedforward controller.
        
        Args:
            gain: Feedforward gain (default 0.5)
        """
        self.gain = gain
    
    def compute(self, velocity_x: float, velocity_y: float) -> Tuple[float, float]:
        """Compute feedforward control from estimated velocity.
        
        Args:
            velocity_x: Estimated velocity in X (degrees/second)
            velocity_y: Estimated velocity in Y (degrees/second)
            
        Returns:
            (ff_x, ff_y) feedforward control output (degrees)
        """
        ff_x = self.gain * velocity_x
        ff_y = self.gain * velocity_y
        
        return (ff_x, ff_y)
    
    def set_gain(self, gain: float):
        """Set feedforward gain.
        
        Args:
            gain: New gain value
        """
        self.gain = gain
    
    def get_gain(self) -> float:
        """Get current feedforward gain.
        
        Returns:
            Current gain value
        """
        return self.gain
