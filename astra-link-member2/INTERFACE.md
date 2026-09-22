# Astra Link Member 2 - Interface Specification

## Overview

This document defines the formal data contracts and interfaces between Member 2 (Tracking + State Estimation + Motion Consistency + Control + Reacquisition + Tracking Metrics) and other members of the Astra Link system.

## Interfaces

### Input from Member 1

#### DetectionResult
```python
@dataclass
class DetectionResult:
    """Beacon detection result from Member 1.
    
    Units:
    - timestamp: seconds
    - centroid_x, centroid_y: pixels
    - confidence: dimensionless [0, 1]
    """
    timestamp: float  # Detection timestamp (seconds)
    frame_id: int  # Frame identifier
    centroid_x: Optional[float] = None  # X centroid in pixels
    centroid_y: Optional[float] = None  # Y centroid in pixels
    confidence: float = 0.0  # Detection confidence [0, 1]
    visible: bool = False  # Whether beacon is visible
    
    # Optional future-compatible fields
    detector_id: Optional[str] = None  # Detector identifier
    bbox: Optional[Tuple[int, int, int, int]] = None  # (x1, y1, x2, y2) bounding box
    detection_area: Optional[float] = None  # Detection area in pixels^2
    metadata: Optional[Dict[str, Any]] = None  # Additional metadata
```

**Required Fields:**
- `timestamp`: Detection timestamp in seconds
- `frame_id`: Integer frame identifier
- `confidence`: Detection confidence in range [0, 1]
- `visible`: Boolean indicating if beacon is visible

**Optional Fields:**
- `centroid_x`, `centroid_y`: Pixel coordinates of beacon centroid (required if visible=True)
- `detector_id`: Identifier for the detector that produced this result
- `bbox`: Bounding box as (x1, y1, x2, y2) in pixels
- `detection_area`: Area of detection in pixels^2
- `metadata`: Additional detector-specific metadata

#### GroundTruthState (for simulation/metrics)
```python
@dataclass
class GroundTruthState:
    """Ground truth state for metrics evaluation.
    
    Units:
    - timestamp: seconds
    - position: pixels
    - velocity: pixels/second
    - acceleration: pixels/second^2
    """
    timestamp: float
    position: Tuple[float, float]  # True position in pixels
    velocity: Tuple[float, float]  # True velocity in pixels/second
    acceleration: Optional[Tuple[float, float]] = None  # True acceleration in pixels/second^2
```

### Output to Member 1

#### CameraCommand
```python
@dataclass
class CameraCommand:
    """Camera control command for Member 1.
    
    Units:
    - timestamp: seconds
    - pan_command, tilt_command: radians
    - slew_rate: radians/second
    """
    timestamp: float  # Command timestamp (seconds)
    pan_command: float  # Pan angle command (radians)
    tilt_command: float  # Tilt angle command (radians)
    
    # Optional diagnostics
    slew_rate: Optional[Tuple[float, float]] = None  # (pan_rate, tilt_rate) in rad/s
    command_mode: Optional[str] = None  # Additional mode information
    diagnostics: Optional[Dict[str, Any]] = None  # Additional diagnostic data
```

**Required Fields:**
- `timestamp`: Command timestamp in seconds
- `pan_command`: Pan angle command in radians
- `tilt_command`: Tilt angle command in radians

**Optional Fields:**
- `slew_rate`: Tuple of (pan_rate, tilt_rate) in radians/second
- `command_mode`: Additional mode information (e.g., "tracking", "searching")
- `diagnostics`: Additional diagnostic data for debugging

### Output to Member 3

