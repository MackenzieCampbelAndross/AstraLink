"""Tests for configuration model and validation."""

import pytest
import json
import tempfile
from pathlib import Path

from astra_link_tracking.models.config import (
    TrackingSystemConfig,
    CameraConfig,
    ControlConfig,
    TrackingConfig,
    ReacquisitionConfig,
    MetricsConfig,
)


class TestCameraConfig:
    """Tests for CameraConfig."""
    
    def test_default_values(self):
        """Test default camera configuration values."""
        config = CameraConfig()
        assert config.resolution_width == 640
        assert config.resolution_height == 480
        assert config.horizontal_fov_deg == 4.0
        assert config.vertical_fov_deg == 3.0
        assert config.update_rate_hz == 30.0
    
    def test_validate_valid(self):
        """Test validation with valid parameters."""
        config = CameraConfig(
            resolution_width=1280,
            resolution_height=720,
            horizontal_fov_deg=5.0,
            vertical_fov_deg=4.0,
            update_rate_hz=60.0
        )
        config.validate()  # Should not raise
    
    def test_validate_invalid_resolution_width(self):
        """Test validation fails with invalid resolution width."""
        config = CameraConfig(resolution_width=0)
        with pytest.raises(ValueError, match="resolution_width must be > 0"):
            config.validate()
    
    def test_validate_invalid_resolution_height(self):
        """Test validation fails with invalid resolution height."""
        config = CameraConfig(resolution_height=-1)
        with pytest.raises(ValueError, match="resolution_height must be > 0"):
            config.validate()
    
    def test_validate_invalid_horizontal_fov(self):
        """Test validation fails with invalid horizontal FOV."""
        config = CameraConfig(horizontal_fov_deg=0)
        with pytest.raises(ValueError, match="horizontal_fov_deg must be > 0"):
            config.validate()
    
    def test_validate_invalid_vertical_fov(self):
        """Test validation fails with invalid vertical FOV."""
        config = CameraConfig(vertical_fov_deg=-0.1)
        with pytest.raises(ValueError, match="vertical_fov_deg must be > 0"):
            config.validate()
    
    def test_validate_invalid_update_rate(self):
        """Test validation fails with invalid update rate."""
        config = CameraConfig(update_rate_hz=0)
        with pytest.raises(ValueError, match="update_rate_hz must be > 0"):
            config.validate()
    
    def test_pixel_to_angle_conversion(self):
        """Test pixel to angle conversion factors."""
        config = CameraConfig(
            resolution_width=640,
            resolution_height=480,
            horizontal_fov_deg=4.0,
            vertical_fov_deg=3.0
        )
        
        # Check that conversion factors are positive
        assert config.pixel_to_angle_x > 0
        assert config.pixel_to_angle_y > 0
        
        # Check that angle to pixel is the inverse
        assert abs(config.angle_to_pixel_x - 1.0 / config.pixel_to_angle_x) < 1e-10
        assert abs(config.angle_to_pixel_y - 1.0 / config.pixel_to_angle_y) < 1e-10
    
    def test_fov_rad_conversion(self):
        """Test FOV degree to radian conversion."""
        config = CameraConfig(horizontal_fov_deg=180.0)
        assert abs(config.horizontal_fov_rad - 3.141592653589793) < 1e-10


