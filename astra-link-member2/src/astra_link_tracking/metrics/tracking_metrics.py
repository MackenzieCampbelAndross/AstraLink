"""Tracking metrics calculation and logging."""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
import json
import csv
from pathlib import Path
from datetime import datetime

from astra_link_tracking.models.interfaces import TrackingMode
from astra_link_tracking.models.config import MetricsConfig
from astra_link_tracking.tracking.coordinate_transform import CoordinateTransform
from astra_link_tracking.models.config import CameraConfig


@dataclass
class TrackingRecord:
    """Single tracking record for logging."""
    timestamp: float
    frame_id: int
    state: str
    measurement_x: Optional[float]  # pixels
    measurement_y: Optional[float]  # pixels
    prediction_x: float  # degrees
    prediction_y: float  # degrees
    ground_truth_x: Optional[float]  # degrees
    ground_truth_y: Optional[float]  # degrees
    confidence: float
    innovation_x: Optional[float]
    innovation_y: Optional[float]
    mahalanobis_distance: Optional[float]
    motion_consistency: Optional[float]
    velocity_x: float  # degrees/second
    velocity_y: float  # degrees/second
    camera_angle_x: float  # degrees
    camera_angle_y: float  # degrees
    camera_command_x: float  # degrees
    camera_command_y: float  # degrees
    tracking_error_x: float  # degrees
    tracking_error_y: float  # degrees
    pixel_error_x: Optional[float]
    pixel_error_y: Optional[float]
    processing_time: float  # seconds


@dataclass
class MetricsSummary:
    """Summary of tracking metrics."""
    acquisition_time: Optional[float] = None  # seconds
    reacquisition_time: Optional[float] = None  # seconds
    mean_angular_error: float = 0.0  # degrees
    rmse_angular: float = 0.0  # degrees
    max_angular_error: float = 0.0  # degrees
    mean_pixel_error: float = 0.0  # pixels
    max_pixel_error: float = 0.0  # pixels
    lock_retention_rate: float = 0.0  # fraction
    target_loss_rate: float = 0.0  # fraction
    lock_events: int = 0
    loss_events: int = 0
    reacquisition_events: int = 0
    avg_processing_time: float = 0.0  # seconds
    max_processing_time: float = 0.0  # seconds
    effective_fps: float = 0.0  # Hz
    state_duration: Dict[str, float] = field(default_factory=dict)  # seconds per state
    total_duration: float = 0.0  # seconds
    total_frames: int = 0


