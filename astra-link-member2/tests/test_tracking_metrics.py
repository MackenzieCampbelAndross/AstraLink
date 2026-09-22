"""Tests for tracking metrics calculator."""

import pytest
import numpy as np
import json
import csv
from pathlib import Path

from astra_link_tracking.metrics.tracking_metrics import (
    TrackingMetricsCalculator,
    TrackingRecord,
    MetricsSummary
)
from astra_link_tracking.models.config import MetricsConfig, CameraConfig
from astra_link_tracking.models.interfaces import TrackingMode


class TestTrackingMetricsCalculator:
    """Test suite for tracking metrics calculator."""
    
    @pytest.fixture
    def metrics_config(self):
        """Create metrics configuration."""
        return MetricsConfig(
            enable_logging=True,
            enable_ground_truth=True,
            log_output_path="outputs/logs/",
            plot_output_path="outputs/plots/"
        )
    
    @pytest.fixture
    def camera_config(self):
        """Create camera configuration."""
        return CameraConfig(
            resolution_width=640,
            resolution_height=480,
            horizontal_fov_deg=4.0,
            vertical_fov_deg=3.0,
            update_rate_hz=30.0
        )
    
    @pytest.fixture
    def calculator(self, metrics_config, camera_config):
        """Create metrics calculator instance."""
        return TrackingMetricsCalculator(metrics_config, camera_config)
    
    def test_initialization(self, calculator, metrics_config, camera_config):
        """Test calculator initialization."""
        assert calculator.config == metrics_config
        assert calculator.camera_config == camera_config
        assert len(calculator.records) == 0
        assert calculator.total_frames == 0
    
    def test_start_experiment(self, calculator):
        """Test starting experiment."""
        calculator.start_experiment(0.0)
        
        assert calculator.experiment_start_time == 0.0
        assert calculator.current_state == TrackingMode.SEARCH
        assert calculator.state_start_time == 0.0
    
    def test_record_basic(self, calculator):
        """Test basic record recording."""
        calculator.start_experiment(0.0)
        
        calculator.record(
            timestamp=0.05,
            frame_id=1,
            state=TrackingMode.LOCKED,
            measurement_x=320.0,
            measurement_y=240.0,
            prediction_x=0.0,
            prediction_y=0.0,
            ground_truth_x=0.0,
            ground_truth_y=0.0,
            confidence=0.9,
            innovation_x=0.0,
            innovation_y=0.0,
            mahalanobis_distance=1.0,
            motion_consistency=0.9,
            velocity_x=0.0,
            velocity_y=0.0,
            camera_angle_x=0.0,
            camera_angle_y=0.0,
            camera_command_x=0.0,
            camera_command_y=0.0,
            processing_time=0.001
        )
        
        assert len(calculator.records) == 1
        assert calculator.total_frames == 1
    
    def test_angular_error_calculation(self, calculator):
        """Test angular error calculation."""
        calculator.start_experiment(0.0)
        
        # Record with known error
        calculator.record(
            timestamp=0.05,
            frame_id=1,
            state=TrackingMode.LOCKED,
            measurement_x=320.0,
            measurement_y=240.0,
            prediction_x=1.0,  # 1 degree error
            prediction_y=0.0,
            ground_truth_x=0.0,
            ground_truth_y=0.0,
            confidence=0.9,
            innovation_x=0.0,
            innovation_y=0.0,
            mahalanobis_distance=1.0,
            motion_consistency=0.9,
            velocity_x=0.0,
            velocity_y=0.0,
            camera_angle_x=0.0,
            camera_angle_y=0.0,
            camera_command_x=0.0,
            camera_command_y=0.0,
            processing_time=0.001
        )
        
        summary = calculator.calculate_summary()
        
        # Angular error should be 1.0 degree
        assert abs(summary.mean_angular_error - 1.0) < 0.01
    
    def test_pixel_error_calculation(self, calculator):
        """Test pixel error calculation."""
        calculator.start_experiment(0.0)
        
        # Record with known error
        calculator.record(
            timestamp=0.05,
            frame_id=1,
            state=TrackingMode.LOCKED,
            measurement_x=320.0,
            measurement_y=240.0,
            prediction_x=0.00625,  # 1 pixel error (0.00625 degrees for default camera)
            prediction_y=0.0,
            ground_truth_x=0.0,
            ground_truth_y=0.0,
            confidence=0.9,
            innovation_x=0.0,
            innovation_y=0.0,
            mahalanobis_distance=1.0,
            motion_consistency=0.9,
            velocity_x=0.0,
            velocity_y=0.0,
            camera_angle_x=0.0,
            camera_angle_y=0.0,
            camera_command_x=0.0,
            camera_command_y=0.0,
            processing_time=0.001
        )
        
        summary = calculator.calculate_summary()
        
        # Pixel error should be approximately 1.0
        assert abs(summary.mean_pixel_error - 1.0) < 0.1
    
    def test_rmse_calculation(self, calculator):
        """Test RMSE calculation with known synthetic data."""
        calculator.start_experiment(0.0)
        
        # Record with known errors: [1.0, 2.0, 3.0] degrees
        errors = [1.0, 2.0, 3.0]
        for i, error in enumerate(errors):
            calculator.record(
                timestamp=0.05 * (i + 1),
                frame_id=i + 1,
                state=TrackingMode.LOCKED,
                measurement_x=320.0,
                measurement_y=240.0,
                prediction_x=error,
                prediction_y=0.0,
                ground_truth_x=0.0,
                ground_truth_y=0.0,
                confidence=0.9,
                innovation_x=0.0,
                innovation_y=0.0,
                mahalanobis_distance=1.0,
                motion_consistency=0.9,
                velocity_x=0.0,
                velocity_y=0.0,
                camera_angle_x=0.0,
                camera_angle_y=0.0,
                camera_command_x=0.0,
                camera_command_y=0.0,
                processing_time=0.001
            )
        
        summary = calculator.calculate_summary()
        
        # RMSE = sqrt((1^2 + 2^2 + 3^2) / 3) = sqrt(14/3) ≈ 2.16
        expected_rmse = np.sqrt(14.0 / 3.0)
        assert abs(summary.rmse_angular - expected_rmse) < 0.01
    
    def test_max_error_calculation(self, calculator):
        """Test maximum error calculation."""
        calculator.start_experiment(0.0)
        
        # Record with known errors: [1.0, 2.0, 3.0] degrees
        errors = [1.0, 2.0, 3.0]
        for i, error in enumerate(errors):
            calculator.record(
                timestamp=0.05 * (i + 1),
                frame_id=i + 1,
                state=TrackingMode.LOCKED,
                measurement_x=320.0,
                measurement_y=240.0,
                prediction_x=error,
                prediction_y=0.0,
                ground_truth_x=0.0,
                ground_truth_y=0.0,
                confidence=0.9,
                innovation_x=0.0,
                innovation_y=0.0,
                mahalanobis_distance=1.0,
                motion_consistency=0.9,
                velocity_x=0.0,
                velocity_y=0.0,
                camera_angle_x=0.0,
                camera_angle_y=0.0,
                camera_command_x=0.0,
                camera_command_y=0.0,
                processing_time=0.001
            )
        
        summary = calculator.calculate_summary()
        
        # Max error should be 3.0
        assert summary.max_angular_error == 3.0
    
    def test_state_tracking(self, calculator):
        """Test state duration tracking."""
        calculator.start_experiment(0.0)
        
        # Record in SEARCH state
        calculator.record(
            timestamp=0.05,
            frame_id=1,
            state=TrackingMode.SEARCH,
            measurement_x=320.0,
            measurement_y=240.0,
            prediction_x=0.0,
            prediction_y=0.0,
            ground_truth_x=0.0,
            ground_truth_y=0.0,
            confidence=0.9,
            innovation_x=0.0,
            innovation_y=0.0,
            mahalanobis_distance=1.0,
            motion_consistency=0.9,
            velocity_x=0.0,
            velocity_y=0.0,
            camera_angle_x=0.0,
            camera_angle_y=0.0,
            camera_command_x=0.0,
            camera_command_y=0.0,
            processing_time=0.001
        )
        
        # Record in LOCKED state (transition from SEARCH)
        calculator.record(
            timestamp=0.10,
            frame_id=2,
            state=TrackingMode.LOCKED,
            measurement_x=320.0,
            measurement_y=240.0,
            prediction_x=0.0,
            prediction_y=0.0,
            ground_truth_x=0.0,
            ground_truth_y=0.0,
            confidence=0.9,
            innovation_x=0.0,
            innovation_y=0.0,
            mahalanobis_distance=1.0,
            motion_consistency=0.9,
            velocity_x=0.0,
            velocity_y=0.0,
            camera_angle_x=0.0,
            camera_angle_y=0.0,
            camera_command_x=0.0,
            camera_command_y=0.0,
            processing_time=0.001
        )
        
        # Transition to COASTING to trigger LOCKED duration recording
        calculator.record(
            timestamp=0.15,
            frame_id=3,
            state=TrackingMode.COASTING,
            measurement_x=None,
            measurement_y=None,
            prediction_x=0.0,
            prediction_y=0.0,
            ground_truth_x=0.0,
            ground_truth_y=0.0,
            confidence=0.0,
            innovation_x=0.0,
            innovation_y=0.0,
            mahalanobis_distance=1.0,
            motion_consistency=0.9,
            velocity_x=0.0,
            velocity_y=0.0,
            camera_angle_x=0.0,
            camera_angle_y=0.0,
            camera_command_x=0.0,
            camera_command_y=0.0,
            processing_time=0.001
        )
        
        summary = calculator.calculate_summary()
        
        # Should have state durations
        assert "search" in summary.state_duration
        assert "locked" in summary.state_duration
        # SEARCH duration: 0.0 to 0.10 = 0.10
        assert abs(summary.state_duration["search"] - 0.10) < 0.01
        # LOCKED duration: 0.10 to 0.15 = 0.05
        assert abs(summary.state_duration["locked"] - 0.05) < 0.01
    
    def test_lock_retention_rate(self, calculator):
        """Test lock retention rate calculation."""
        calculator.start_experiment(0.0)
        
        # Record half in LOCKED, half in LOST
        for i in range(10):
            state = TrackingMode.LOCKED if i < 5 else TrackingMode.LOST
            calculator.record(
                timestamp=0.05 * (i + 1),
                frame_id=i + 1,
                state=state,
                measurement_x=320.0,
                measurement_y=240.0,
                prediction_x=0.0,
                prediction_y=0.0,
                ground_truth_x=0.0,
                ground_truth_y=0.0,
                confidence=0.9,
                innovation_x=0.0,
                innovation_y=0.0,
                mahalanobis_distance=1.0,
                motion_consistency=0.9,
                velocity_x=0.0,
                velocity_y=0.0,
                camera_angle_x=0.0,
                camera_angle_y=0.0,
                camera_command_x=0.0,
                camera_command_y=0.0,
                processing_time=0.001
            )
        
        summary = calculator.calculate_summary()
        
        # Lock retention should be 0.5 (5 out of 10 frames)
        assert abs(summary.lock_retention_rate - 0.5) < 0.01
    
    def test_target_loss_rate(self, calculator):
        """Test target loss rate calculation."""
        calculator.start_experiment(0.0)
        
        # Record half in LOST
        for i in range(10):
            state = TrackingMode.LOST if i < 5 else TrackingMode.LOCKED
            calculator.record(
                timestamp=0.05 * (i + 1),
                frame_id=i + 1,
                state=state,
                measurement_x=320.0,
                measurement_y=240.0,
                prediction_x=0.0,
                prediction_y=0.0,
                ground_truth_x=0.0,
                ground_truth_y=0.0,
                confidence=0.9,
                innovation_x=0.0,
                innovation_y=0.0,
                mahalanobis_distance=1.0,
                motion_consistency=0.9,
                velocity_x=0.0,
                velocity_y=0.0,
                camera_angle_x=0.0,
                camera_angle_y=0.0,
                camera_command_x=0.0,
                camera_command_y=0.0,
                processing_time=0.001
            )
        
        summary = calculator.calculate_summary()
        
        # Loss rate should be 0.5 (5 out of 10 frames)
        assert abs(summary.target_loss_rate - 0.5) < 0.01
    
    def test_lock_events(self, calculator):
        """Test lock event counting."""
        calculator.start_experiment(0.0)
        
        # First in SEARCH
        calculator.record(
            timestamp=0.05,
            frame_id=1,
            state=TrackingMode.SEARCH,
            measurement_x=320.0,
            measurement_y=240.0,
            prediction_x=0.0,
            prediction_y=0.0,
            ground_truth_x=0.0,
            ground_truth_y=0.0,
            confidence=0.9,
            innovation_x=0.0,
            innovation_y=0.0,
            mahalanobis_distance=1.0,
            motion_consistency=0.9,
            velocity_x=0.0,
            velocity_y=0.0,
            camera_angle_x=0.0,
            camera_angle_y=0.0,
            camera_command_x=0.0,
            camera_command_y=0.0,
            processing_time=0.001
        )
        
        # Transition to LOCKED (should not count as lock event - initial acquisition)
        calculator.record(
            timestamp=0.10,
            frame_id=2,
            state=TrackingMode.LOCKED,
            measurement_x=320.0,
            measurement_y=240.0,
            prediction_x=0.0,
            prediction_y=0.0,
            ground_truth_x=0.0,
            ground_truth_y=0.0,
            confidence=0.9,
            innovation_x=0.0,
            innovation_y=0.0,
            mahalanobis_distance=1.0,
            motion_consistency=0.9,
            velocity_x=0.0,
            velocity_y=0.0,
            camera_angle_x=0.0,
            camera_angle_y=0.0,
            camera_command_x=0.0,
            camera_command_y=0.0,
            processing_time=0.001
        )
        
        # Transition to LOST
        calculator.record(
            timestamp=0.15,
            frame_id=3,
            state=TrackingMode.LOST,
            measurement_x=None,
            measurement_y=None,
            prediction_x=0.0,
            prediction_y=0.0,
            ground_truth_x=0.0,
            ground_truth_y=0.0,
            confidence=0.0,
            innovation_x=0.0,
            innovation_y=0.0,
            mahalanobis_distance=1.0,
            motion_consistency=0.9,
            velocity_x=0.0,
            velocity_y=0.0,
            camera_angle_x=0.0,
            camera_angle_y=0.0,
            camera_command_x=0.0,
            camera_command_y=0.0,
            processing_time=0.001
        )
        
        # Reacquisition to LOCKED (should count as lock event)
        calculator.record(
            timestamp=0.20,
            frame_id=4,
            state=TrackingMode.LOCKED,
            measurement_x=320.0,
            measurement_y=240.0,
            prediction_x=0.0,
            prediction_y=0.0,
            ground_truth_x=0.0,
            ground_truth_y=0.0,
            confidence=0.9,
            innovation_x=0.0,
            innovation_y=0.0,
            mahalanobis_distance=1.0,
            motion_consistency=0.9,
            velocity_x=0.0,
            velocity_y=0.0,
            camera_angle_x=0.0,
            camera_angle_y=0.0,
            camera_command_x=0.0,
            camera_command_y=0.0,
            processing_time=0.001
        )
        
        summary = calculator.calculate_summary()
        
        # LOST->LOCKED should count as a lock event (not initial SEARCH->LOCKED)
        assert summary.lock_events == 1
    
    def test_loss_events(self, calculator):
        """Test loss event counting."""
        calculator.start_experiment(0.0)
        
        # First in SEARCH
        calculator.record(
            timestamp=0.05,
            frame_id=1,
            state=TrackingMode.SEARCH,
            measurement_x=320.0,
            measurement_y=240.0,
            prediction_x=0.0,
            prediction_y=0.0,
            ground_truth_x=0.0,
            ground_truth_y=0.0,
            confidence=0.9,
            innovation_x=0.0,
            innovation_y=0.0,
            mahalanobis_distance=1.0,
            motion_consistency=0.9,
            velocity_x=0.0,
            velocity_y=0.0,
            camera_angle_x=0.0,
            camera_angle_y=0.0,
            camera_command_x=0.0,
            camera_command_y=0.0,
            processing_time=0.001
        )
        
        # Then in LOCKED
        calculator.record(
            timestamp=0.10,
            frame_id=2,
            state=TrackingMode.LOCKED,
            measurement_x=320.0,
            measurement_y=240.0,
            prediction_x=0.0,
            prediction_y=0.0,
            ground_truth_x=0.0,
            ground_truth_y=0.0,
            confidence=0.9,
            innovation_x=0.0,
            innovation_y=0.0,
            mahalanobis_distance=1.0,
            motion_consistency=0.9,
            velocity_x=0.0,
            velocity_y=0.0,
            camera_angle_x=0.0,
            camera_angle_y=0.0,
            camera_command_x=0.0,
            camera_command_y=0.0,
            processing_time=0.001
        )
        
        # Then transition to LOST
        calculator.record(
            timestamp=0.15,
            frame_id=3,
            state=TrackingMode.LOST,
            measurement_x=None,
            measurement_y=None,
            prediction_x=0.0,
            prediction_y=0.0,
            ground_truth_x=0.0,
            ground_truth_y=0.0,
            confidence=0.0,
            innovation_x=0.0,
            innovation_y=0.0,
            mahalanobis_distance=1.0,
            motion_consistency=0.9,
            velocity_x=0.0,
            velocity_y=0.0,
            camera_angle_x=0.0,
            camera_angle_y=0.0,
            camera_command_x=0.0,
            camera_command_y=0.0,
            processing_time=0.001
        )
        
        # Transition to SEARCH to trigger LOST duration recording
        calculator.record(
            timestamp=0.20,
            frame_id=4,
            state=TrackingMode.SEARCH,
            measurement_x=None,
            measurement_y=None,
            prediction_x=0.0,
            prediction_y=0.0,
            ground_truth_x=0.0,
            ground_truth_y=0.0,
            confidence=0.0,
            innovation_x=0.0,
            innovation_y=0.0,
            mahalanobis_distance=1.0,
            motion_consistency=0.9,
            velocity_x=0.0,
            velocity_y=0.0,
            camera_angle_x=0.0,
            camera_angle_y=0.0,
            camera_command_x=0.0,
            camera_command_y=0.0,
            processing_time=0.001
        )
        
        summary = calculator.calculate_summary()
        
        # LOCKED->LOST should count as a loss event
        assert summary.loss_events == 1
    
    def test_reacquisition_events(self, calculator):
        """Test reacquisition event counting."""
        calculator.start_experiment(0.0)
        
        # First in SEARCH
        calculator.record(
            timestamp=0.05,
            frame_id=1,
            state=TrackingMode.SEARCH,
            measurement_x=320.0,
            measurement_y=240.0,
            prediction_x=0.0,
            prediction_y=0.0,
            ground_truth_x=0.0,
            ground_truth_y=0.0,
            confidence=0.9,
            innovation_x=0.0,
            innovation_y=0.0,
            mahalanobis_distance=1.0,
            motion_consistency=0.9,
            velocity_x=0.0,
            velocity_y=0.0,
            camera_angle_x=0.0,
            camera_angle_y=0.0,
            camera_command_x=0.0,
            camera_command_y=0.0,
            processing_time=0.001
        )
        
        # LOCKED (initial acquisition)
        calculator.record(
            timestamp=0.10,
            frame_id=2,
            state=TrackingMode.LOCKED,
            measurement_x=320.0,
            measurement_y=240.0,
            prediction_x=0.0,
            prediction_y=0.0,
            ground_truth_x=0.0,
            ground_truth_y=0.0,
            confidence=0.9,
            innovation_x=0.0,
            innovation_y=0.0,
            mahalanobis_distance=1.0,
            motion_consistency=0.9,
            velocity_x=0.0,
            velocity_y=0.0,
            camera_angle_x=0.0,
            camera_angle_y=0.0,
            camera_command_x=0.0,
            camera_command_y=0.0,
            processing_time=0.001
        )
        
        # LOST
        calculator.record(
            timestamp=0.15,
            frame_id=3,
            state=TrackingMode.LOST,
            measurement_x=None,
            measurement_y=None,
            prediction_x=0.0,
            prediction_y=0.0,
            ground_truth_x=0.0,
            ground_truth_y=0.0,
            confidence=0.0,
            innovation_x=0.0,
            innovation_y=0.0,
            mahalanobis_distance=1.0,
            motion_consistency=0.9,
            velocity_x=0.0,
            velocity_y=0.0,
            camera_angle_x=0.0,
            camera_angle_y=0.0,
            camera_command_x=0.0,
            camera_command_y=0.0,
            processing_time=0.001
        )
        
        # SEARCH during reacquisition
        calculator.record(
            timestamp=0.20,
            frame_id=4,
            state=TrackingMode.SEARCH,
            measurement_x=None,
            measurement_y=None,
            prediction_x=0.0,
            prediction_y=0.0,
            ground_truth_x=0.0,
            ground_truth_y=0.0,
            confidence=0.0,
            innovation_x=0.0,
            innovation_y=0.0,
            mahalanobis_distance=1.0,
            motion_consistency=0.9,
            velocity_x=0.0,
            velocity_y=0.0,
            camera_angle_x=0.0,
            camera_angle_y=0.0,
            camera_command_x=0.0,
            camera_command_y=0.0,
            processing_time=0.001
        )
        
        # Reacquisition to LOCKED
        calculator.record(
            timestamp=0.25,
            frame_id=5,
            state=TrackingMode.LOCKED,
            measurement_x=320.0,
            measurement_y=240.0,
            prediction_x=0.0,
            prediction_y=0.0,
            ground_truth_x=0.0,
            ground_truth_y=0.0,
            confidence=0.9,
            innovation_x=0.0,
            innovation_y=0.0,
            mahalanobis_distance=1.0,
            motion_consistency=0.9,
            velocity_x=0.0,
            velocity_y=0.0,
            camera_angle_x=0.0,
            camera_angle_y=0.0,
            camera_command_x=0.0,
            camera_command_y=0.0,
            processing_time=0.001
        )
        
        # Transition to COASTING to trigger event recording
        calculator.record(
            timestamp=0.30,
            frame_id=6,
            state=TrackingMode.COASTING,
            measurement_x=None,
            measurement_y=None,
            prediction_x=0.0,
            prediction_y=0.0,
            ground_truth_x=0.0,
            ground_truth_y=0.0,
            confidence=0.0,
            innovation_x=0.0,
            innovation_y=0.0,
            mahalanobis_distance=1.0,
            motion_consistency=0.9,
            velocity_x=0.0,
            velocity_y=0.0,
            camera_angle_x=0.0,
            camera_angle_y=0.0,
            camera_command_x=0.0,
            camera_command_y=0.0,
            processing_time=0.001
        )
        
        summary = calculator.calculate_summary()
        
        # Should have 1 reacquisition event (LOST/SEARCH -> LOCKED)
        assert summary.reacquisition_events == 1
        assert summary.reacquisition_time is not None
        assert summary.reacquisition_time == 0.10  # 0.25 - 0.15
        # Should have 1 lock event (SEARCH->LOCKED during reacquisition counts)
        assert summary.lock_events == 1
    
    def test_processing_time_metrics(self, calculator):
        """Test processing time metrics."""
        calculator.start_experiment(0.0)
        
        processing_times = [0.001, 0.002, 0.003]
        for i, pt in enumerate(processing_times):
            calculator.record(
                timestamp=0.05 * (i + 1),
                frame_id=i + 1,
                state=TrackingMode.LOCKED,
                measurement_x=320.0,
                measurement_y=240.0,
                prediction_x=0.0,
                prediction_y=0.0,
                ground_truth_x=0.0,
                ground_truth_y=0.0,
                confidence=0.9,
                innovation_x=0.0,
                innovation_y=0.0,
                mahalanobis_distance=1.0,
                motion_consistency=0.9,
                velocity_x=0.0,
                velocity_y=0.0,
                camera_angle_x=0.0,
                camera_angle_y=0.0,
                camera_command_x=0.0,
                camera_command_y=0.0,
                processing_time=pt
            )
        
        summary = calculator.calculate_summary()
        
        # Average should be 0.002
        assert abs(summary.avg_processing_time - 0.002) < 0.0001
        # Max should be 0.003
        assert summary.max_processing_time == 0.003
    
    def test_effective_fps(self, calculator):
        """Test effective FPS calculation."""
        calculator.start_experiment(0.0)
        
        # Record 10 frames over 0.5 seconds
        for i in range(10):
            calculator.record(
                timestamp=0.05 * (i + 1),
                frame_id=i + 1,
                state=TrackingMode.LOCKED,
                measurement_x=320.0,
                measurement_y=240.0,
                prediction_x=0.0,
                prediction_y=0.0,
                ground_truth_x=0.0,
                ground_truth_y=0.0,
                confidence=0.9,
                innovation_x=0.0,
                innovation_y=0.0,
                mahalanobis_distance=1.0,
                motion_consistency=0.9,
                velocity_x=0.0,
                velocity_y=0.0,
                camera_angle_x=0.0,
                camera_angle_y=0.0,
                camera_command_x=0.0,
                camera_command_y=0.0,
                processing_time=0.001
            )
        
        summary = calculator.calculate_summary()
        
        # FPS should be 10 / 0.5 = 20 Hz
        assert abs(summary.effective_fps - 20.0) < 0.1
    
    def test_save_json(self, calculator, tmp_path):
        """Test JSON saving."""
        calculator.start_experiment(0.0)
        
        calculator.record(
            timestamp=0.05,
            frame_id=1,
            state=TrackingMode.LOCKED,
            measurement_x=320.0,
            measurement_y=240.0,
            prediction_x=0.0,
            prediction_y=0.0,
            ground_truth_x=0.0,
            ground_truth_y=0.0,
            confidence=0.9,
            innovation_x=0.0,
            innovation_y=0.0,
            mahalanobis_distance=1.0,
            motion_consistency=0.9,
            velocity_x=0.0,
            velocity_y=0.0,
            camera_angle_x=0.0,
            camera_angle_y=0.0,
            camera_command_x=0.0,
            camera_command_y=0.0,
            processing_time=0.001
        )
        
        output_file = tmp_path / "test_metrics.json"
        calculator.save_json(str(output_file))
        
        assert output_file.exists()
        
        with open(output_file, 'r') as f:
            data = json.load(f)
        
        assert "summary" in data
        assert "records" in data
        assert len(data["records"]) == 1
    
    def test_save_csv(self, calculator, tmp_path):
        """Test CSV saving."""
        calculator.start_experiment(0.0)
        
        calculator.record(
            timestamp=0.05,
            frame_id=1,
            state=TrackingMode.LOCKED,
            measurement_x=320.0,
            measurement_y=240.0,
            prediction_x=0.0,
            prediction_y=0.0,
            ground_truth_x=0.0,
            ground_truth_y=0.0,
            confidence=0.9,
            innovation_x=0.0,
            innovation_y=0.0,
            mahalanobis_distance=1.0,
            motion_consistency=0.9,
            velocity_x=0.0,
            velocity_y=0.0,
            camera_angle_x=0.0,
            camera_angle_y=0.0,
            camera_command_x=0.0,
            camera_command_y=0.0,
            processing_time=0.001
        )
        
        output_file = tmp_path / "test_metrics.csv"
        calculator.save_csv(str(output_file))
        
        assert output_file.exists()
        
        with open(output_file, 'r') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        
        assert len(rows) == 1
    
    def test_save_summary_report(self, calculator, tmp_path):
        """Test summary report saving."""
        calculator.start_experiment(0.0)
        
        calculator.record(
            timestamp=0.05,
            frame_id=1,
            state=TrackingMode.LOCKED,
            measurement_x=320.0,
            measurement_y=240.0,
            prediction_x=0.0,
            prediction_y=0.0,
            ground_truth_x=0.0,
            ground_truth_y=0.0,
            confidence=0.9,
            innovation_x=0.0,
            innovation_y=0.0,
            mahalanobis_distance=1.0,
            motion_consistency=0.9,
            velocity_x=0.0,
            velocity_y=0.0,
            camera_angle_x=0.0,
            camera_angle_y=0.0,
            camera_command_x=0.0,
            camera_command_y=0.0,
            processing_time=0.001
        )
        
        output_file = tmp_path / "test_report.txt"
        calculator.save_summary_report(str(output_file))
        
        assert output_file.exists()
        
        with open(output_file, 'r') as f:
            content = f.read()
        
        assert "Tracking Metrics Summary Report" in content
        assert "RMSE Angular" in content
    
    def test_reset(self, calculator):
        """Test calculator reset."""
        calculator.start_experiment(0.0)
        
        calculator.record(
            timestamp=0.05,
            frame_id=1,
            state=TrackingMode.LOCKED,
            measurement_x=320.0,
            measurement_y=240.0,
            prediction_x=0.0,
            prediction_y=0.0,
            ground_truth_x=0.0,
            ground_truth_y=0.0,
            confidence=0.9,
            innovation_x=0.0,
            innovation_y=0.0,
            mahalanobis_distance=1.0,
            motion_consistency=0.9,
            velocity_x=0.0,
            velocity_y=0.0,
            camera_angle_x=0.0,
            camera_angle_y=0.0,
            camera_command_x=0.0,
            camera_command_y=0.0,
            processing_time=0.001
        )
        
        calculator.reset()
        
        assert len(calculator.records) == 0
        assert calculator.total_frames == 0
        assert calculator.experiment_start_time is None
    
    def test_no_ground_truth(self, calculator):
        """Test metrics calculation without ground truth."""
        calculator.start_experiment(0.0)
        
        calculator.record(
            timestamp=0.05,
            frame_id=1,
            state=TrackingMode.LOCKED,
            measurement_x=320.0,
            measurement_y=240.0,
            prediction_x=0.0,
            prediction_y=0.0,
            ground_truth_x=None,  # No ground truth
            ground_truth_y=None,
            confidence=0.9,
            innovation_x=0.0,
            innovation_y=0.0,
            mahalanobis_distance=1.0,
            motion_consistency=0.9,
            velocity_x=0.0,
            velocity_y=0.0,
            camera_angle_x=0.0,
            camera_angle_y=0.0,
            camera_command_x=0.0,
            camera_command_y=0.0,
            processing_time=0.001
        )
        
        summary = calculator.calculate_summary()
        
        # Errors should be zero without ground truth
        assert summary.mean_angular_error == 0.0
        assert summary.rmse_angular == 0.0
        assert summary.mean_pixel_error == 0.0