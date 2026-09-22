"""Independent slew rate limiting for camera control."""

from typing import Tuple


class SlewLimiter:
    """Independent slew rate limiter for a single axis.
    
    Limits the rate of change of a single control channel (pan or tilt).
    """
    
    def __init__(self, max_rate_deg_per_sec: float):
        """Initialize slew limiter for a single axis.
        
        Args:
            max_rate_deg_per_sec: Maximum slew rate in degrees/second
        """
        self.max_rate = max_rate_deg_per_sec
        self.last_position: float = 0.0
        self.initialized = False
    
    def limit(self, desired_position: float, dt: float) -> Tuple[float, float]:
        """Limit position change based on slew rate constraint.
        
        Args:
            desired_position: Desired position (degrees)
            dt: Time step in seconds
            
        Returns:
            (limited_position, achieved_rate) where achieved_rate is in degrees/second
        """
        if dt <= 0:
            raise ValueError(f"dt must be positive, got {dt}")
        
        if not self.initialized:
            # First update, initialize to desired position
            self.last_position = desired_position
            self.initialized = True
            return desired_position, 0.0
        
        # Compute desired rate
        delta = desired_position - self.last_position
        desired_rate = delta / dt
        
        # Limit rate
        limited_rate = max(-self.max_rate, min(self.max_rate, desired_rate))
        
        # Apply limited rate
        limited_position = self.last_position + limited_rate * dt
        
        # Update state
        self.last_position = limited_position
        
        return limited_position, limited_rate
    
    def reset(self, initial_position: float = 0.0):
        """Reset slew limiter state.
        
        Args:
            initial_position: Initial position to set (default 0.0)
        """
        self.last_position = initial_position
        self.initialized = False


class SlewLimiterPair:
    """Independent slew rate limiters for pan and tilt axes.
    
    Maintains separate limiters for pan and tilt to allow different
    slew rate constraints for each axis.
    """
    
    def __init__(self, max_pan_speed_deg_per_sec: float, max_tilt_speed_deg_per_sec: float):
        """Initialize slew limiter pair.
        
        Args:
            max_pan_speed_deg_per_sec: Maximum pan slew rate in degrees/second
            max_tilt_speed_deg_per_sec: Maximum tilt slew rate in degrees/second
        """
        self.pan_limiter = SlewLimiter(max_pan_speed_deg_per_sec)
        self.tilt_limiter = SlewLimiter(max_tilt_speed_deg_per_sec)
    
    def limit(
        self,
        desired_pan: float,
        desired_tilt: float,
        dt: float
    ) -> Tuple[float, float, Tuple[float, float]]:
        """Limit pan and tilt based on independent slew rate constraints.
        
        Args:
            desired_pan: Desired pan angle (degrees)
            desired_tilt: Desired tilt angle (degrees)
            dt: Time step in seconds
            
        Returns:
            (limited_pan, limited_tilt, (pan_rate, tilt_rate))
        """
        limited_pan, pan_rate = self.pan_limiter.limit(desired_pan, dt)
        limited_tilt, tilt_rate = self.tilt_limiter.limit(desired_tilt, dt)
        
        return limited_pan, limited_tilt, (pan_rate, tilt_rate)
    
    def reset(self, initial_pan: float = 0.0, initial_tilt: float = 0.0):
        """Reset both slew limiters.
        
        Args:
            initial_pan: Initial pan position (default 0.0)
            initial_tilt: Initial tilt position (default 0.0)
        """
        self.pan_limiter.reset(initial_pan)
        self.tilt_limiter.reset(initial_tilt)