class TestControlConfig:
    """Tests for ControlConfig."""
    
    def test_default_values(self):
        """Test default control configuration values."""
        config = ControlConfig()
        assert config.control_rate_hz == 20.0
        assert config.max_pan_speed_deg_per_sec == 5.0
        assert config.max_tilt_speed_deg_per_sec == 5.0
        assert config.kp == 1.0
        assert config.ki == 0.1
        assert config.kd == 0.01
        assert config.feedforward_gain == 0.5
    
    def test_validate_valid(self):
        """Test validation with valid parameters."""
        config = ControlConfig(
            control_rate_hz=30.0,
            max_pan_speed_deg_per_sec=10.0,
            max_tilt_speed_deg_per_sec=10.0,
            kp=2.0,
            ki=0.2,
            kd=0.02,
            feedforward_gain=0.8
        )
        config.validate()  # Should not raise
    
    def test_validate_invalid_control_rate(self):
        """Test validation fails with invalid control rate."""
        config = ControlConfig(control_rate_hz=0)
        with pytest.raises(ValueError, match="control_rate_hz must be > 0"):
            config.validate()
    
    def test_validate_control_rate_below_minimum(self):
        """Test validation fails when control rate is below minimum."""
        config = ControlConfig(control_rate_hz=5.0)
        with pytest.raises(ValueError, match="control_rate_hz must be >= 10.0"):
            config.validate()
    
    def test_validate_invalid_pan_speed(self):
        """Test validation fails with invalid pan speed."""
        config = ControlConfig(max_pan_speed_deg_per_sec=0)
        with pytest.raises(ValueError, match="max_pan_speed_deg_per_sec must be > 0"):
            config.validate()
    
    def test_validate_invalid_tilt_speed(self):
        """Test validation fails with invalid tilt speed."""
        config = ControlConfig(max_tilt_speed_deg_per_sec=-1.0)
        with pytest.raises(ValueError, match="max_tilt_speed_deg_per_sec must be > 0"):
            config.validate()
    
    def test_speed_rad_conversion(self):
        """Test speed degree to radian conversion."""
        config = ControlConfig(max_pan_speed_deg_per_sec=180.0)
        assert abs(config.max_pan_speed_rad_per_sec - 3.141592653589793) < 1e-10


class TestTrackingConfig:
    """Tests for TrackingConfig."""
    
    def test_default_values(self):
        """Test default tracking configuration values."""
        config = TrackingConfig()
        assert config.confidence_threshold == 0.5
        assert config.process_noise == 0.1
        assert config.measurement_noise == 1.0
        assert config.mahalanobis_threshold == 3.0
        assert config.confirmation_frames == 3
        assert config.maximum_missed_frames == 10
        assert config.maximum_covariance_threshold == 100.0
    
    def test_validate_valid(self):
        """Test validation with valid parameters."""
        config = TrackingConfig(
            confidence_threshold=0.7,
            process_noise=0.2,
            measurement_noise=2.0,
            mahalanobis_threshold=4.0,
            confirmation_frames=5,
            maximum_missed_frames=20,
            maximum_covariance_threshold=200.0
        )
        config.validate()  # Should not raise
    
    def test_validate_invalid_confidence_threshold(self):
        """Test validation fails with invalid confidence threshold."""
        config = TrackingConfig(confidence_threshold=1.5)
        with pytest.raises(ValueError, match="confidence_threshold must be in \\[0, 1\\]"):
            config.validate()
        
        config = TrackingConfig(confidence_threshold=-0.1)
        with pytest.raises(ValueError, match="confidence_threshold must be in \\[0, 1\\]"):
            config.validate()
    
    def test_validate_invalid_process_noise(self):
        """Test validation fails with invalid process noise."""
        config = TrackingConfig(process_noise=0)
        with pytest.raises(ValueError, match="process_noise must be > 0"):
            config.validate()
    
    def test_validate_invalid_measurement_noise(self):
        """Test validation fails with invalid measurement noise."""
        config = TrackingConfig(measurement_noise=-0.1)
        with pytest.raises(ValueError, match="measurement_noise must be > 0"):
            config.validate()
    
    def test_validate_invalid_mahalanobis_threshold(self):
        """Test validation fails with invalid Mahalanobis threshold."""
        config = TrackingConfig(mahalanobis_threshold=0)
        with pytest.raises(ValueError, match="mahalanobis_threshold must be > 0"):
            config.validate()
    
    def test_validate_invalid_confirmation_frames(self):
        """Test validation fails with invalid confirmation frames."""
        config = TrackingConfig(confirmation_frames=0)
        with pytest.raises(ValueError, match="confirmation_frames must be > 0"):
            config.validate()
    
    def test_validate_invalid_maximum_missed_frames(self):
        """Test validation fails with invalid maximum missed frames."""
        config = TrackingConfig(maximum_missed_frames=-1)
        with pytest.raises(ValueError, match="maximum_missed_frames must be > 0"):
            config.validate()
    
    def test_validate_invalid_maximum_covariance_threshold(self):
        """Test validation fails with invalid maximum covariance threshold."""
        config = TrackingConfig(maximum_covariance_threshold=0)
        with pytest.raises(ValueError, match="maximum_covariance_threshold must be > 0"):
            config.validate()


