"""Configuration model with validation for Astra Link tracking system."""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any
import json
from pathlib import Path


@dataclass
class CameraConfig:
    """Camera configuration parameters.
    
    Units:
    - resolution_width, resolution_height: pixels
    - horizontal_fov_deg, vertical_fov_deg: degrees
    - update_rate_hz: Hz
    """
    resolution_width: int = 640
    resolution_height: int = 480
    horizontal_fov_deg: float = 4.0
    vertical_fov_deg: float = 3.0
    update_rate_hz: float = 30.0
    
    def validate(self) -> None:
        """Validate camera configuration parameters."""
        if self.resolution_width <= 0:
            raise ValueError(f"resolution_width must be > 0, got {self.resolution_width}")
        if self.resolution_height <= 0:
            raise ValueError(f"resolution_height must be > 0, got {self.resolution_height}")
        if self.horizontal_fov_deg <= 0:
            raise ValueError(f"horizontal_fov_deg must be > 0, got {self.horizontal_fov_deg}")
        if self.vertical_fov_deg <= 0:
            raise ValueError(f"vertical_fov_deg must be > 0, got {self.vertical_fov_deg}")
        if self.update_rate_hz <= 0:
            raise ValueError(f"update_rate_hz must be > 0, got {self.update_rate_hz}")
    
    @property
    def horizontal_fov_rad(self) -> float:
        """Horizontal field of view in radians."""
        return self.horizontal_fov_deg * (3.141592653589793 / 180.0)
    
    @property
    def vertical_fov_rad(self) -> float:
        """Vertical field of view in radians."""
        return self.vertical_fov_deg * (3.141592653589793 / 180.0)
    
    @property
    def pixel_to_angle_x(self) -> float:
        """Conversion factor from pixels to radians (horizontal)."""
        return self.horizontal_fov_rad / self.resolution_width
    
    @property
    def pixel_to_angle_y(self) -> float:
        """Conversion factor from pixels to radians (vertical)."""
        return self.vertical_fov_rad / self.resolution_height
    
    @property
    def angle_to_pixel_x(self) -> float:
        """Conversion factor from radians to pixels (horizontal)."""
        return self.resolution_width / self.horizontal_fov_rad
    
    @property
    def angle_to_pixel_y(self) -> float:
        """Conversion factor from radians to pixels (vertical)."""
        return self.resolution_height / self.vertical_fov_rad


@dataclass
class ControlConfig:
    """Control system configuration parameters.
    
    Units:
    - control_rate_hz: Hz
    - max_pan_speed_deg_per_sec, max_tilt_speed_deg_per_sec: degrees/second
    - kp, ki, kd: dimensionless (PID gains)
    - feedforward_gain: dimensionless
    """
    control_rate_hz: float = 20.0
    max_pan_speed_deg_per_sec: float = 5.0
    max_tilt_speed_deg_per_sec: float = 5.0
    kp: float = 1.0
    ki: float = 0.1
    kd: float = 0.01
    feedforward_gain: float = 0.5
    
    # Minimum system requirement
    MIN_CONTROL_RATE_HZ: float = 10.0
    
    def validate(self) -> None:
        """Validate control configuration parameters."""
        if self.control_rate_hz <= 0:
            raise ValueError(f"control_rate_hz must be > 0, got {self.control_rate_hz}")
        if self.control_rate_hz < self.MIN_CONTROL_RATE_HZ:
            raise ValueError(
                f"control_rate_hz must be >= {self.MIN_CONTROL_RATE_HZ} Hz, "
                f"got {self.control_rate_hz}"
            )
        if self.max_pan_speed_deg_per_sec <= 0:
            raise ValueError(
                f"max_pan_speed_deg_per_sec must be > 0, got {self.max_pan_speed_deg_per_sec}"
            )
        if self.max_tilt_speed_deg_per_sec <= 0:
            raise ValueError(
                f"max_tilt_speed_deg_per_sec must be > 0, got {self.max_tilt_speed_deg_per_sec}"
            )
    
    @property
    def max_pan_speed_rad_per_sec(self) -> float:
        """Maximum pan speed in radians/second."""
        return self.max_pan_speed_deg_per_sec * (3.141592653589793 / 180.0)
    
    @property
    def max_tilt_speed_rad_per_sec(self) -> float:
        """Maximum tilt speed in radians/second."""
        return self.max_tilt_speed_deg_per_sec * (3.141592653589793 / 180.0)


