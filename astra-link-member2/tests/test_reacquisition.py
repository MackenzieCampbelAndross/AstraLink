"""Tests for reacquisition system."""

import pytest
import numpy as np

from astra_link_tracking.reacquisition.predictor import TrajectoryPredictor
from astra_link_tracking.reacquisition.levy_search import LevySearch
from astra_link_tracking.reacquisition.raster_search import RasterSearch
from astra_link_tracking.reacquisition.reacquisition_controller import ReacquisitionController
from astra_link_tracking.models.config import ReacquisitionConfig, ControlConfig, TrackingConfig
from astra_link_tracking.models.interfaces import DetectionResult, TrackingMode


class TestTrajectoryPredictor:
    """Test suite for trajectory predictor."""
    
    @pytest.fixture
    def reacq_config(self):
        """Create reacquisition configuration."""
        return ReacquisitionConfig(
            initial_search_radius=0.5,
            maximum_search_radius=2.0,
            levy_alpha=1.5,
            levy_min_step=0.01,
            levy_max_step=0.5,
            raster_grid_spacing=0.1,
            raster_search_radius=1.0,
            timeout=10.0
        )
    
    @pytest.fixture
    def predictor(self, reacq_config):
        """Create trajectory predictor instance."""
        return TrajectoryPredictor(reacq_config)
    
    def test_initialization(self, predictor, reacq_config):
        """Test predictor initialization."""
        assert predictor.config == reacq_config
        assert predictor.last_position is None
        assert predictor.last_velocity is None
        assert predictor.last_timestamp is None
    
    def test_update_state(self, predictor):
        """Test updating predictor state."""
        predictor.update_state((1.0, 2.0), (0.5, 0.3), 1.0)
        
        assert predictor.last_position == (1.0, 2.0)
        assert predictor.last_velocity == (0.5, 0.3)
        assert predictor.last_timestamp == 1.0
    
    def test_predict_position(self, predictor):
        """Test position prediction."""
        predictor.update_state((0.0, 0.0), (1.0, 0.5), 0.0)
        
        pred = predictor.predict_position(1.0)
        
        assert pred == (1.0, 0.5)  # Position + velocity * time
    
    def test_predict_position_no_state(self, predictor):
        """Test prediction without state."""
        pred = predictor.predict_position(1.0)
        
        assert pred == (0.0, 0.0)  # Default
    
    def test_get_search_region(self, predictor):
        """Test search region calculation."""
        predictor.update_state((0.0, 0.0), (1.0, 0.5), 0.0)
        
        covariance = np.eye(2) * 0.1
        region = predictor.get_search_region(covariance, 0.5)
        
        (min_x, min_y), (max_x, max_y) = region
        
        # Region should be centered at predicted position
        center_x = (min_x + max_x) / 2
        center_y = (min_y + max_y) / 2
        
        assert abs(center_x - 0.5) < 0.1  # Predicted position
        assert abs(center_y - 0.25) < 0.1
    
    def test_search_region_minimum_radius(self, predictor):
        """Test minimum search radius."""
        predictor.update_state((0.0, 0.0), (0.0, 0.0), 0.0)
        
        # Very small covariance
        covariance = np.eye(2) * 0.001
        region = predictor.get_search_region(covariance, 0.5)
        
        (min_x, min_y), (max_x, max_y) = region
        
        # Should use minimum radius
        width = max_x - min_x
        assert width >= 2 * predictor.config.initial_search_radius
    
    def test_search_region_maximum_radius(self, predictor):
        """Test maximum search radius."""
        predictor.update_state((0.0, 0.0), (0.0, 0.0), 0.0)
        
        # Very large covariance
        covariance = np.eye(2) * 100.0
        region = predictor.get_search_region(covariance, 0.5)
        
        (min_x, min_y), (max_x, max_y) = region
        
        # Should use maximum radius
        width = max_x - min_x
        assert width <= 2 * predictor.config.maximum_search_radius
    
    def test_reset(self, predictor):
        """Test predictor reset."""
        predictor.update_state((1.0, 2.0), (0.5, 0.3), 1.0)
        predictor.reset()
        
        assert predictor.last_position is None
        assert predictor.last_velocity is None
        assert predictor.last_timestamp is None