class TestReacquisitionConfig:
    """Tests for ReacquisitionConfig."""
    
    def test_default_values(self):
        """Test default reacquisition configuration values."""
        config = ReacquisitionConfig()
        assert config.initial_search_radius == 0.1
        assert config.maximum_search_radius == 1.0
        assert config.levy_alpha == 1.5
        assert config.levy_min_step == 0.01
        assert config.levy_max_step == 0.5
        assert config.raster_grid_spacing == 0.1
        assert config.raster_search_radius == 1.0
        assert config.timeout == 10.0
    
    def test_validate_valid(self):
        """Test validation with valid parameters."""
        config = ReacquisitionConfig(
            initial_search_radius=0.2,
            maximum_search_radius=2.0,
            levy_alpha=1.8,
            levy_min_step=0.02,
            levy_max_step=0.8,
            raster_grid_spacing=0.2,
            raster_search_radius=2.0,
            timeout=15.0
        )
        config.validate()  # Should not raise
    
    def test_validate_invalid_initial_search_radius(self):
        """Test validation fails with invalid initial search radius."""
        config = ReacquisitionConfig(initial_search_radius=0)
        with pytest.raises(ValueError, match="initial_search_radius must be > 0"):
            config.validate()
    
    def test_validate_invalid_maximum_search_radius(self):
        """Test validation fails with invalid maximum search radius."""
        config = ReacquisitionConfig(maximum_search_radius=0)
        with pytest.raises(ValueError, match="maximum_search_radius must be > 0"):
            config.validate()
    
    def test_validate_search_radius_order(self):
        """Test validation fails when max < initial search radius."""
        config = ReacquisitionConfig(
            initial_search_radius=1.0,
            maximum_search_radius=0.5
        )
        with pytest.raises(ValueError, match="maximum_search_radius must be >= initial_search_radius"):
            config.validate()
    
    def test_validate_invalid_levy_alpha(self):
        """Test validation fails with invalid Lévy alpha."""
        config = ReacquisitionConfig(levy_alpha=0)
        with pytest.raises(ValueError, match="levy_alpha must be > 0"):
            config.validate()
    
    def test_validate_invalid_levy_min_step(self):
        """Test validation fails with invalid Lévy min step."""
        config = ReacquisitionConfig(levy_min_step=0)
        with pytest.raises(ValueError, match="levy_min_step must be > 0"):
            config.validate()
    
    def test_validate_invalid_levy_max_step(self):
        """Test validation fails with invalid Lévy max step."""
        config = ReacquisitionConfig(levy_max_step=0)
        with pytest.raises(ValueError, match="levy_max_step must be > 0"):
            config.validate()
    
    def test_validate_levy_step_order(self):
        """Test validation fails when max < min step."""
        config = ReacquisitionConfig(
            levy_min_step=0.5,
            levy_max_step=0.1
        )
        with pytest.raises(ValueError, match="levy_max_step must be >= levy_min_step"):
            config.validate()
    
    def test_validate_invalid_raster_grid_spacing(self):
        """Test validation fails with invalid raster grid spacing."""
        config = ReacquisitionConfig(raster_grid_spacing=0)
        with pytest.raises(ValueError, match="raster_grid_spacing must be > 0"):
            config.validate()
    
    def test_validate_invalid_raster_search_radius(self):
        """Test validation fails with invalid raster search radius."""
        config = ReacquisitionConfig(raster_search_radius=-0.1)
        with pytest.raises(ValueError, match="raster_search_radius must be > 0"):
            config.validate()
    
    def test_validate_invalid_timeout(self):
        """Test validation fails with invalid timeout."""
        config = ReacquisitionConfig(timeout=0)
        with pytest.raises(ValueError, match="timeout must be > 0"):
            config.validate()