class TrackingMetricsCalculator:
    """Calculates comprehensive tracking performance metrics.
    
    Calculates all metrics from actual logged data without inventing values.
    """
    
    def __init__(
        self,
        config: MetricsConfig,
        camera_config: CameraConfig
    ):
        """Initialize metrics calculator with configuration.
        
        Args:
            config: Metrics configuration
            camera_config: Camera configuration for pixel conversions
        """
        self.config = config
        self.camera_config = camera_config
        self.coord_transform = CoordinateTransform(camera_config)
        
        # Tracking records
        self.records: List[TrackingRecord] = []
        
        # State tracking
        self.current_state: Optional[TrackingMode] = None
        self.state_start_time: Optional[float] = None
        self.state_durations: Dict[str, float] = {}
        
        # Event tracking
        self.lock_events: int = 0
        self.loss_events: int = 0
        self.reacquisition_events: int = 0
        
        # Timing tracking
        self.acquisition_start_time: Optional[float] = None
        self.acquisition_time: Optional[float] = None
        self.loss_start_time: Optional[float] = None
        self.reacquisition_start_time: Optional[float] = None
        self.reacquisition_times: List[float] = []
        
        # Processing times
        self.processing_times: List[float] = []
        
        # Ground truth tracking
        self.experiment_start_time: Optional[float] = None
        self.total_frames: int = 0
    
    def start_experiment(self, timestamp: float):
        """Start the experiment.
        
        Args:
            timestamp: Experiment start timestamp
        """
        self.experiment_start_time = timestamp
        self.current_state = TrackingMode.SEARCH
        self.state_start_time = timestamp
    
    def record(
        self,
        timestamp: float,
        frame_id: int,
        state: TrackingMode,
        measurement_x: Optional[float],
        measurement_y: Optional[float],
        prediction_x: float,
        prediction_y: float,
        ground_truth_x: Optional[float],
        ground_truth_y: Optional[float],
        confidence: float,
        innovation_x: Optional[float],
        innovation_y: Optional[float],
        mahalanobis_distance: Optional[float],
        motion_consistency: Optional[float],
        velocity_x: float,
        velocity_y: float,
        camera_angle_x: float,
        camera_angle_y: float,
        camera_command_x: float,
        camera_command_y: float,
        processing_time: float
    ):
        """Record a tracking record.
        
        Args:
            timestamp: Record timestamp
            frame_id: Frame identifier
            state: Current tracking mode
            measurement_x: Measurement X in pixels
            measurement_y: Measurement Y in pixels
            prediction_x: Prediction X in degrees
            prediction_y: Prediction Y in degrees
            ground_truth_x: Ground truth X in degrees
            ground_truth_y: Ground truth Y in degrees
            confidence: Detection confidence
            innovation_x: Innovation X
            innovation_y: Innovation Y
            mahalanobis_distance: Mahalanobis distance
            motion_consistency: Motion consistency score
            velocity_x: Velocity X in degrees/second
            velocity_y: Velocity Y in degrees/second
            camera_angle_x: Camera angle X in degrees
            camera_angle_y: Camera angle Y in degrees
            camera_command_x: Camera command X in degrees
            camera_command_y: Camera command Y in degrees
            processing_time: Processing time in seconds
        """
        # Record processing time
        self.processing_times.append(processing_time)
        
        # Track events using old state (before transition)
        self._track_events(timestamp, state, self.current_state)
        
        # Track state transitions (updates current_state)
        self._track_state_transition(timestamp, state)
        
        # Calculate errors
        tracking_error_x = 0.0
        tracking_error_y = 0.0
        pixel_error_x = None
        pixel_error_y = None
        
        if ground_truth_x is not None and ground_truth_y is not None:
            tracking_error_x = prediction_x - ground_truth_x
            tracking_error_y = prediction_y - ground_truth_y
            
            # Convert to pixel error
            pred_pixel_x, pred_pixel_y = self.coord_transform.angle_to_pixel(
                prediction_x, prediction_y
            )
            gt_pixel_x, gt_pixel_y = self.coord_transform.angle_to_pixel(
                ground_truth_x, ground_truth_y
            )
            pixel_error_x = pred_pixel_x - gt_pixel_x
            pixel_error_y = pred_pixel_y - gt_pixel_y
        
        # Record processing time
        self.processing_times.append(processing_time)
        
        # Track events using old state (before transition)
        self._track_events(timestamp, state, self.current_state)
        
        # Track state transitions (updates current_state)
        self._track_state_transition(timestamp, state)
        
        # Create record
        record = TrackingRecord(
            timestamp=timestamp,
            frame_id=frame_id,
            state=state.value,
            measurement_x=measurement_x,
            measurement_y=measurement_y,
            prediction_x=prediction_x,
            prediction_y=prediction_y,
            ground_truth_x=ground_truth_x,
            ground_truth_y=ground_truth_y,
            confidence=confidence,
            innovation_x=innovation_x,
            innovation_y=innovation_y,
            mahalanobis_distance=mahalanobis_distance,
            motion_consistency=motion_consistency,
            velocity_x=velocity_x,
            velocity_y=velocity_y,
            camera_angle_x=camera_angle_x,
            camera_angle_y=camera_angle_y,
            camera_command_x=camera_command_x,
            camera_command_y=camera_command_y,
            tracking_error_x=tracking_error_x,
            tracking_error_y=tracking_error_y,
            pixel_error_x=pixel_error_x,
            pixel_error_y=pixel_error_y,
            processing_time=processing_time
        )
        
        self.records.append(record)
        self.total_frames += 1
    
    def _track_state_transition(self, timestamp: float, new_state: TrackingMode):
        """Track state transitions and durations.
        
        Args:
            timestamp: Current timestamp
            new_state: New tracking mode
        """
        if self.current_state != new_state:
            # Record duration of previous state
            if self.state_start_time is not None and self.current_state is not None:
                duration = timestamp - self.state_start_time
                state_name = self.current_state.value
                self.state_durations[state_name] = self.state_durations.get(state_name, 0.0) + duration
            
            # Update state
            self.current_state = new_state
            self.state_start_time = timestamp
    
    def _track_events(self, timestamp: float, new_state: TrackingMode, old_state: Optional[TrackingMode]):
        """Track lock, loss, and reacquisition events.
        
        Args:
            timestamp: Current timestamp
            new_state: New tracking mode
            old_state: Previous tracking mode (before transition)
        """
        # Track first acquisition (SEARCH -> LOCKED)
        if self.acquisition_time is None and new_state == TrackingMode.LOCKED:
            if self.acquisition_start_time is not None:
                self.acquisition_time = timestamp - self.acquisition_start_time
            elif self.experiment_start_time is not None:
                self.acquisition_time = timestamp - self.experiment_start_time
        
        # Track lock events (any transition to LOCKED except initial SEARCH->LOCKED)
        if new_state == TrackingMode.LOCKED and old_state != TrackingMode.LOCKED:
            # Count as lock event if not initial SEARCH->LOCKED
            # or if it's a reacquisition (reacquisition_start_time is set)
            if old_state != TrackingMode.SEARCH or self.reacquisition_start_time is not None:
                self.lock_events += 1
            
            # Check if this is a reacquisition (from LOST to LOCKED)
            if self.reacquisition_start_time is not None:
                reacq_time = timestamp - self.reacquisition_start_time
                self.reacquisition_times.append(reacq_time)
                self.reacquisition_events += 1
                self.reacquisition_start_time = None
        
        # Track loss events (any transition to LOST)
        if new_state == TrackingMode.LOST and old_state != TrackingMode.LOST:
            self.loss_events += 1
            self.loss_start_time = timestamp
            self.reacquisition_start_time = timestamp
    
    def calculate_summary(self) -> MetricsSummary:
        """Calculate comprehensive metrics summary.
        
        Returns:
            MetricsSummary with all calculated metrics
        """
        if not self.records:
            return MetricsSummary()
        
        # Calculate angular errors
        angular_errors = []
        pixel_errors = []
        
        for record in self.records:
            if record.ground_truth_x is not None and record.ground_truth_y is not None:
                # Angular error: sqrt(error_x^2 + error_y^2)
                angular_error = np.sqrt(
                    record.tracking_error_x**2 + record.tracking_error_y**2
                )
                angular_errors.append(angular_error)
                
                # Pixel error
                if record.pixel_error_x is not None and record.pixel_error_y is not None:
                    pixel_error = np.sqrt(
                        record.pixel_error_x**2 + record.pixel_error_y**2
                    )
                    pixel_errors.append(pixel_error)
        
        # Calculate angular metrics
        mean_angular_error = np.mean(angular_errors) if angular_errors else 0.0
        rmse_angular = np.sqrt(np.mean(np.array(angular_errors)**2)) if angular_errors else 0.0
        max_angular_error = np.max(angular_errors) if angular_errors else 0.0
        
        # Calculate pixel metrics
        mean_pixel_error = np.mean(pixel_errors) if pixel_errors else 0.0
        max_pixel_error = np.max(pixel_errors) if pixel_errors else 0.0
        
        # Calculate lock retention rate
        locked_duration = self.state_durations.get("locked", 0.0)
        total_duration = 0.0
        if self.experiment_start_time is not None and self.records:
            total_duration = self.records[-1].timestamp - self.experiment_start_time
        if total_duration > 0:
            lock_retention_rate = locked_duration / total_duration
        else:
            lock_retention_rate = 0.0
        
        # Calculate target loss rate
        lost_duration = self.state_durations.get("lost", 0.0)
        if total_duration > 0:
            target_loss_rate = lost_duration / total_duration
        else:
            target_loss_rate = 0.0
        
        # Calculate processing time metrics
        avg_processing_time = np.mean(self.processing_times) if self.processing_times else 0.0
        max_processing_time = np.max(self.processing_times) if self.processing_times else 0.0
        
        # Calculate effective FPS
        if total_duration > 0:
            effective_fps = self.total_frames / total_duration
        else:
            effective_fps = 0.0
        
        # Calculate reacquisition time
        reacquisition_time = None
        if self.reacquisition_times:
            reacquisition_time = np.mean(self.reacquisition_times)
        
        return MetricsSummary(
            acquisition_time=self.acquisition_time,
            reacquisition_time=reacquisition_time,
            mean_angular_error=mean_angular_error,
            rmse_angular=rmse_angular,
            max_angular_error=max_angular_error,
            mean_pixel_error=mean_pixel_error,
            max_pixel_error=max_pixel_error,
            lock_retention_rate=lock_retention_rate,
            target_loss_rate=target_loss_rate,
            lock_events=self.lock_events,
            loss_events=self.loss_events,
            reacquisition_events=self.reacquisition_events,
            avg_processing_time=avg_processing_time,
            max_processing_time=max_processing_time,
            effective_fps=effective_fps,
            state_duration=self.state_durations.copy(),
            total_duration=total_duration,
            total_frames=self.total_frames
        )
    
    def save_json(self, output_path: str):
        """Save tracking records and summary to JSON.
        
        Args:
            output_path: Path to output JSON file
        """
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Prepare data
        summary = self.calculate_summary()
        
        data = {
            "summary": {
                "acquisition_time": summary.acquisition_time,
                "reacquisition_time": summary.reacquisition_time,
                "mean_angular_error_deg": summary.mean_angular_error,
                "rmse_angular_deg": summary.rmse_angular,
                "max_angular_error_deg": summary.max_angular_error,
                "mean_pixel_error": summary.mean_pixel_error,
                "max_pixel_error": summary.max_pixel_error,
                "lock_retention_rate": summary.lock_retention_rate,
                "target_loss_rate": summary.target_loss_rate,
                "lock_events": summary.lock_events,
                "loss_events": summary.loss_events,
                "reacquisition_events": summary.reacquisition_events,
                "avg_processing_time_s": summary.avg_processing_time,
                "max_processing_time_s": summary.max_processing_time,
                "effective_fps": summary.effective_fps,
                "state_duration_s": summary.state_duration,
                "total_duration_s": summary.total_duration,
                "total_frames": summary.total_frames
            },
            "records": [
                {
                    "timestamp": r.timestamp,
                    "frame_id": r.frame_id,
                    "state": r.state,
                    "measurement_x": r.measurement_x,
                    "measurement_y": r.measurement_y,
                    "prediction_x_deg": r.prediction_x,
                    "prediction_y_deg": r.prediction_y,
                    "ground_truth_x_deg": r.ground_truth_x,
                    "ground_truth_y_deg": r.ground_truth_y,
                    "confidence": r.confidence,
                    "innovation_x": r.innovation_x,
                    "innovation_y": r.innovation_y,
                    "mahalanobis_distance": r.mahalanobis_distance,
                    "motion_consistency": r.motion_consistency,
                    "velocity_x_deg_s": r.velocity_x,
                    "velocity_y_deg_s": r.velocity_y,
                    "camera_angle_x_deg": r.camera_angle_x,
                    "camera_angle_y_deg": r.camera_angle_y,
                    "camera_command_x_deg": r.camera_command_x,
                    "camera_command_y_deg": r.camera_command_y,
                    "tracking_error_x_deg": r.tracking_error_x,
                    "tracking_error_y_deg": r.tracking_error_y,
                    "pixel_error_x": r.pixel_error_x,
                    "pixel_error_y": r.pixel_error_y,
                    "processing_time_s": r.processing_time
                }
                for r in self.records
            ]
        }
        
        with open(output_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def save_csv(self, output_path: str):
        """Save tracking records to CSV.
        
        Args:
            output_path: Path to output CSV file
        """
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        if not self.records:
            return
        
        fieldnames = [
            "timestamp", "frame_id", "state",
            "measurement_x", "measurement_y",
            "prediction_x_deg", "prediction_y_deg",
            "ground_truth_x_deg", "ground_truth_y_deg",
            "confidence",
            "innovation_x", "innovation_y",
            "mahalanobis_distance", "motion_consistency",
            "velocity_x_deg_s", "velocity_y_deg_s",
            "camera_angle_x_deg", "camera_angle_y_deg",
            "camera_command_x_deg", "camera_command_y_deg",
            "tracking_error_x_deg", "tracking_error_y_deg",
            "pixel_error_x", "pixel_error_y",
            "processing_time_s"
        ]
        
        with open(output_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for r in self.records:
                writer.writerow({
                    "timestamp": r.timestamp,
                    "frame_id": r.frame_id,
                    "state": r.state,
                    "measurement_x": r.measurement_x,
                    "measurement_y": r.measurement_y,
                    "prediction_x_deg": r.prediction_x,
                    "prediction_y_deg": r.prediction_y,
                    "ground_truth_x_deg": r.ground_truth_x,
                    "ground_truth_y_deg": r.ground_truth_y,
                    "confidence": r.confidence,
                    "innovation_x": r.innovation_x,
                    "innovation_y": r.innovation_y,
                    "mahalanobis_distance": r.mahalanobis_distance,
                    "motion_consistency": r.motion_consistency,
                    "velocity_x_deg_s": r.velocity_x,
                    "velocity_y_deg_s": r.velocity_y,
                    "camera_angle_x_deg": r.camera_angle_x,
                    "camera_angle_y_deg": r.camera_angle_y,
                    "camera_command_x_deg": r.camera_command_x,
                    "camera_command_y_deg": r.camera_command_y,
                    "tracking_error_x_deg": r.tracking_error_x,
                    "tracking_error_y_deg": r.tracking_error_y,
                    "pixel_error_x": r.pixel_error_x,
                    "pixel_error_y": r.pixel_error_y,
                    "processing_time_s": r.processing_time
                })
    
    def save_summary_report(self, output_path: str):
        """Save human-readable summary report.
        
        Args:
            output_path: Path to output report file
        """
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        summary = self.calculate_summary()
        
        acquisition_str = f"{summary.acquisition_time:.3f} s" if summary.acquisition_time is not None else "N/A"
        reacq_str = f"{summary.reacquisition_time:.3f} s" if summary.reacquisition_time is not None else "N/A"
        
        report = f"""Tracking Metrics Summary Report
Generated: {datetime.now().isoformat()}

=== Overall Performance ===
Total Duration: {summary.total_duration:.3f} s
Total Frames: {summary.total_frames}
Effective FPS: {summary.effective_fps:.2f} Hz

=== Acquisition ===
Acquisition Time: {acquisition_str}

=== Reacquisition ===
Reacquisition Events: {summary.reacquisition_events}
Reacquisition Time: {reacq_str}

=== Tracking Accuracy ===
Mean Angular Error: {summary.mean_angular_error:.4f}°
RMSE Angular: {summary.rmse_angular:.4f}°
Max Angular Error: {summary.max_angular_error:.4f}°
Mean Pixel Error: {summary.mean_pixel_error:.2f} px
Max Pixel Error: {summary.max_pixel_error:.2f} px

=== State Statistics ===
Lock Events: {summary.lock_events}
Loss Events: {summary.loss_events}
Lock Retention Rate: {summary.lock_retention_rate:.2%}
Target Loss Rate: {summary.target_loss_rate:.2%}

=== State Durations ===
"""
        
        for state, duration in summary.state_duration.items():
            report += f"{state.upper()}: {duration:.3f} s\n"
        
        report += f"""
=== Processing Performance ===
Average Processing Time: {summary.avg_processing_time*1000:.2f} ms
Max Processing Time: {summary.max_processing_time*1000:.2f} ms
"""
        
        with open(output_file, 'w') as f:
            f.write(report)
    
    def reset(self):
        """Reset metrics calculator."""
        self.records.clear()
        self.current_state = None
        self.state_start_time = None
        self.state_durations.clear()
        self.lock_events = 0
        self.loss_events = 0
        self.reacquisition_events = 0
        self.acquisition_start_time = None
        self.acquisition_time = None
        self.loss_start_time = None
        self.reacquisition_start_time = None
        self.reacquisition_times.clear()
        self.processing_times.clear()
        self.experiment_start_time = None
        self.total_frames = 0