class TestLevySearch:
    """Test suite for Lévy search."""
    
    @pytest.fixture
    def reacq_config(self):
        """Create reacquisition configuration."""
        return ReacquisitionConfig(
            initial_search_radius=0.5,
            maximum_search_radius=2.0,
            levy_alpha=1.5,
            levy_min_step=0.01,
            levy_max_step=0.5,
            raster_grid_spacing=0.1,
            raster_search_radius=1.0,
            timeout=10.0
        )
    
    @pytest.fixture
    def levy_search(self, reacq_config):
        """Create Lévy search instance."""
        return LevySearch(reacq_config, seed=42)
    
    def test_initialization(self, levy_search, reacq_config):
        """Test Lévy search initialization."""
        assert levy_search.config == reacq_config
        assert levy_search.alpha == 1.5
        assert levy_search.min_step == 0.01
        assert levy_search.max_step == 0.5
        assert levy_search.seed == 42
    
    def test_generate_step(self, levy_search):
        """Test step generation."""
        dx, dy = levy_search.generate_step()
        
        assert isinstance(dx, float)
        assert isinstance(dy, float)
        # Step should be within reasonable bounds
        assert abs(dx) <= levy_search.max_step
        assert abs(dy) <= levy_search.max_step
    
    def test_step_clamped_to_max(self, levy_search):
        """Test that steps are clamped to maximum."""
        # Generate many steps
        steps = [levy_search.generate_step() for _ in range(100)]
        
        for dx, dy in steps:
            assert abs(dx) <= levy_search.max_step
            assert abs(dy) <= levy_search.max_step
    
    def test_get_next_position(self, levy_search):
        """Test getting next position."""
        start = (0.0, 0.0)
        next_pos = levy_search.get_next_position(start)
        
        assert next_pos != start
        assert levy_search.current_position == next_pos
    
    def test_deterministic_behavior(self, reacq_config):
        """Test that search is deterministic with seed."""
        levy1 = LevySearch(reacq_config, seed=42)
        levy2 = LevySearch(reacq_config, seed=42)
        
        start = (0.0, 0.0)
        pos1 = levy1.get_next_position(start)
        levy1.reset(start)  # Reset to same state
        pos1_again = levy1.get_next_position(start)
        
        # Same instance should produce same result after reset
        assert pos1 == pos1_again
    
    def test_reset(self, levy_search):
        """Test search reset."""
        levy_search.get_next_position((0.0, 0.0))
        levy_search.reset((1.0, 1.0))
        
        assert levy_search.current_position == (1.0, 1.0)
        assert levy_search.step_count == 0
    
    def test_get_step_count(self, levy_search):
        """Test step count."""
        assert levy_search.get_step_count() == 0
        
        levy_search.get_next_position((0.0, 0.0))
        assert levy_search.get_step_count() == 1
        
        levy_search.get_next_position((0.0, 0.0))
        assert levy_search.get_step_count() == 2


class TestRasterSearch:
    """Test suite for raster search."""
    
    @pytest.fixture
    def reacq_config(self):
        """Create reacquisition configuration."""
        return ReacquisitionConfig(
            initial_search_radius=0.5,
            maximum_search_radius=2.0,
            levy_alpha=1.5,
            levy_min_step=0.01,
            levy_max_step=0.5,
            raster_grid_spacing=0.1,
            raster_search_radius=1.0,
            timeout=10.0
        )
    
    @pytest.fixture
    def raster_search(self, reacq_config):
        """Create raster search instance."""
        return RasterSearch(reacq_config)
    
    def test_initialization(self, raster_search, reacq_config):
        """Test raster search initialization."""
        assert raster_search.config == reacq_config
        assert raster_search.grid_spacing == 0.1
        assert raster_search.search_radius == 1.0
    
    def test_generate_search_path(self, raster_search):
        """Test search path generation."""
        path = raster_search.generate_search_path((0.0, 0.0))
        
        assert len(path) > 0
        assert all(isinstance(pos, tuple) and len(pos) == 2 for pos in path)
    
    def test_search_path_coverage(self, raster_search):
        """Test that path covers the search region."""
        path = raster_search.generate_search_path((0.0, 0.0))
        
        # Check that path has reasonable length
        assert len(path) > 10
        
        # Check that path is within bounds
        for x, y in path:
            assert abs(x) <= raster_search.search_radius + 0.1
            assert abs(y) <= raster_search.search_radius + 0.1
    
    def test_get_next_position(self, raster_search):
        """Test getting next position."""
        raster_search.reset((0.0, 0.0))
        
        pos1 = raster_search.get_next_position()
        pos2 = raster_search.get_next_position()
        
        assert pos1 != pos2
        assert raster_search.current_position == pos2
    
    def test_reset(self, raster_search):
        """Test search reset."""
        raster_search.reset((0.0, 0.0))
        raster_search.get_next_position()
        
        raster_search.reset((1.0, 1.0))
        
        assert raster_search.current_position == (1.0, 1.0)
        assert raster_search.current_index == 0
    
    def test_get_progress(self, raster_search):
        """Test progress calculation."""
        raster_search.reset((0.0, 0.0))
        
        assert raster_search.get_progress() == 0.0
        
        raster_search.get_next_position()
        progress = raster_search.get_progress()
        
        assert 0.0 < progress <= 1.0
    
    def test_is_complete(self, raster_search):
        """Test completion check."""
        raster_search.reset((0.0, 0.0))
        
        assert not raster_search.is_complete()
        
        # Exhaust path
        while not raster_search.is_complete():
            raster_search.get_next_position()
        
        assert raster_search.is_complete()