class TestMetricsConfig:
    """Tests for MetricsConfig."""
    
    def test_default_values(self):
        """Test default metrics configuration values."""
        config = MetricsConfig()
        assert config.enable_logging is True
        assert config.enable_ground_truth is False
        assert config.log_output_path is None
        assert config.plot_output_path is None
    
    def test_validate_always_passes(self):
        """Test validation always passes for metrics config."""
        config = MetricsConfig(
            enable_logging=False,
            enable_ground_truth=True,
            log_output_path="/tmp/log.txt",
            plot_output_path="/tmp/plot.png"
        )
        config.validate()  # Should not raise


class TestTrackingSystemConfig:
    """Tests for TrackingSystemConfig."""
    
    def test_default_values(self):
        """Test default system configuration values."""
        config = TrackingSystemConfig()
        assert isinstance(config.camera, CameraConfig)
        assert isinstance(config.control, ControlConfig)
        assert isinstance(config.tracking, TrackingConfig)
        assert isinstance(config.reacquisition, ReacquisitionConfig)
        assert isinstance(config.metrics, MetricsConfig)
    
    def test_validate_all_sections(self):
        """Test validation validates all sections."""
        config = TrackingSystemConfig()
        config.validate()  # Should not raise with default values
    
    def test_from_dict(self):
        """Test creating configuration from dictionary."""
        config_dict = {
            "CAMERA": {
                "resolution_width": 1280,
                "resolution_height": 720,
                "horizontal_fov_deg": 5.0,
                "vertical_fov_deg": 4.0,
                "update_rate_hz": 60.0
            },
            "CONTROL": {
                "control_rate_hz": 30.0,
                "max_pan_speed_deg_per_sec": 10.0,
                "max_tilt_speed_deg_per_sec": 10.0,
                "kp": 2.0,
                "ki": 0.2,
                "kd": 0.02,
                "feedforward_gain": 0.8
            },
            "TRACKING": {
                "confidence_threshold": 0.7,
                "process_noise": 0.2,
                "measurement_noise": 2.0,
                "mahalanobis_threshold": 4.0,
                "confirmation_frames": 5,
                "maximum_missed_frames": 20,
                "maximum_covariance_threshold": 200.0
            },
            "REACQUISITION": {
                "initial_search_radius": 0.2,
                "maximum_search_radius": 2.0,
                "levy_alpha": 1.8,
                "levy_min_step": 0.02,
                "levy_max_step": 0.8,
                "raster_grid_spacing": 0.2,
                "raster_search_radius": 2.0,
                "timeout": 15.0
            },
            "METRICS": {
                "enable_logging": False,
                "enable_ground_truth": True,
                "log_output_path": "/tmp/log.txt",
                "plot_output_path": "/tmp/plot.png"
            }
        }
        
        config = TrackingSystemConfig.from_dict(config_dict)
        assert config.camera.resolution_width == 1280
        assert config.control.control_rate_hz == 30.0
        assert config.tracking.confidence_threshold == 0.7
        assert config.reacquisition.initial_search_radius == 0.2
        assert config.metrics.enable_logging is False
    
    def test_from_json_file(self):
        """Test loading configuration from JSON file."""
        config_dict = {
            "CAMERA": {
                "resolution_width": 1280,
                "resolution_height": 720,
                "horizontal_fov_deg": 5.0,
                "vertical_fov_deg": 4.0,
                "update_rate_hz": 60.0
            },
            "CONTROL": {
                "control_rate_hz": 30.0,
                "max_pan_speed_deg_per_sec": 10.0,
                "max_tilt_speed_deg_per_sec": 10.0,
                "kp": 2.0,
                "ki": 0.2,
                "kd": 0.02,
                "feedforward_gain": 0.8
            },
            "TRACKING": {
                "confidence_threshold": 0.7,
                "process_noise": 0.2,
                "measurement_noise": 2.0,
                "mahalanobis_threshold": 4.0,
                "confirmation_frames": 5,
                "maximum_missed_frames": 20,
                "maximum_covariance_threshold": 200.0
            },
            "REACQUISITION": {
                "initial_search_radius": 0.2,
                "maximum_search_radius": 2.0,
                "levy_alpha": 1.8,
                "levy_min_step": 0.02,
                "levy_max_step": 0.8,
                "raster_grid_spacing": 0.2,
                "raster_search_radius": 2.0,
                "timeout": 15.0
            },
            "METRICS": {
                "enable_logging": False,
                "enable_ground_truth": True,
                "log_output_path": "/tmp/log.txt",
                "plot_output_path": "/tmp/plot.png"
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_dict, f)
            temp_path = f.name
        
        try:
            config = TrackingSystemConfig.from_json_file(temp_path)
            assert config.camera.resolution_width == 1280
            assert config.control.control_rate_hz == 30.0
        finally:
            Path(temp_path).unlink()
    
    def test_to_dict(self):
        """Test converting configuration to dictionary."""
        config = TrackingSystemConfig(
            camera=CameraConfig(resolution_width=1280),
            control=ControlConfig(control_rate_hz=30.0),
            tracking=TrackingConfig(confidence_threshold=0.7),
            reacquisition=ReacquisitionConfig(initial_search_radius=0.2),
            metrics=MetricsConfig(enable_logging=False)
        )
        
        config_dict = config.to_dict()
        assert config_dict["CAMERA"]["resolution_width"] == 1280
        assert config_dict["CONTROL"]["control_rate_hz"] == 30.0
        assert config_dict["TRACKING"]["confidence_threshold"] == 0.7
        assert config_dict["REACQUISITION"]["initial_search_radius"] == 0.2
        assert config_dict["METRICS"]["enable_logging"] is False
    
    def test_to_json_file(self):
        """Test saving configuration to JSON file."""
        config = TrackingSystemConfig(
            camera=CameraConfig(resolution_width=1280),
            control=ControlConfig(control_rate_hz=30.0),
            tracking=TrackingConfig(confidence_threshold=0.7),
            reacquisition=ReacquisitionConfig(initial_search_radius=0.2),
            metrics=MetricsConfig(enable_logging=False)
        )
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name
        
        try:
            config.to_json_file(temp_path)
            
            # Load and verify
            with open(temp_path, 'r') as f:
                loaded_dict = json.load(f)
            
            assert loaded_dict["CAMERA"]["resolution_width"] == 1280
            assert loaded_dict["CONTROL"]["control_rate_hz"] == 30.0
        finally:
            Path(temp_path).unlink()
    
    def test_roundtrip_dict(self):
        """Test roundtrip conversion from dict to config and back."""
        original_dict = {
            "CAMERA": {
                "resolution_width": 1280,
                "resolution_height": 720,
                "horizontal_fov_deg": 5.0,
                "vertical_fov_deg": 4.0,
                "update_rate_hz": 60.0
            },
            "CONTROL": {
                "control_rate_hz": 30.0,
                "max_pan_speed_deg_per_sec": 10.0,
                "max_tilt_speed_deg_per_sec": 10.0,
                "kp": 2.0,
                "ki": 0.2,
                "kd": 0.02,
                "feedforward_gain": 0.8
            },
            "TRACKING": {
                "confidence_threshold": 0.7,
                "process_noise": 0.2,
                "measurement_noise": 2.0,
                "mahalanobis_threshold": 4.0,
                "confirmation_frames": 5,
                "maximum_missed_frames": 20,
                "maximum_covariance_threshold": 200.0
            },
            "REACQUISITION": {
                "initial_search_radius": 0.2,
                "maximum_search_radius": 2.0,
                "levy_alpha": 1.8,
                "levy_min_step": 0.02,
                "levy_max_step": 0.8,
                "raster_grid_spacing": 0.2,
                "raster_search_radius": 2.0,
                "timeout": 15.0
            },
            "METRICS": {
                "enable_logging": False,
                "enable_ground_truth": True,
                "log_output_path": "/tmp/log.txt",
                "plot_output_path": "/tmp/plot.png"
            }
        }
        
        config = TrackingSystemConfig.from_dict(original_dict)
        result_dict = config.to_dict()
        
        assert result_dict == original_dict
    
    def test_validation_propagates(self):
        """Test that validation errors propagate from subsections."""
        config = TrackingSystemConfig(
            camera=CameraConfig(resolution_width=0)  # Invalid
        )
        
        with pytest.raises(ValueError, match="resolution_width must be > 0"):
            config.validate()