@dataclass
class TrackingConfig:
    """Tracking system configuration parameters.
    
    Units:
    - confidence_threshold: dimensionless [0, 1]
    - process_noise, measurement_noise: pixels^2 (variance)
    - mahalanobis_threshold: dimensionless
    - confirmation_frames, maximum_missed_frames: dimensionless (count)
    - maximum_covariance_threshold: pixels^2 (variance)
    """
    confidence_threshold: float = 0.5
    process_noise: float = 0.1
    measurement_noise: float = 1.0
    mahalanobis_threshold: float = 3.0
    confirmation_frames: int = 3
    maximum_missed_frames: int = 10
    maximum_covariance_threshold: float = 100.0
    
    def validate(self) -> None:
        """Validate tracking configuration parameters."""
        if not 0.0 <= self.confidence_threshold <= 1.0:
            raise ValueError(
                f"confidence_threshold must be in [0, 1], got {self.confidence_threshold}"
            )
        if self.process_noise <= 0:
            raise ValueError(f"process_noise must be > 0, got {self.process_noise}")
        if self.measurement_noise <= 0:
            raise ValueError(f"measurement_noise must be > 0, got {self.measurement_noise}")
        if self.mahalanobis_threshold <= 0:
            raise ValueError(
                f"mahalanobis_threshold must be > 0, got {self.mahalanobis_threshold}"
            )
        if self.confirmation_frames <= 0:
            raise ValueError(
                f"confirmation_frames must be > 0, got {self.confirmation_frames}"
            )
        if self.maximum_missed_frames <= 0:
            raise ValueError(
                f"maximum_missed_frames must be > 0, got {self.maximum_missed_frames}"
            )
        if self.maximum_covariance_threshold <= 0:
            raise ValueError(
                f"maximum_covariance_threshold must be > 0, got {self.maximum_covariance_threshold}"
            )


@dataclass
class ReacquisitionConfig:
    """Reacquisition system configuration parameters.
    
    Units:
    - initial_search_radius, maximum_search_radius: radians
    - levy_alpha: dimensionless (Lévy exponent)
    - levy_min_step, levy_max_step: radians
    - raster_grid_spacing: radians
    - raster_search_radius: radians
    - timeout: seconds
    """
    initial_search_radius: float = 0.1
    maximum_search_radius: float = 1.0
    levy_alpha: float = 1.5
    levy_min_step: float = 0.01
    levy_max_step: float = 0.5
    raster_grid_spacing: float = 0.1
    raster_search_radius: float = 1.0
    timeout: float = 10.0
    
    def validate(self) -> None:
        """Validate reacquisition configuration parameters."""
        if self.initial_search_radius <= 0:
            raise ValueError(
                f"initial_search_radius must be > 0, got {self.initial_search_radius}"
            )
        if self.maximum_search_radius <= 0:
            raise ValueError(
                f"maximum_search_radius must be > 0, got {self.maximum_search_radius}"
            )
        if self.maximum_search_radius < self.initial_search_radius:
            raise ValueError(
                f"maximum_search_radius must be >= initial_search_radius, "
                f"got {self.maximum_search_radius} < {self.initial_search_radius}"
            )
        if self.levy_alpha <= 0:
            raise ValueError(f"levy_alpha must be > 0, got {self.levy_alpha}")
        if self.levy_min_step <= 0:
            raise ValueError(f"levy_min_step must be > 0, got {self.levy_min_step}")
        if self.levy_max_step <= 0:
            raise ValueError(f"levy_max_step must be > 0, got {self.levy_max_step}")
        if self.levy_max_step < self.levy_min_step:
            raise ValueError(
                f"levy_max_step must be >= levy_min_step, "
                f"got {self.levy_max_step} < {self.levy_min_step}"
            )
        if self.raster_grid_spacing <= 0:
            raise ValueError(f"raster_grid_spacing must be > 0, got {self.raster_grid_spacing}")
        if self.raster_search_radius <= 0:
            raise ValueError(
                f"raster_search_radius must be > 0, got {self.raster_search_radius}"
            )
        if self.timeout <= 0:
            raise ValueError(f"timeout must be > 0, got {self.timeout}")


@dataclass
class MetricsConfig:
    """Metrics and logging configuration parameters."""
    enable_logging: bool = True
    enable_ground_truth: bool = False
    log_output_path: Optional[str] = None
    plot_output_path: Optional[str] = None
    
    def validate(self) -> None:
        """Validate metrics configuration parameters."""
        # No validation needed for boolean flags
        pass


