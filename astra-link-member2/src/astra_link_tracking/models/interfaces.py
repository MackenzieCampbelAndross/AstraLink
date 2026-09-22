"""Data interfaces for Astra Link tracking system."""

from dataclasses import dataclass, field
from typing import Tuple, Optional, Dict, Any
from enum import Enum
import numpy as np


class TrackingMode(Enum):
    """Tracking mode enumeration.
    
    Designed to be extensible for future security states without rewriting
    the tracker. New states can be added as needed.
    """
    SEARCH = "search"  # Actively searching for beacon
    LOCKED = "locked"  # Beacon locked and tracking
    COASTING = "coasting"  # Predicting without recent detections
    LOST = "lost"  # Beacon lost, reacquisition needed


@dataclass
class DetectionResult:
    """Beacon detection result from Member 1.
    
    This is the primary input to the tracking system from Member 1's
    beacon detection module.
    
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


@dataclass
class CameraCommand:
    """Camera control command for Member 1.
    
    This is the primary output to Member 1 for camera control.
    
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


@dataclass
class TrackingState:
    """Current tracking state for Member 3 (security/trust).
    
    This is output to Member 3 for security, authentication, and logging.
    
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


@dataclass
class TrackingMetrics:
    """Tracking performance metrics.
    
    These metrics are computed during simulation and can be output to Member 3
    for analysis and logging.
    
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


@dataclass
class GroundTruthState:
    """Ground truth state for metrics evaluation.
    
    This is used during simulation to compute tracking metrics.
    
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