#### TrackingState
```python
@dataclass
class TrackingState:
    """Current tracking state for Member 3 (security/trust).
    
    Units:
    - timestamp: seconds
    - predicted_x, predicted_y: pixels
    - angular_x, angular_y: radians
    - velocity_x, velocity_y: pixels/second
    - prediction_uncertainty: pixels^2 (variance)
    - confidence: dimensionless [0, 1]
    - time_since_last_detection: seconds
    """
    timestamp: float  # State timestamp (seconds)
    state: TrackingMode  # Current tracking mode
    predicted_x: float  # Predicted X position (pixels)
    predicted_y: float  # Predicted Y position (pixels)
    angular_x: float  # Angular position X (radians)
    angular_y: float  # Angular position Y (radians)
    velocity_x: float  # Velocity X (pixels/second)
    velocity_y: float  # Velocity Y (pixels/second)
    motion_consistency: bool  # Whether motion is physically consistent
    prediction_uncertainty: float  # Prediction uncertainty (variance)
    measurement_accepted: bool  # Whether last measurement was accepted
    confidence: float  # Tracking confidence [0, 1]
    time_since_last_detection: float  # Time since last detection (seconds)
    
    # Optional diagnostics
    position_covariance: Optional[np.ndarray] = None  # 2x2 covariance matrix
    tracking_id: Optional[str] = None  # Unique tracking session identifier
    diagnostics: Optional[Dict[str, Any]] = None  # Additional diagnostic data
```

**Required Fields:**
- `timestamp`: State timestamp in seconds
- `state`: Current tracking mode (TrackingMode enum)
- `predicted_x`, `predicted_y`: Predicted position in pixels
- `angular_x`, `angular_y`: Angular position in radians
- `velocity_x`, `velocity_y`: Velocity in pixels/second
- `motion_consistency`: Boolean indicating motion consistency
- `prediction_uncertainty`: Prediction uncertainty (variance) in pixels^2
- `measurement_accepted`: Boolean indicating if last measurement was accepted
- `confidence`: Tracking confidence in range [0, 1]
- `time_since_last_detection`: Time since last detection in seconds

**Optional Fields:**
- `position_covariance`: 2x2 position covariance matrix
- `tracking_id`: Unique tracking session identifier
- `diagnostics`: Additional diagnostic data

#### TrackingMode Enum
```python
class TrackingMode(Enum):
    """Tracking mode enumeration.
    
    Designed to be extensible for future security states without rewriting
    the tracker. New states can be added as needed.
    """
    SEARCH = "search"  # Actively searching for beacon
    LOCKED = "locked"  # Beacon locked and tracking
    COASTING = "coasting"  # Predicting without recent detections
    LOST = "lost"  # Beacon lost, reacquisition needed
```

**State Machine Transitions:**

The state machine implements hysteresis to prevent rapid oscillation between states:

- **SEARCH → LOCKED**: After `confirmation_frames` consecutive valid observations
- **SEARCH → SEARCH**: If candidate is invalid
- **LOCKED → COASTING**: When detection is temporarily missing or confidence insufficient
- **LOCKED → LOCKED**: Continue tracking with valid measurements
- **COASTING → LOCKED**: When valid consistent measurement returns (requires confirmation)
- **COASTING → LOST**: When missed frames exceed `maximum_missed_frames` OR prediction uncertainty exceeds `maximum_covariance_threshold`
- **LOST → LOCKED**: After valid reacquisition and confirmation
- **LOST → LOST**: Wait for reacquisition (does not immediately transition to SEARCH)

**Hysteresis Design:**
- Confirmation required for LOCKED and re-locking to prevent oscillation
- COASTING acts as a buffer state before declaring LOST
- Missing detection goes to COASTING first, not directly to LOST
- State machine is independent from security to allow Member 3 to add states like LOCKED_UNVERIFIED, AUTHENTICATING, AUTHENTICATED

#### Motion Consistency Diagnostics

Motion consistency analysis provides statistical filtering to prevent the tracker from being corrupted by spurious measurements:

**Mahalanobis Distance Gating:**
- Innovation: `y = z - H @ x_pred` (measurement - prediction)
- Innovation covariance: `S = H @ P_pred @ H.T + R`
- Mahalanobis distance: `d² = y.T @ inv(S) @ y`
- Gate threshold: Configurable (default 9.21 for 99% confidence with 2 DOF)

**Units:**
- Innovation components: degrees
- Innovation magnitude: degrees
- Mahalanobis distance squared: dimensionless
- Consistency score: dimensionless [0, 1]

**Measurement Handling:**
- **CASE 1** (visible + valid + gate passes): Accept normally (1x measurement covariance)
- **CASE 2** (visible + valid + gate fails): Reject measurement
- **CASE 3** (low confidence + statistically consistent): Accept with increased measurement covariance (1x to 10x multiplier)
- **CASE 4** (high confidence + wildly inconsistent): Reject despite high confidence (prevents violent jumps)

**Consistency Score Mapping:**
- Score = `exp(-d² / threshold)` in range [0, 1]
- d² = 0 → score = 1.0 (perfect consistency)
- d² = threshold → score = 0.368 (at gate boundary)
- d² >> threshold → score → 0.0 (inconsistent)
- This is a statistically meaningful mapping, not a fake accuracy score

#### TrackingMetrics
```python
@dataclass
class TrackingMetrics:
    """Tracking performance metrics.
    
    Units:
    - position_error: pixels or radians (depending on mode)
    - stability_score: dimensionless [0, 1]
    - latency: seconds
    - reacquisition_time: seconds
    - track_duration: seconds
    """
    position_error: float  # RMS position error (pixels or radians)
    stability_score: float  # Stability metric [0, 1]
    latency: float  # End-to-end latency (seconds)
    reacquisition_time: Optional[float] = None  # Time to reacquire after loss (seconds)
    track_duration: float = 0.0  # Total tracking duration (seconds)
    detection_count: int = 0  # Number of detections processed
    false_positive_count: int = 0  # Number of false positives rejected
```

## Configuration Schema

### Camera Configuration
```python
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
```

**Validation Rules:**
- `resolution_width > 0`
- `resolution_height > 0`
- `horizontal_fov_deg > 0`
- `vertical_fov_deg > 0`
- `update_rate_hz > 0`

**Computed Properties:**
- `pixel_to_angle_x`: Conversion factor from pixels to radians (horizontal)
- `pixel_to_angle_y`: Conversion factor from pixels to radians (vertical)
- `angle_to_pixel_x`: Conversion factor from radians to pixels (horizontal)
- `angle_to_pixel_y`: Conversion factor from radians to pixels (vertical)

### Control Configuration
```python
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
    
    MIN_CONTROL_RATE_HZ: float = 10.0  # Minimum system requirement
```

**Validation Rules:**
- `control_rate_hz > 0`
- `control_rate_hz >= 10.0` (minimum system requirement)
- `max_pan_speed_deg_per_sec > 0`
- `max_tilt_speed_deg_per_sec > 0`

### Tracking Configuration
```python
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
    mahalanobis_threshold: float = 9.21  # 99% confidence for 2D measurements
    confirmation_frames: int = 3
    maximum_missed_frames: int = 5
    maximum_covariance_threshold: float = 100.0
```

**Validation Rules:**
- `0.0 <= confidence_threshold <= 1.0`
- `process_noise > 0`
- `measurement_noise > 0`
- `mahalanobis_threshold > 0`
- `confirmation_frames > 0`
- `maximum_missed_frames > 0`
- `maximum_covariance_threshold > 0`

**Mahalanobis Threshold:**
- Default value of 9.21 corresponds to 99% confidence level for chi-squared distribution with 2 degrees of freedom
- Configurable to trade off false positives vs missed detections
- Lower threshold = stricter (more false positives, fewer missed detections)
- Higher threshold = more permissive (fewer false positives, more missed detections)
- Statistical interpretation: P(d² ≤ threshold) = confidence level

### Reacquisition Configuration
```python
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
```