class TestReacquisitionController:
    """Test suite for reacquisition controller."""
    
    @pytest.fixture
    def reacq_config(self):
        """Create reacquisition configuration."""
        return ReacquisitionConfig(
            initial_search_radius=0.5,
            maximum_search_radius=2.0,
            levy_alpha=1.5,
            levy_min_step=0.01,
            levy_max_step=0.5,
            raster_grid_spacing=0.1,
            raster_search_radius=1.0,
            timeout=10.0
        )
    
    @pytest.fixture
    def control_config(self):
        """Create control configuration."""
        return ControlConfig(
            control_rate_hz=20.0,
            max_pan_speed_deg_per_sec=5.0,
            max_tilt_speed_deg_per_sec=3.0,
            kp=1.0,
            ki=0.1,
            kd=0.01,
            feedforward_gain=0.5
        )
    
    @pytest.fixture
    def tracking_config(self):
        """Create tracking configuration."""
        return TrackingConfig(
            confidence_threshold=0.5,
            process_noise=0.1,
            measurement_noise=0.1,
            mahalanobis_threshold=9.21,
            confirmation_frames=3,
            maximum_missed_frames=5,
            maximum_covariance_threshold=100.0
        )
    
    @pytest.fixture
    def controller(self, reacq_config, control_config, tracking_config):
        """Create reacquisition controller instance."""
        return ReacquisitionController(reacq_config, control_config, tracking_config, seed=42)
    
    def test_initialization(self, controller):
        """Test controller initialization."""
        assert not controller.active
        assert controller.search_start_time is None
        assert controller.confirmation_count == 0
        assert controller.reacquisition_time is None
    
    def test_start(self, controller):
        """Test starting reacquisition."""
        position = (1.0, 2.0)
        velocity = (0.5, 0.3)
        covariance = np.eye(2) * 0.1
        
        controller.start(position, velocity, covariance, 1.0)
        
        assert controller.active
        assert controller.search_start_time == 1.0
        assert controller.last_position == position
        assert controller.last_velocity == velocity
    
    def test_step(self, controller):
        """Test search step."""
        controller.start((0.0, 0.0), (0.0, 0.0), np.eye(2) * 0.1, 1.0)
        
        target = controller.step(0.05, (0.0, 0.0))
        
        assert isinstance(target, tuple)
        assert len(target) == 2
    
    def test_step_applies_slew_limit(self, controller):
        """Test that slew limiting is applied."""
        controller.start((0.0, 0.0), (0.0, 0.0), np.eye(2) * 0.1, 1.0)
        
        # Try to move very far
        camera_pos = (0.0, 0.0)
        target = controller.step(0.05, camera_pos)
        
        # Movement should be limited by slew rate
        max_delta = controller.control_config.max_pan_speed_deg_per_sec * 0.05
        assert abs(target[0] - camera_pos[0]) <= max_delta + 1e-6
    
    def test_process_detection_visible(self, controller):
        """Test processing visible detection."""
        controller.start((0.0, 0.0), (0.0, 0.0), np.eye(2) * 0.1, 1.0)
        
        detection = DetectionResult(
            timestamp=1.0,
            frame_id=1,
            centroid_x=320.0,
            centroid_y=240.0,
            confidence=0.9,
            visible=True
        )
        
        estimated_state = np.array([0.0, 0.0, 0.0, 0.0])
        estimated_covariance = np.eye(4) * 0.1
        
        result = controller.process_detection(
            detection, estimated_state, estimated_covariance, 1.0
        )
        
        # Should increment confirmation count
        assert controller.confirmation_count > 0
    
    def test_process_detection_invisible(self, controller):
        """Test processing invisible detection."""
        controller.start((0.0, 0.0), (0.0, 0.0), np.eye(2) * 0.1, 1.0)
        
        detection = DetectionResult(
            timestamp=1.0,
            frame_id=1,
            centroid_x=None,
            centroid_y=None,
            confidence=0.0,
            visible=False
        )
        
        estimated_state = np.array([0.0, 0.0, 0.0, 0.0])
        estimated_covariance = np.eye(4) * 0.1
        
        result = controller.process_detection(
            detection, estimated_state, estimated_covariance, 1.0
        )
        
        # Should not increment confirmation count
        assert controller.confirmation_count == 0
        assert not result
    
    def test_process_detection_low_confidence(self, controller):
        """Test processing low-confidence detection."""
        controller.start((0.0, 0.0), (0.0, 0.0), np.eye(2) * 0.1, 1.0)
        
        detection = DetectionResult(
            timestamp=1.0,
            frame_id=1,
            centroid_x=320.0,
            centroid_y=240.0,
            confidence=0.3,  # Below threshold
            visible=True
        )
        
        estimated_state = np.array([0.0, 0.0, 0.0, 0.0])
        estimated_covariance = np.eye(4) * 0.1
        
        result = controller.process_detection(
            detection, estimated_state, estimated_covariance, 1.0
        )
        
        # Should not increment confirmation count
        assert controller.confirmation_count == 0
        assert not result
    
    def test_confirmation_requirement(self, controller):
        """Test that confirmation frames are required."""
        controller.start((0.0, 0.0), (0.0, 0.0), np.eye(2) * 0.1, 1.0)
        
        detection = DetectionResult(
            timestamp=1.0,
            frame_id=1,
            centroid_x=320.0,
            centroid_y=240.0,
            confidence=0.9,
            visible=True
        )
        
        estimated_state = np.array([0.0, 0.0, 0.0, 0.0])
        estimated_covariance = np.eye(4) * 0.1
        
        # Process detection multiple times
        for i in range(2):
            result = controller.process_detection(
                detection, estimated_state, estimated_covariance, 1.0 + i * 0.05
            )
        
        # Should not be confirmed yet (need 3 frames)
        assert not result
        
        # One more frame
        result = controller.process_detection(
            detection, estimated_state, estimated_covariance, 1.2
        )
        
        # Should be confirmed
        assert result
        assert controller.is_complete()
    
    def test_reset(self, controller):
        """Test controller reset."""
        controller.start((0.0, 0.0), (0.0, 0.0), np.eye(2) * 0.1, 1.0)
        controller.reset()
        
        assert not controller.active
        assert controller.search_start_time is None
        assert controller.confirmation_count == 0
        assert controller.reacquisition_time is None
    
    def test_current_search_position(self, controller):
        """Test getting current search position."""
        controller.start((0.0, 0.0), (0.0, 0.0), np.eye(2) * 0.1, 1.0)
        
        pos = controller.get_current_search_position()
        
        assert isinstance(pos, tuple)
        assert len(pos) == 2
    
    def test_is_active(self, controller):
        """Test active status."""
        assert not controller.is_active()
        
        controller.start((0.0, 0.0), (0.0, 0.0), np.eye(2) * 0.1, 1.0)
        
        assert controller.is_active()
    
    def test_is_complete(self, controller):
        """Test completion status."""
        assert not controller.is_complete()
        
        controller.start((0.0, 0.0), (0.0, 0.0), np.eye(2) * 0.1, 1.0)
        
        assert not controller.is_complete()
    
    def test_get_reacquisition_time(self, controller):
        """Test getting reacquisition time."""
        assert controller.get_reacquisition_time() is None
        
        controller.start((0.0, 0.0), (0.0, 0.0), np.eye(2) * 0.1, 1.0)
        
        # Simulate successful reacquisition
        detection = DetectionResult(
            timestamp=1.0,
            frame_id=1,
            centroid_x=320.0,
            centroid_y=240.0,
            confidence=0.9,
            visible=True
        )
        
        estimated_state = np.array([0.0, 0.0, 0.0, 0.0])
        estimated_covariance = np.eye(4) * 0.1
        
        for i in range(3):
            controller.process_detection(
                detection, estimated_state, estimated_covariance, 1.0 + i * 0.05
            )
        
        time = controller.get_reacquisition_time()
        
        assert time is not None
        assert time > 0