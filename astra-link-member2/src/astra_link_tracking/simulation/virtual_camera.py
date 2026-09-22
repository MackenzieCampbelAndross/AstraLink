"""Virtual camera model for closed-loop simulation."""

from typing import Tuple, Optional
import numpy as np

from astra_link_tracking.models.config import CameraConfig, ControlConfig
from astra_link_tracking.tracking.coordinate_transform import CoordinateTransform


class VirtualCamera:
    """Virtual camera model for simulation.
    
    Simulates a physical camera with:
    - Configurable resolution and FOV
    - Independent pan/tilt with slew rate limits
    - Angle-to-pixel conversion
    - Measurement noise generation
    """
    
    def __init__(
        self,
        camera_config: CameraConfig,
        control_config: ControlConfig,
        measurement_noise_std: float = 0.1
    ):
        """Initialize virtual camera.
        
        Args:
            camera_config: Camera configuration
            control_config: Control configuration with slew limits
            measurement_noise_std: Standard deviation of measurement noise (degrees)
        """
        self.camera_config = camera_config
        self.control_config = control_config
        self.measurement_noise_std = measurement_noise_std
        
        # Camera orientation (degrees)
        self.pan_angle = 0.0
        self.tilt_angle = 0.0
        
        # Initialize coordinate transform
        self.coord_transform = CoordinateTransform(camera_config)
    
    def get_state(self) -> Tuple[float, float]:
        """Get current camera orientation.
        
        Returns:
            (pan_angle, tilt_angle) in degrees
        """
        return (self.pan_angle, self.tilt_angle)
    
    def apply_command(self, pan_command: float, tilt_command: float, dt: float):
        """Apply camera command through physical slew limits.
        
        Camera angle evolves according to:
        new_angle = old_angle + clamped_command * dt
        
        Args:
            pan_command: Desired pan angle (degrees)
            tilt_command: Desired tilt angle (degrees)
            dt: Time step in seconds
        """
        # Calculate maximum allowed change per axis
        max_pan_delta = self.control_config.max_pan_speed_deg_per_sec * dt
        max_tilt_delta = self.control_config.max_tilt_speed_deg_per_sec * dt
        
        # Calculate desired change
        pan_delta = pan_command - self.pan_angle
        tilt_delta = tilt_command - self.tilt_angle
        
        # Clamp to slew limits
        pan_delta_clamped = max(-max_pan_delta, min(max_pan_delta, pan_delta))
        tilt_delta_clamped = max(-max_tilt_delta, min(max_tilt_delta, tilt_delta))
        
        # Apply clamped change
        self.pan_angle += pan_delta_clamped
        self.tilt_angle += tilt_delta_clamped
    
    def observe_target(
        self,
        target_pan: float,
        target_tilt: float,
        noise_std: Optional[float] = None
    ) -> Tuple[float, float]:
        """Observe target with measurement noise.
        
        Args:
            target_pan: True target pan angle (degrees)
            target_tilt: True target tilt angle (degrees)
            noise_std: Override default noise std (optional)
            
        Returns:
            (measured_pan, measured_tilt) with noise added
        """
        std = noise_std if noise_std is not None else self.measurement_noise_std
        
        # Add Gaussian noise
        measured_pan = target_pan + np.random.normal(0, std)
        measured_tilt = target_tilt + np.random.normal(0, std)
        
        return (measured_pan, measured_tilt)
    
    def angle_to_pixel(self, angle_x: float, angle_y: float) -> Tuple[float, float]:
        """Convert angular position to pixel coordinates.
        
        Args:
            angle_x: X angle in degrees (relative to camera center)
            angle_y: Y angle in degrees (relative to camera center)
            
        Returns:
            (pixel_x, pixel_y) coordinates
        """
        return self.coord_transform.angle_to_pixel(angle_x, angle_y)
    
    def pixel_to_angle(self, pixel_x: float, pixel_y: float) -> Tuple[float, float]:
        """Convert pixel coordinates to angular position.
        
        Args:
            pixel_x: X pixel coordinate
            pixel_y: Y pixel coordinate
            
        Returns:
            (angle_x, angle_y) in degrees (relative to camera center)
        """
        return self.coord_transform.pixel_to_angle(pixel_x, pixel_y)
    
    def get_relative_angle(
        self,
        target_pan: float,
        target_tilt: float
    ) -> Tuple[float, float]:
        """Get target angle relative to camera orientation.
        
        Args:
            target_pan: Target pan angle (degrees, absolute)
            target_tilt: Target tilt angle (degrees, absolute)
            
        Returns:
            (relative_pan, relative_tilt) in degrees (relative to camera center)
        """
        relative_pan = target_pan - self.pan_angle
        relative_tilt = target_tilt - self.tilt_angle
        
        return (relative_pan, relative_tilt)
    
    def reset(self, pan: float = 0.0, tilt: float = 0.0):
        """Reset camera to initial orientation.
        
        Args:
            pan: Initial pan angle (degrees)
            tilt: Initial tilt angle (degrees)
        """
        self.pan_angle = pan
        self.tilt_angle = tilt