**Validation Rules:**
- `initial_search_radius > 0`
- `maximum_search_radius > 0`
- `maximum_search_radius >= initial_search_radius`
- `levy_alpha > 0`
- `levy_min_step > 0`
- `levy_max_step > 0`
- `levy_max_step >= levy_min_step`
- `raster_grid_spacing > 0`
- `raster_search_radius > 0`
- `timeout > 0`

### Metrics Configuration
```python
@dataclass
class MetricsConfig:
    """Metrics and logging configuration parameters."""
    enable_logging: bool = True
    enable_ground_truth: bool = False
    log_output_path: Optional[str] = None
    plot_output_path: Optional[str] = None
```

## Data Flow

```
Member 1 (Detection) -> DetectionResult -> Member 2 (Tracking)
Member 2 (Tracking) -> CameraCommand -> Member 1 (Camera Control)
Member 2 (Tracking) -> TrackingState -> Member 3 (Security)
Member 2 (Tracking) -> TrackingMetrics -> Member 3 (Logging/Analysis)
```

## Usage Examples

### Basic Tracking Loop
```python
from astra_link_tracking.models.interfaces import DetectionResult, CameraCommand, TrackingMode
from astra_link_tracking.models.config import TrackingSystemConfig
from astra_link_tracking.tracking.tracker import Tracker

# Load configuration
config = TrackingSystemConfig.from_json_file("config/default_config.json")
config.validate()

# Create tracker
tracker = Tracker(config)

# Process detection
detection = DetectionResult(
    timestamp=1.0,
    frame_id=42,
    centroid_x=320.0,
    centroid_y=240.0,
    confidence=0.95,
    visible=True
)

tracking_state, camera_command = tracker.update(detection)

print(f"Tracking mode: {tracking_state.state.value}")
print(f"Predicted position: ({tracking_state.predicted_x}, {tracking_state.predicted_y})")
print(f"Camera command: pan={camera_command.pan_command:.4f}, tilt={camera_command.tilt_command:.4f}")
```

### Configuration Loading
```python
from astra_link_tracking.models.config import TrackingSystemConfig

# Load from JSON file
config = TrackingSystemConfig.from_json_file("config/default_config.json")
config.validate()

# Access configuration
print(f"Camera resolution: {config.camera.resolution_width}x{config.camera.resolution_height}")
print(f"Horizontal FOV: {config.camera.horizontal_fov_deg}°")
print(f"Pixel to angle X: {config.camera.pixel_to_angle_x} rad/pixel")

# Modify configuration
config.camera.resolution_width = 1280
config.camera.horizontal_fov_deg = 5.0
config.validate()

# Save modified configuration
config.to_json_file("config/custom_config.json")
```

### Closed-Loop Simulation
```python
from astra_link_tracking.simulation.closed_loop import ClosedLoopSimulation
from astra_link_tracking.models.config import TrackingSystemConfig

# Load configuration
config = TrackingSystemConfig.from_json_file("config/default_config.json")

# Run simulation
sim = ClosedLoopSimulation(config)
results = sim.run(duration=60.0)

# Access results
metrics = results["metrics"]
print(f"Position error: {metrics.position_error:.4f} pixels")
print(f"Stability score: {metrics.stability_score:.4f}")
print(f"Detection count: {metrics.detection_count}")
```

## Interface Principles

1. **Clear Separation**: Member 2 only depends on data structures, not implementation details of other members
2. **Type Safety**: All interfaces use Python type hints and dataclasses
3. **Configurability**: All parameters are configurable via JSON config with validation
4. **Headless Operation**: All core functionality works without visualization
5. **Testability**: Interfaces support both dummy and real data for testing
6. **Extensibility**: TrackingMode enum designed for future security states without rewriting tracker
7. **Validation**: All configuration parameters are validated with clear error messages
8. **Units Consistency**: All fields include explicit unit documentation
