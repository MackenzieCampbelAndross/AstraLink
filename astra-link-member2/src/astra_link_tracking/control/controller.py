"""Main controller integrating PID, feedforward, and slew limiting."""

from dataclasses import dataclass
from typing import Tuple, Optional

from astra_link_tracking.control.pid import PIDController
from astra_link_tracking.control.feedforward import VelocityFeedforward
from astra_link_tracking.control.slew_limit import SlewLimiterPair
from astra_link_tracking.models.interfaces import TrackingMode, CameraCommand
from astra_link_tracking.models.config import ControlConfig


@dataclass
class ControlDiagnostics:
    """Diagnostics from control pipeline."""
    error_x: float  # Angular error X (degrees)
    error_y: float  # Angular error Y (degrees)
    pid_x: float  # PID output X (degrees)
    pid_y: float  # PID output Y (degrees)
    feedforward_x: float  # Feedforward output X (degrees)
    feedforward_y: float  # Feedforward output Y (degrees)
    raw_x: float  # Raw command X before slew limiting (degrees)
    raw_y: float  # Raw command Y before slew limiting (degrees)
    limited_x: float  # Limited command X after slew limiting (degrees)
    limited_y: float  # Limited command Y after slew limiting (degrees)
    slew_rate_x: float  # Achieved slew rate X (degrees/second)
    slew_rate_y: float  # Achieved slew rate Y (degrees/second)


class CameraController:
    """Main camera controller integrating PID, feedforward, and slew limiting.
    
    Control pipeline:
    1. Compute angular error (target - current)
    2. Apply PID control
    3. Add velocity feedforward
    4. Apply independent slew limiting (pan and tilt)
    5. Output CameraCommand with diagnostics
    """
    
    def __init__(self, control_config: ControlConfig):
        """Initialize camera controller with configuration.
        
        Args:
            control_config: Control system configuration
        """
        # Initialize PID controllers (one for each axis)
        self.pan_pid = PIDController(
            kp=control_config.kp,
            ki=control_config.ki,
            kd=control_config.kd
        )
        
        self.tilt_pid = PIDController(
            kp=control_config.kp,
            ki=control_config.ki,
            kd=control_config.kd
        )
        
        # Initialize velocity feedforward
        self.feedforward = VelocityFeedforward(gain=control_config.feedforward_gain)
        
        # Initialize independent slew limiters
        self.slew_limiters = SlewLimiterPair(
            max_pan_speed_deg_per_sec=control_config.max_pan_speed_deg_per_sec,
            max_tilt_speed_deg_per_sec=control_config.max_tilt_speed_deg_per_sec
        )
        
        # Current camera position state
        self.current_pan: float = 0.0
        self.current_tilt: float = 0.0
        self.position_initialized = False
    
    def update(
        self,
        target_pan: float,
        target_tilt: float,
        velocity_x: float,
        velocity_y: float,
        tracking_mode: TrackingMode,
        dt: float,
        timestamp: float,
        allow_lost_control: bool = False
    ) -> Tuple[CameraCommand, ControlDiagnostics]:
        """Compute camera command from target and current state.
        
        Args:
            target_pan: Target pan angle (degrees)
            target_tilt: Target tilt angle (degrees)
            velocity_x: Estimated velocity X (degrees/second)
            velocity_y: Estimated velocity Y (degrees/second)
            tracking_mode: Current tracking mode
            dt: Time step in seconds
            timestamp: Current timestamp (seconds)
            allow_lost_control: Allow control when in LOST state (for reacquisition)
            
        Returns:
            (CameraCommand, ControlDiagnostics) with command and diagnostics
        """
        # Do not allow control when LOST unless explicitly commanded
        if tracking_mode == TrackingMode.LOST and not allow_lost_control:
            # Hold current position
            limited_pan = self.current_pan
            limited_tilt = self.current_tilt
            pan_rate = 0.0
            tilt_rate = 0.0
            
            # Reset PIDs to prevent windup while holding
            self.pan_pid.reset()
            self.tilt_pid.reset()
            
            diagnostics = ControlDiagnostics(
                error_x=0.0,
                error_y=0.0,
                pid_x=0.0,
                pid_y=0.0,
                feedforward_x=0.0,
                feedforward_y=0.0,
                raw_x=0.0,
                raw_y=0.0,
                limited_x=limited_pan,
                limited_y=limited_tilt,
                slew_rate_x=pan_rate,
                slew_rate_y=tilt_rate
            )
            
            command = CameraCommand(
                timestamp=timestamp,
                pan_command=limited_pan,
                tilt_command=limited_tilt,
                slew_rate=(pan_rate, tilt_rate),
                command_mode="hold"
            )
            
            return command, diagnostics
        
        # Initialize position on first update
        if not self.position_initialized:
            self.current_pan = target_pan
            self.current_tilt = target_tilt
            self.position_initialized = True
            self.slew_limiters.reset(target_pan, target_tilt)
        
        # Compute angular errors
        error_x = target_pan - self.current_pan
        error_y = target_tilt - self.current_tilt
        
        # PID control
        pid_x = self.pan_pid.update(error_x, dt)
        pid_y = self.tilt_pid.update(error_y, dt)
        
        # Velocity feedforward
        ff_x, ff_y = self.feedforward.compute(velocity_x, velocity_y)
        
        # Combine PID and feedforward
        raw_x = self.current_pan + pid_x + ff_x
        raw_y = self.current_tilt + pid_y + ff_y
        
        # Apply independent slew limiting
        limited_x, limited_y, (slew_rate_x, slew_rate_y) = self.slew_limiters.limit(
            raw_x, raw_y, dt
        )
        
        # Update current position
        self.current_pan = limited_x
        self.current_tilt = limited_y
        
        # Create diagnostics
        diagnostics = ControlDiagnostics(
            error_x=error_x,
            error_y=error_y,
            pid_x=pid_x,
            pid_y=pid_y,
            feedforward_x=ff_x,
            feedforward_y=ff_y,
            raw_x=raw_x,
            raw_y=raw_y,
            limited_x=limited_x,
            limited_y=limited_y,
            slew_rate_x=slew_rate_x,
            slew_rate_y=slew_rate_y
        )
        
        # Create camera command
        command = CameraCommand(
            timestamp=timestamp,
            pan_command=limited_x,
            tilt_command=limited_y,
            slew_rate=(slew_rate_x, slew_rate_y),
            command_mode="tracking"
        )
        
        return command, diagnostics
    
    def reset(self, initial_pan: float = 0.0, initial_tilt: float = 0.0):
        """Reset controller state.
        
        Args:
            initial_pan: Initial pan position (default 0.0)
            initial_tilt: Initial tilt position (default 0.0)
        """
        self.pan_pid.reset()
        self.tilt_pid.reset()
        self.slew_limiters.reset(initial_pan, initial_tilt)
        self.current_pan = initial_pan
        self.current_tilt = initial_tilt
        self.position_initialized = False
