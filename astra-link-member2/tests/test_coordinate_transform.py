"""Comprehensive tests for coordinate transformation."""

import pytest
import numpy as np
import math

from astra_link_tracking.tracking.coordinate_transform import CoordinateTransform
from astra_link_tracking.models.config import CameraConfig


class TestCoordinateTransform:
    """Test suite for coordinate transformation."""
    
    @pytest.fixture
    def default_camera_config(self):
        """Create default camera configuration (640x480, 4x3 degrees)."""
        return CameraConfig(
            resolution_width=640,
            resolution_height=480,
            horizontal_fov_deg=4.0,
            vertical_fov_deg=3.0,
            update_rate_hz=30.0
        )
    
    @pytest.fixture
    def default_transform(self, default_camera_config):
        """Create coordinate transform with default configuration."""
        return CoordinateTransform(default_camera_config)
    
    @pytest.fixture
    def hd_camera_config(self):
        """Create HD camera configuration (1280x720, 5x4 degrees)."""
        return CameraConfig(
            resolution_width=1280,
            resolution_height=720,
            horizontal_fov_deg=5.0,
            vertical_fov_deg=4.0,
            update_rate_hz=30.0
        )
    
    @pytest.fixture
    def hd_transform(self, hd_camera_config):
        """Create coordinate transform with HD configuration."""
        return CoordinateTransform(hd_camera_config)
    
    def test_initialization(self, default_transform):
        """Test coordinate transform initialization."""
        assert default_transform.resolution_width == 640
        assert default_transform.resolution_height == 480
        assert default_transform.horizontal_fov_deg == 4.0
        assert default_transform.vertical_fov_deg == 3.0
        assert default_transform.cx == 320.0
        assert default_transform.cy == 240.0
    
    def test_conversion_factors_default(self, default_transform):
        """Test conversion factors for default camera."""
        # For 640x480 with 4x3 degree FOV:
        # degrees_per_pixel = fov / resolution
        # For horizontal: 4.0 / 640 = 0.00625
        # For vertical: 3.0 / 480 = 0.00625
        
        assert abs(default_transform.degrees_per_pixel_x - 0.00625) < 1e-10
        assert abs(default_transform.degrees_per_pixel_y - 0.00625) < 1e-10
        assert abs(default_transform.pixels_per_degree_x - 160.0) < 1e-10
        assert abs(default_transform.pixels_per_degree_y - 160.0) < 1e-10
    
    def test_conversion_factors_hd(self, hd_transform):
        """Test conversion factors for HD camera."""
        # For 1280x720 with 5x4 degree FOV:
        # degrees_per_pixel_x = 5.0 / 1280 = 0.00390625
        # degrees_per_pixel_y = 4.0 / 720 = 0.005555...
        
        assert abs(hd_transform.degrees_per_pixel_x - 0.00390625) < 1e-10
        assert abs(hd_transform.degrees_per_pixel_y - 0.005555555555555556) < 1e-10
        assert abs(hd_transform.pixels_per_degree_x - 256.0) < 1e-10
        assert abs(hd_transform.pixels_per_degree_y - 180.0) < 1e-10
    
    def test_pixel_to_angle_center(self, default_transform):
        """Test pixel to angle conversion at image center."""
        # Image center should map to (0, 0) angular coordinates
        theta_x, theta_y = default_transform.pixel_to_angle(320.0, 240.0)
        
        assert abs(theta_x) < 1e-10
        assert abs(theta_y) < 1e-10
    
    def test_pixel_to_angle_right(self, default_transform):
        """Test pixel to angle conversion for rightward offset."""
        # Offset of 160 pixels right should be 1 degree (160 * 0.00625 = 1.0)
        theta_x, theta_y = default_transform.pixel_to_angle(480.0, 240.0)
        
        assert abs(theta_x - 1.0) < 1e-10
        assert abs(theta_y) < 1e-10
    
    def test_pixel_to_angle_left(self, default_transform):
        """Test pixel to angle conversion for leftward offset."""
        # Offset of 160 pixels left should be -1 degree
        theta_x, theta_y = default_transform.pixel_to_angle(160.0, 240.0)
        
        assert abs(theta_x - (-1.0)) < 1e-10
        assert abs(theta_y) < 1e-10
    
    def test_pixel_to_angle_down(self, default_transform):
        """Test pixel to angle conversion for downward offset."""
        # Offset of 160 pixels down should be 1 degree
        theta_x, theta_y = default_transform.pixel_to_angle(320.0, 400.0)
        
        assert abs(theta_x) < 1e-10
        assert abs(theta_y - 1.0) < 1e-10
    
    def test_pixel_to_angle_up(self, default_transform):
        """Test pixel to angle conversion for upward offset."""
        # Offset of 160 pixels up should be -1 degree
        theta_x, theta_y = default_transform.pixel_to_angle(320.0, 80.0)
        
        assert abs(theta_x) < 1e-10
        assert abs(theta_y - (-1.0)) < 1e-10
    
    def test_pixel_to_angle_diagonal(self, default_transform):
        """Test pixel to angle conversion for diagonal offset."""
        # Offset of 160 pixels right and 160 pixels down
        theta_x, theta_y = default_transform.pixel_to_angle(480.0, 400.0)
        
        assert abs(theta_x - 1.0) < 1e-10
        assert abs(theta_y - 1.0) < 1e-10
    
    def test_angle_to_pixel_center(self, default_transform):
        """Test angle to pixel conversion at origin."""
        # (0, 0) angular should map to image center
        x, y = default_transform.angle_to_pixel(0.0, 0.0)
        
        assert abs(x - 320.0) < 1e-10
        assert abs(y - 240.0) < 1e-10
    
    def test_angle_to_pixel_right(self, default_transform):
        """Test angle to pixel conversion for rightward angle."""
        # 1 degree right should map to 160 pixels right from center
        x, y = default_transform.angle_to_pixel(1.0, 0.0)
        
        assert abs(x - 480.0) < 1e-10
        assert abs(y - 240.0) < 1e-10
    
    def test_angle_to_pixel_left(self, default_transform):
        """Test angle to pixel conversion for leftward angle."""
        # -1 degree left should map to 160 pixels left from center
        x, y = default_transform.angle_to_pixel(-1.0, 0.0)
        
        assert abs(x - 160.0) < 1e-10
        assert abs(y - 240.0) < 1e-10
    
    def test_angle_to_pixel_down(self, default_transform):
        """Test angle to pixel conversion for downward angle."""
        # 1 degree down should map to 160 pixels down from center
        x, y = default_transform.angle_to_pixel(0.0, 1.0)
        
        assert abs(x - 320.0) < 1e-10
        assert abs(y - 400.0) < 1e-10
    
    def test_angle_to_pixel_up(self, default_transform):
        """Test angle to pixel conversion for upward angle."""
        # -1 degree up should map to 160 pixels up from center
        x, y = default_transform.angle_to_pixel(0.0, -1.0)
        
        assert abs(x - 320.0) < 1e-10
        assert abs(y - 80.0) < 1e-10
    
    def test_roundtrip_pixel_angle_pixel(self, default_transform):
        """Test roundtrip conversion: pixel -> angle -> pixel."""
        test_points = [
            (320.0, 240.0),  # Center
            (480.0, 400.0),  # Bottom-right
            (160.0, 80.0),   # Top-left
            (100.0, 100.0),  # Near corner
            (540.0, 380.0),  # Random
        ]
        
        for x_orig, y_orig in test_points:
            theta_x, theta_y = default_transform.pixel_to_angle(x_orig, y_orig)
            x_round, y_round = default_transform.angle_to_pixel(theta_x, theta_y)
            
            # Should roundtrip within floating point tolerance
            assert abs(x_round - x_orig) < 1e-9
            assert abs(y_round - y_orig) < 1e-9
    
    def test_roundtrip_angle_pixel_angle(self, default_transform):
        """Test roundtrip conversion: angle -> pixel -> angle."""
        test_angles = [
            (0.0, 0.0),      # Center
            (1.0, 1.0),      # Bottom-right
            (-1.0, -1.0),    # Top-left
            (0.5, -0.3),     # Random
            (2.0, 1.5),      # Larger offset
        ]
        
        for theta_x_orig, theta_y_orig in test_angles:
            x, y = default_transform.angle_to_pixel(theta_x_orig, theta_y_orig)
            theta_x_round, theta_y_round = default_transform.pixel_to_angle(x, y)
            
            # Should roundtrip within floating point tolerance
            assert abs(theta_x_round - theta_x_orig) < 1e-9
            assert abs(theta_y_round - theta_y_orig) < 1e-9
    
    def test_pixel_velocity_to_angular_velocity(self, default_transform):
        """Test pixel velocity to angular velocity conversion."""
        # 160 pixels/second should convert to 1 degree/second
        omega_x, omega_y = default_transform.pixel_velocity_to_angular_velocity(160.0, 160.0, 0.1)
        
        assert abs(omega_x - 1.0) < 1e-10
        assert abs(omega_y - 1.0) < 1e-10
    
    def test_angular_velocity_to_pixel_velocity(self, default_transform):
        """Test angular velocity to pixel velocity conversion."""
        # 1 degree/second should convert to 160 pixels/second
        vx, vy = default_transform.angular_velocity_to_pixel_velocity(1.0, 1.0, 0.1)
        
        assert abs(vx - 160.0) < 1e-10
        assert abs(vy - 160.0) < 1e-10
    
    def test_velocity_roundtrip(self, default_transform):
        """Test roundtrip velocity conversion."""
        test_velocities = [
            (100.0, 50.0),
            (-50.0, 30.0),
            (0.0, 0.0),
            (200.0, -100.0),
        ]
        
        for vx_orig, vy_orig in test_velocities:
            omega_x, omega_y = default_transform.pixel_velocity_to_angular_velocity(
                vx_orig, vy_orig, 0.1
            )
            vx_round, vy_round = default_transform.angular_velocity_to_pixel_velocity(
                omega_x, omega_y, 0.1
            )
            
            assert abs(vx_round - vx_orig) < 1e-9
            assert abs(vy_round - vy_orig) < 1e-9
    
    def test_velocity_conversion_independent_of_dt(self, default_transform):
        """Test that velocity conversion is independent of dt."""
        vx, vy = 100.0, 50.0
        
        # Convert with different dt values
        omega_x_1, omega_y_1 = default_transform.pixel_velocity_to_angular_velocity(vx, vy, 0.01)
        omega_x_2, omega_y_2 = default_transform.pixel_velocity_to_angular_velocity(vx, vy, 0.1)
        omega_x_3, omega_y_3 = default_transform.pixel_velocity_to_angular_velocity(vx, vy, 1.0)
        
        # Results should be identical
        assert abs(omega_x_1 - omega_x_2) < 1e-10
        assert abs(omega_y_1 - omega_y_2) < 1e-10
        assert abs(omega_x_2 - omega_x_3) < 1e-10
        assert abs(omega_y_2 - omega_y_3) < 1e-10
    
    def test_sign_convention_positive_x(self, default_transform):
        """Test sign convention: positive x (right) maps to positive angle."""
        # Right of center should give positive angle
        theta_x, _ = default_transform.pixel_to_angle(400.0, 240.0)
        assert theta_x > 0
    
    def test_sign_convention_negative_x(self, default_transform):
        """Test sign convention: negative x (left) maps to negative angle."""
        # Left of center should give negative angle
        theta_x, _ = default_transform.pixel_to_angle(240.0, 240.0)
        assert theta_x < 0
    
    def test_sign_convention_positive_y(self, default_transform):
        """Test sign convention: positive y (down) maps to positive angle."""
        # Below center should give positive angle
        _, theta_y = default_transform.pixel_to_angle(320.0, 300.0)
        assert theta_y > 0
    
    def test_sign_convention_negative_y(self, default_transform):
        """Test sign convention: negative y (up) maps to negative angle."""
        # Above center should give negative angle
        _, theta_y = default_transform.pixel_to_angle(320.0, 180.0)
        assert theta_y < 0
    
    def test_fov_boundaries(self, default_transform):
        """Test conversion at FOV boundaries."""
        # Left edge (0 pixels) should be at -2 degrees (half of 4 degree FOV)
        theta_x_left, _ = default_transform.pixel_to_angle(0.0, 240.0)
        assert abs(theta_x_left - (-2.0)) < 1e-10
        
        # Right edge (640 pixels) should be at +2 degrees
        theta_x_right, _ = default_transform.pixel_to_angle(640.0, 240.0)
        assert abs(theta_x_right - 2.0) < 1e-10
        
        # Top edge (0 pixels) should be at -1.5 degrees (half of 3 degree FOV)
        _, theta_y_top = default_transform.pixel_to_angle(320.0, 0.0)
        assert abs(theta_y_top - (-1.5)) < 1e-10
        
        # Bottom edge (480 pixels) should be at +1.5 degrees
        _, theta_y_bottom = default_transform.pixel_to_angle(320.0, 480.0)
        assert abs(theta_y_bottom - 1.5) < 1e-10
    
    def test_invalid_pixel_coordinates_nan(self, default_transform):
        """Test validation of NaN pixel coordinates."""
        with pytest.raises(ValueError, match="Invalid pixel x coordinate"):
            default_transform.pixel_to_angle(float('nan'), 240.0)
        
        with pytest.raises(ValueError, match="Invalid pixel y coordinate"):
            default_transform.pixel_to_angle(320.0, float('nan'))
    
    def test_invalid_pixel_coordinates_inf(self, default_transform):
        """Test validation of infinite pixel coordinates."""
        with pytest.raises(ValueError, match="Invalid pixel x coordinate"):
            default_transform.pixel_to_angle(float('inf'), 240.0)
        
        with pytest.raises(ValueError, match="Invalid pixel y coordinate"):
            default_transform.pixel_to_angle(320.0, float('-inf'))
    
    def test_invalid_angular_coordinates_nan(self, default_transform):
        """Test validation of NaN angular coordinates."""
        with pytest.raises(ValueError, match="Invalid angular theta_x coordinate"):
            default_transform.angle_to_pixel(float('nan'), 0.0)
        
        with pytest.raises(ValueError, match="Invalid angular theta_y coordinate"):
            default_transform.angle_to_pixel(0.0, float('nan'))
    
    def test_invalid_angular_coordinates_inf(self, default_transform):
        """Test validation of infinite angular coordinates."""
        with pytest.raises(ValueError, match="Invalid angular theta_x coordinate"):
            default_transform.angle_to_pixel(float('inf'), 0.0)
        
        with pytest.raises(ValueError, match="Invalid angular theta_y coordinate"):
            default_transform.angle_to_pixel(0.0, float('-inf'))
    
    def test_invalid_velocity_nan(self, default_transform):
        """Test validation of NaN velocities."""
        with pytest.raises(ValueError, match="Invalid pixel velocity vx"):
            default_transform.pixel_velocity_to_angular_velocity(float('nan'), 100.0, 0.1)
        
        with pytest.raises(ValueError, match="Invalid pixel velocity vy"):
            default_transform.pixel_velocity_to_angular_velocity(100.0, float('nan'), 0.1)
        
        with pytest.raises(ValueError, match="Invalid angular velocity omega_x"):
            default_transform.angular_velocity_to_pixel_velocity(float('nan'), 1.0, 0.1)
        
        with pytest.raises(ValueError, match="Invalid angular velocity omega_y"):
            default_transform.angular_velocity_to_pixel_velocity(1.0, float('nan'), 0.1)
    
    def test_invalid_velocity_inf(self, default_transform):
        """Test validation of infinite velocities."""
        with pytest.raises(ValueError, match="Invalid pixel velocity vx"):
            default_transform.pixel_velocity_to_angular_velocity(float('inf'), 100.0, 0.1)
        
        with pytest.raises(ValueError, match="Invalid angular velocity omega_x"):
            default_transform.angular_velocity_to_pixel_velocity(float('inf'), 1.0, 0.1)
    
    def test_invalid_dt_zero(self, default_transform):
        """Test validation of zero dt."""
        with pytest.raises(ValueError, match="Invalid time step dt"):
            default_transform.pixel_velocity_to_angular_velocity(100.0, 50.0, 0.0)
        
        with pytest.raises(ValueError, match="Invalid time step dt"):
            default_transform.angular_velocity_to_pixel_velocity(1.0, 0.5, 0.0)
    
    def test_invalid_dt_negative(self, default_transform):
        """Test validation of negative dt."""
        with pytest.raises(ValueError, match="Invalid time step dt"):
            default_transform.pixel_velocity_to_angular_velocity(100.0, 50.0, -0.1)
        
        with pytest.raises(ValueError, match="Invalid time step dt"):
            default_transform.angular_velocity_to_pixel_velocity(1.0, 0.5, -0.1)
    
    def test_invalid_dt_nan(self, default_transform):
        """Test validation of NaN dt."""
        with pytest.raises(ValueError, match="Invalid time step dt"):
            default_transform.pixel_velocity_to_angular_velocity(100.0, 50.0, float('nan'))
    
    def test_invalid_config_zero_resolution(self):
        """Test validation of zero resolution."""
        config = CameraConfig(resolution_width=0, resolution_height=480, 
                             horizontal_fov_deg=4.0, vertical_fov_deg=3.0)
        with pytest.raises(ValueError, match="resolution_width must be > 0"):
            config.validate()
    
    def test_invalid_config_zero_fov(self):
        """Test validation of zero FOV."""
        config = CameraConfig(resolution_width=640, resolution_height=480,
                             horizontal_fov_deg=0.0, vertical_fov_deg=3.0)
        with pytest.raises(ValueError, match="horizontal_fov_deg must be > 0"):
            config.validate()
    
    def test_get_conversion_factors(self, default_transform):
        """Test getting conversion factors."""
        factors = default_transform.get_conversion_factors()
        
        assert len(factors) == 4
        assert abs(factors[0] - 0.00625) < 1e-10  # degrees_per_pixel_x
        assert abs(factors[1] - 0.00625) < 1e-10  # degrees_per_pixel_y
        assert abs(factors[2] - 160.0) < 1e-10    # pixels_per_degree_x
        assert abs(factors[3] - 160.0) < 1e-10    # pixels_per_degree_y
    
    def test_get_camera_center(self, default_transform):
        """Test getting camera center."""
        cx, cy = default_transform.get_camera_center()
        
        assert abs(cx - 320.0) < 1e-10
        assert abs(cy - 240.0) < 1e-10
    
    def test_hd_vs_default_conversion(self, default_transform, hd_transform):
        """Test that different camera configurations produce different conversions."""
        # Same pixel offset should produce different angles for different cameras
        theta_x_default, _ = default_transform.pixel_to_angle(160.0, 240.0)
        theta_x_hd, _ = hd_transform.pixel_to_angle(160.0, 240.0)
        
        # Different FOV/resolution should give different angles
        assert abs(theta_x_default - theta_x_hd) > 1e-10
    
    def test_subpixel_precision(self, default_transform):
        """Test conversion with subpixel precision."""
        # Test with fractional pixel coordinates
        theta_x, theta_y = default_transform.pixel_to_angle(320.5, 240.3)
        
        # Should produce precise angular values
        assert math.isfinite(theta_x)
        assert math.isfinite(theta_y)
        
        # Roundtrip should preserve subpixel precision
        x_round, y_round = default_transform.angle_to_pixel(theta_x, theta_y)
        assert abs(x_round - 320.5) < 1e-9
        assert abs(y_round - 240.3) < 1e-9
    
    def test_large_angles(self, default_transform):
        """Test conversion with large angles."""
        # Test with angles larger than FOV (should still work mathematically)
        x, y = default_transform.angle_to_pixel(10.0, 10.0)
        
        # Should produce large pixel coordinates
        assert math.isfinite(x)
        assert math.isfinite(y)
        assert x > default_transform.resolution_width
        assert y > default_transform.resolution_height