@dataclass
class TrackingSystemConfig:
    """Complete tracking system configuration."""
    camera: CameraConfig = field(default_factory=CameraConfig)
    control: ControlConfig = field(default_factory=ControlConfig)
    tracking: TrackingConfig = field(default_factory=TrackingConfig)
    reacquisition: ReacquisitionConfig = field(default_factory=ReacquisitionConfig)
    metrics: MetricsConfig = field(default_factory=MetricsConfig)
    
    def validate(self) -> None:
        """Validate all configuration sections."""
        self.camera.validate()
        self.control.validate()
        self.tracking.validate()
        self.reacquisition.validate()
        self.metrics.validate()
    
    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> "TrackingSystemConfig":
        """Create configuration from dictionary.
        
        Args:
            config_dict: Configuration dictionary
            
        Returns:
            TrackingSystemConfig instance
        """
        camera_dict = config_dict.get("CAMERA", {})
        control_dict = config_dict.get("CONTROL", {})
        tracking_dict = config_dict.get("TRACKING", {})
        reacquisition_dict = config_dict.get("REACQUISITION", {})
        metrics_dict = config_dict.get("METRICS", {})
        
        return cls(
            camera=CameraConfig(**camera_dict),
            control=ControlConfig(**control_dict),
            tracking=TrackingConfig(**tracking_dict),
            reacquisition=ReacquisitionConfig(**reacquisition_dict),
            metrics=MetricsConfig(**metrics_dict)
        )
    
    @classmethod
    def from_json_file(cls, file_path: str) -> "TrackingSystemConfig":
        """Load configuration from JSON file.
        
        Args:
            file_path: Path to JSON configuration file
            
        Returns:
            TrackingSystemConfig instance
        """
        with open(file_path, 'r') as f:
            config_dict = json.load(f)
        return cls.from_dict(config_dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary.
        
        Returns:
            Configuration dictionary
        """
        return {
            "CAMERA": {
                "resolution_width": self.camera.resolution_width,
                "resolution_height": self.camera.resolution_height,
                "horizontal_fov_deg": self.camera.horizontal_fov_deg,
                "vertical_fov_deg": self.camera.vertical_fov_deg,
                "update_rate_hz": self.camera.update_rate_hz,
            },
            "CONTROL": {
                "control_rate_hz": self.control.control_rate_hz,
                "max_pan_speed_deg_per_sec": self.control.max_pan_speed_deg_per_sec,
                "max_tilt_speed_deg_per_sec": self.control.max_tilt_speed_deg_per_sec,
                "kp": self.control.kp,
                "ki": self.control.ki,
                "kd": self.control.kd,
                "feedforward_gain": self.control.feedforward_gain,
            },
            "TRACKING": {
                "confidence_threshold": self.tracking.confidence_threshold,
                "process_noise": self.tracking.process_noise,
                "measurement_noise": self.tracking.measurement_noise,
                "mahalanobis_threshold": self.tracking.mahalanobis_threshold,
                "confirmation_frames": self.tracking.confirmation_frames,
                "maximum_missed_frames": self.tracking.maximum_missed_frames,
                "maximum_covariance_threshold": self.tracking.maximum_covariance_threshold,
            },
            "REACQUISITION": {
                "initial_search_radius": self.reacquisition.initial_search_radius,
                "maximum_search_radius": self.reacquisition.maximum_search_radius,
                "levy_alpha": self.reacquisition.levy_alpha,
                "levy_min_step": self.reacquisition.levy_min_step,
                "levy_max_step": self.reacquisition.levy_max_step,
                "raster_grid_spacing": self.reacquisition.raster_grid_spacing,
                "raster_search_radius": self.reacquisition.raster_search_radius,
                "timeout": self.reacquisition.timeout,
            },
            "METRICS": {
                "enable_logging": self.metrics.enable_logging,
                "enable_ground_truth": self.metrics.enable_ground_truth,
                "log_output_path": self.metrics.log_output_path,
                "plot_output_path": self.metrics.plot_output_path,
            }
        }
    
    def to_json_file(self, file_path: str) -> None:
        """Save configuration to JSON file.
        
        Args:
            file_path: Path to save JSON configuration file
        """
        config_dict = self.to_dict()
        with open(file_path, 'w') as f:
            json.dump(config_dict, f, indent=2)
