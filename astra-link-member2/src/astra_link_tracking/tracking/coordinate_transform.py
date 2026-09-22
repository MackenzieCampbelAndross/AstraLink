"""Coordinate transformation utilities for Astra Link tracking system.

This module handles transformations between pixel coordinates (from detector)
and angular coordinates (internal tracking system).

Coordinate Conventions:
- Pixel coordinates: positive x = right, positive y = down (image coordinates)
- Angular coordinates: positive theta_x = right, positive theta_y = down
- Angular units: degrees for position, degrees/second for velocity
- Time units: seconds

Camera Reference Frame:
- Origin (0,0) in angular coordinates corresponds to image center (cx, cy)
- cx = resolution_width / 2
- cy = resolution_height / 2
"""

from typing import Tuple
import numpy as np
import math

from astra_link_tracking.models.config import CameraConfig


class CoordinateTransform:
    """Handles coordinate transformations between pixel and angular coordinates.
    
    The internal tracking system uses angular coordinates (degrees) while
    the detector provides pixel coordinates. This class converts between
    these coordinate systems using camera parameters from configuration.
    
    Sign Convention:
    - Pixel: positive x = right, positive y = down (standard image coordinates)
    - Angular: positive theta_x = right, positive theta_y = down
    - This maintains consistency: rightward pixel offset → rightward angle
    """
    
    def __init__(self, camera_config: CameraConfig):
        """Initialize coordinate transform with camera configuration.
        
        Args:
            camera_config: Camera configuration with resolution and FOV parameters
            
        Raises:
            ValueError: If configuration parameters are invalid
        """
        # Validate configuration
        camera_config.validate()
        
        self.resolution_width = camera_config.resolution_width
        self.resolution_height = camera_config.resolution_height
        self.horizontal_fov_deg = camera_config.horizontal_fov_deg
        self.vertical_fov_deg = camera_config.vertical_fov_deg
        
        # Camera center (pixel coordinates)
        self.cx = self.resolution_width / 2.0
        self.cy = self.resolution_height / 2.0
        
        # Conversion factors (degrees per pixel)
        # These are calculated dynamically from configuration, not hardcoded
        self.degrees_per_pixel_x = self.horizontal_fov_deg / self.resolution_width
        self.degrees_per_pixel_y = self.vertical_fov_deg / self.resolution_height
        
        # Inverse conversion factors (pixels per degree)
        self.pixels_per_degree_x = self.resolution_width / self.horizontal_fov_deg
        self.pixels_per_degree_y = self.resolution_height / self.vertical_fov_deg
        
        # Validate computed conversion factors
        self._validate_conversion_factors()
    
    def _validate_conversion_factors(self):
        """Validate that conversion factors are valid.
        
        Raises:
            ValueError: If conversion factors are invalid (NaN, infinity, or zero)
        """
        if not math.isfinite(self.degrees_per_pixel_x) or self.degrees_per_pixel_x <= 0:
            raise ValueError(f"Invalid degrees_per_pixel_x: {self.degrees_per_pixel_x}")
        if not math.isfinite(self.degrees_per_pixel_y) or self.degrees_per_pixel_y <= 0:
            raise ValueError(f"Invalid degrees_per_pixel_y: {self.degrees_per_pixel_y}")
        if not math.isfinite(self.pixels_per_degree_x) or self.pixels_per_degree_x <= 0:
            raise ValueError(f"Invalid pixels_per_degree_x: {self.pixels_per_degree_x}")
        if not math.isfinite(self.pixels_per_degree_y) or self.pixels_per_degree_y <= 0:
            raise ValueError(f"Invalid pixels_per_degree_y: {self.pixels_per_degree_y}")
    
    def _validate_pixel_coordinates(self, x: float, y: float):
        """Validate pixel coordinates.
        
        Args:
            x: X pixel coordinate
            y: Y pixel coordinate
            
        Raises:
            ValueError: If coordinates are invalid (NaN or infinity)
        """
        if not math.isfinite(x):
            raise ValueError(f"Invalid pixel x coordinate: {x}")
        if not math.isfinite(y):
            raise ValueError(f"Invalid pixel y coordinate: {y}")
    
    def _validate_angular_coordinates(self, theta_x: float, theta_y: float):
        """Validate angular coordinates.
        
        Args:
            theta_x: X angular coordinate (degrees)
            theta_y: Y angular coordinate (degrees)
            
        Raises:
            ValueError: If coordinates are invalid (NaN or infinity)
        """
        if not math.isfinite(theta_x):
            raise ValueError(f"Invalid angular theta_x coordinate: {theta_x}")
        if not math.isfinite(theta_y):
            raise ValueError(f"Invalid angular theta_y coordinate: {theta_y}")
    
    def pixel_to_angle(self, x: float, y: float) -> Tuple[float, float]:
        """Convert pixel coordinates to angular coordinates.
        
        Conversion formula:
        - dx_pixels = x - cx
        - dy_pixels = y - cy
        - theta_x = dx_pixels * horizontal_fov_deg / width
        - theta_y = dy_pixels * vertical_fov_deg / height
        
        Args:
            x: X pixel coordinate (positive = right)
            y: Y pixel coordinate (positive = down)
            
        Returns:
            (theta_x, theta_y) angular coordinates in degrees
            - theta_x: horizontal angle (positive = right)
            - theta_y: vertical angle (positive = down)
            
        Raises:
            ValueError: If pixel coordinates are invalid
        """
        self._validate_pixel_coordinates(x, y)
        
        # Calculate pixel offset from camera center
        dx_pixels = x - self.cx
        dy_pixels = y - self.cy
        
        # Convert to angular coordinates
        theta_x = dx_pixels * self.degrees_per_pixel_x
        theta_y = dy_pixels * self.degrees_per_pixel_y
        
        return (theta_x, theta_y)
    
    def angle_to_pixel(self, theta_x: float, theta_y: float) -> Tuple[float, float]:
        """Convert angular coordinates to pixel coordinates.
        
        Conversion formula (inverse of pixel_to_angle):
        - dx_pixels = theta_x * width / horizontal_fov_deg
        - dy_pixels = theta_y * height / vertical_fov_deg
        - x = dx_pixels + cx
        - y = dy_pixels + cy
        
        Args:
            theta_x: X angular coordinate in degrees (positive = right)
            theta_y: Y angular coordinate in degrees (positive = down)
            
        Returns:
            (x, y) pixel coordinates
            - x: X pixel coordinate (positive = right)
            - y: Y pixel coordinate (positive = down)
            
        Raises:
            ValueError: If angular coordinates are invalid
        """
        self._validate_angular_coordinates(theta_x, theta_y)
        
        # Convert angular offset to pixel offset
        dx_pixels = theta_x * self.pixels_per_degree_x
        dy_pixels = theta_y * self.pixels_per_degree_y
        
        # Convert to pixel coordinates
        x = dx_pixels + self.cx
        y = dy_pixels + self.cy
        
        return (x, y)
    
    def pixel_velocity_to_angular_velocity(
        self, 
        vx_pixels: float, 
        vy_pixels: float,
        dt: float
    ) -> Tuple[float, float]:
        """Convert pixel velocity to angular velocity.
        
        Conversion formula:
        - omega_x = vx_pixels * horizontal_fov_deg / width
        - omega_y = vy_pixels * vertical_fov_deg / height
        
        Note: This conversion is independent of dt because the scale factor
        (degrees per pixel) is the same for both position and velocity.
        
        Args:
            vx_pixels: X velocity in pixels/second
            vy_pixels: Y velocity in pixels/second
            dt: Time step in seconds (for validation, must be positive)
            
        Returns:
            (omega_x, omega_y) angular velocity in degrees/second
            - omega_x: horizontal angular velocity (positive = right)
            - omega_y: vertical angular velocity (positive = down)
            
        Raises:
            ValueError: If velocities are invalid or dt is not positive
        """
        if not math.isfinite(vx_pixels):
            raise ValueError(f"Invalid pixel velocity vx: {vx_pixels}")
        if not math.isfinite(vy_pixels):
            raise ValueError(f"Invalid pixel velocity vy: {vy_pixels}")
        if dt <= 0 or not math.isfinite(dt):
            raise ValueError(f"Invalid time step dt: {dt}")
        
        # Convert to angular velocity
        omega_x = vx_pixels * self.degrees_per_pixel_x
        omega_y = vy_pixels * self.degrees_per_pixel_y
        
        return (omega_x, omega_y)
    
    def angular_velocity_to_pixel_velocity(
        self,
        omega_x: float,
        omega_y: float,
        dt: float
    ) -> Tuple[float, float]:
        """Convert angular velocity to pixel velocity.
        
        Conversion formula (inverse of pixel_velocity_to_angular_velocity):
        - vx_pixels = omega_x * width / horizontal_fov_deg
        - vy_pixels = omega_y * height / vertical_fov_deg
        
        Note: This conversion is independent of dt because the scale factor
        (pixels per degree) is the same for both position and velocity.
        
        Args:
            omega_x: X angular velocity in degrees/second (positive = right)
            omega_y: Y angular velocity in degrees/second (positive = down)
            dt: Time step in seconds (for validation, must be positive)
            
        Returns:
            (vx_pixels, vy_pixels) pixel velocity in pixels/second
            - vx_pixels: X pixel velocity (positive = right)
            - vy_pixels: Y pixel velocity (positive = down)
            
        Raises:
            ValueError: If angular velocities are invalid or dt is not positive
        """
        if not math.isfinite(omega_x):
            raise ValueError(f"Invalid angular velocity omega_x: {omega_x}")
        if not math.isfinite(omega_y):
            raise ValueError(f"Invalid angular velocity omega_y: {omega_y}")
        if dt <= 0 or not math.isfinite(dt):
            raise ValueError(f"Invalid time step dt: {dt}")
        
        # Convert to pixel velocity
        vx_pixels = omega_x * self.pixels_per_degree_x
        vy_pixels = omega_y * self.pixels_per_degree_y
        
        return (vx_pixels, vy_pixels)
    
    def get_conversion_factors(self) -> Tuple[float, float, float, float]:
        """Get the conversion factors for reference.
        
        Returns:
            (degrees_per_pixel_x, degrees_per_pixel_y, 
             pixels_per_degree_x, pixels_per_degree_y)
        """
        return (
            self.degrees_per_pixel_x,
            self.degrees_per_pixel_y,
            self.pixels_per_degree_x,
            self.pixels_per_degree_y
        )
    
    def get_camera_center(self) -> Tuple[float, float]:
        """Get the camera center in pixel coordinates.
        
        Returns:
            (cx, cy) camera center
        """
        return (self.cx, self.cy)
