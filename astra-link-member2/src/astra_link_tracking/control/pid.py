"""PID controller implementation with anti-windup and variable dt support."""

from typing import Tuple, Optional


class PIDController:
    """Proportional-Integral-Derivative controller with anti-windup.
    
    Supports P-only, PI, and PID operation by setting gains to zero.
    Handles variable dt with protection against zero/invalid dt.
    Implements integral anti-windup to prevent saturation issues.
    """
    
    def __init__(
        self,
        kp: float,
        ki: float = 0.0,
        kd: float = 0.0,
        output_limits: Tuple[float, float] = (-float('inf'), float('inf'))
    ):
        """Initialize PID controller.
        
        Args:
            kp: Proportional gain
            ki: Integral gain (default 0.0 for P-only operation)
            kd: Derivative gain (default 0.0 for P/PI operation)
            output_limits: (min, max) output limits (default unlimited)
        """
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.output_limits = output_limits
        
        # State variables
        self.integral = 0.0
        self.last_error: Optional[float] = None
        self.last_output: Optional[float] = None
    
    def update(self, error: float, dt: float) -> float:
        """Update PID controller with new error.
        
        Args:
            error: Current error (setpoint - measured)
            dt: Time step in seconds
            
        Returns:
            Control output
            
        Raises:
            ValueError: If dt is zero or negative
        """
        # Validate dt
        if dt <= 0:
            raise ValueError(f"dt must be positive, got {dt}")
        
        # Proportional term
        p_term = self.kp * error
        
        # Integral term with anti-windup
        i_term = 0.0
        if self.ki != 0:
            # Tentative integral update
            tentative_integral = self.integral + error * dt
            tentative_i_term = self.ki * tentative_integral
            
            # Compute tentative output
            d_term = 0.0
            if self.kd != 0 and self.last_error is not None:
                d_term = self.kd * (error - self.last_error) / dt
            
            tentative_output = p_term + tentative_i_term + d_term
            
            # Anti-windup: only update integral if it wouldn't increase saturation
            min_limit, max_limit = self.output_limits
            if self.last_output is not None:
                # If output was saturated and error would increase saturation, don't update integral
                if self.last_output >= max_limit and error > 0:
                    # Saturated at max, positive error would increase saturation
                    pass
                elif self.last_output <= min_limit and error < 0:
                    # Saturated at min, negative error would increase saturation
                    pass
                else:
                    # Not saturated or error would reduce saturation, update integral
                    self.integral = tentative_integral
            else:
                # First update, no saturation history
                self.integral = tentative_integral
            
            i_term = self.ki * self.integral
        
        # Derivative term (using actual dt)
        d_term = 0.0
        if self.kd != 0 and self.last_error is not None:
            d_term = self.kd * (error - self.last_error) / dt
        
        # Compute output
        output = p_term + i_term + d_term
        
        # Apply output limits
        min_limit, max_limit = self.output_limits
        output = max(min_limit, min(max_limit, output))
        
        # Update state
        self.last_error = error
        self.last_output = output
        
        return output
    
    def reset(self):
        """Reset PID controller state."""
        self.integral = 0.0
        self.last_error = None
        self.last_output = None
    
    def get_integral(self) -> float:
        """Get current integral value.
        
        Returns:
            Current integral accumulation
        """
        return self.integral
