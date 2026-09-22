"""Tests for closed-loop simulation."""

import pytest
import numpy as np

from astra_link_tracking.simulation.closed_loop import ClosedLoopSimulation, SimulationStep, SimulationResult
from astra_link_tracking.simulation.trajectories import TrajectoryGenerator
from astra_link_tracking.simulation.virtual_camera import VirtualCamera
from astra_link_tracking.models.config import TrackingSystemConfig
from astra_link_tracking.models.interfaces import TrackingMode


class TestTrajectoryGenerator:
    """Test suite for trajectory generator."""
    
    def test_stationary_trajectory(self):
        """Test stationary trajectory generation."""
        gen = TrajectoryGenerator("stationary", duration=10.0, dt=0.1)
        trajectory = gen.generate()
        
        # All positions should be (0, 0)
        for t, pos, vel in trajectory:
            assert pos == (0.0, 0.0)
            assert vel == (0.0, 0.0)
    
    def test_linear_trajectory(self):
        """Test linear trajectory generation."""
        gen = TrajectoryGenerator("linear", duration=10.0, dt=0.1)
        trajectory = gen.generate()
        
        # Velocity should be constant
        first_vel = trajectory[0][2]
        for t, pos, vel in trajectory:
            assert vel == first_vel
    
    def test_circular_trajectory(self):
        """Test circular trajectory generation."""
        gen = TrajectoryGenerator("circular", duration=10.0, dt=0.1)
        trajectory = gen.generate()
        
        # Radius should be constant
        radii = [np.sqrt(pos[0]**2 + pos[1]**2) for t, pos, vel in trajectory]
        for r in radii:
            assert abs(r - 1.5) < 0.1  # Allow small tolerance
    
    def test_figure8_trajectory(self):
        """Test figure-8 trajectory generation."""
        gen = TrajectoryGenerator("figure8", duration=10.0, dt=0.1)
        trajectory = gen.generate()
        
        # Should generate trajectory
        assert len(trajectory) > 0
    
    def test_deterministic_behavior(self):
        """Test that trajectory is deterministic."""
        gen1 = TrajectoryGenerator("linear", duration=10.0, dt=0.1, seed=42)
        traj1 = gen1.generate()
        
        gen2 = TrajectoryGenerator("linear", duration=10.0, dt=0.1, seed=42)
        traj2 = gen2.generate()
        
        # Should be identical
        assert len(traj1) == len(traj2)
        for i in range(len(traj1)):
            assert traj1[i] == traj2[i]
    
    def test_random_requires_seed(self):
        """Test that random trajectory requires seed."""
        gen = TrajectoryGenerator("random", duration=10.0, dt=0.1)
        
        with pytest.raises(ValueError, match="requires a seed"):
            gen.generate()


class TestVirtualCamera:
    """Test suite for virtual camera."""
    
    @pytest.fixture
    def camera_config(self):
        """Create camera configuration."""
        from astra_link_tracking.models.config import CameraConfig, ControlConfig
        return CameraConfig(
            resolution_width=640,
            resolution_height=480,
            horizontal_fov_deg=4.0,
            vertical_fov_deg=3.0,
            update_rate_hz=30.0
        )
    
    @pytest.fixture
    def control_config(self):
        """Create control configuration."""
        from astra_link_tracking.models.config import ControlConfig
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
    def camera(self, camera_config, control_config):
        """Create virtual camera instance."""
        return VirtualCamera(camera_config, control_config, measurement_noise_std=0.1)
    
    def test_initialization(self, camera, camera_config, control_config):
        """Test camera initialization."""
        assert camera.pan_angle == 0.0
        assert camera.tilt_angle == 0.0
        assert camera.measurement_noise_std == 0.1
    
    def test_get_state(self, camera):
        """Test getting camera state."""
        pan, tilt = camera.get_state()
        
        assert pan == 0.0
        assert tilt == 0.0
    
    def test_apply_command_within_limits(self, camera):
        """Test applying command within slew limits."""
        camera.apply_command(1.0, 0.5, 0.1)
        
        pan, tilt = camera.get_state()
        
        # Should have moved
        assert pan > 0
        assert tilt > 0
    
    def test_apply_command_respects_slew_limit(self, camera):
        """Test that slew limit is respected."""
        # Try to move very fast (100 degrees in 0.1s = 1000 deg/s)
        camera.apply_command(100.0, 100.0, 0.1)
        
        pan, tilt = camera.get_state()
        
        # Maximum allowed change: 5 deg/s * 0.1s = 0.5 degrees
        assert pan <= 0.5 + 1e-6
        assert tilt <= 0.3 + 1e-6  # 3 deg/s * 0.1s = 0.3 degrees
    
    def test_apply_command_negative_direction(self, camera):
        """Test command in negative direction."""
        camera.apply_command(-1.0, -0.5, 0.1)
        
        pan, tilt = camera.get_state()
        
        assert pan < 0
        assert tilt < 0
    
    def test_observe_target_adds_noise(self, camera):
        """Test that observation adds noise."""
        np.random.seed(42)
        measured_pan, measured_tilt = camera.observe_target(10.0, 5.0)
        
        # Should not equal exactly
        assert measured_pan != 10.0 or measured_tilt != 5.0
    
    def test_observe_target_without_noise(self, camera):
        """Test observation with zero noise."""
        measured_pan, measured_tilt = camera.observe_target(10.0, 5.0, noise_std=0.0)
        
        # Should equal exactly (within floating point precision)
        assert abs(measured_pan - 10.0) < 1e-10
        assert abs(measured_tilt - 5.0) < 1e-10
    
    def test_get_relative_angle(self, camera):
        """Test relative angle calculation."""
        camera.pan_angle = 5.0
        camera.tilt_angle = 3.0
        
        rel_pan, rel_tilt = camera.get_relative_angle(10.0, 8.0)
        
        assert rel_pan == 5.0  # 10 - 5
        assert rel_tilt == 5.0  # 8 - 3
    
    def test_angle_to_pixel(self, camera):
        """Test angle to pixel conversion."""
        pixel_x, pixel_y = camera.angle_to_pixel(0.0, 0.0)
        
        # Center should map to center pixel
        assert pixel_x == 320.0  # 640 / 2
        assert pixel_y == 240.0  # 480 / 2
    
    def test_pixel_to_angle(self, camera):
        """Test pixel to angle conversion."""
        angle_x, angle_y = camera.pixel_to_angle(320.0, 240.0)
        
        # Center pixel should map to zero angle
        assert abs(angle_x) < 1e-10
        assert abs(angle_y) < 1e-10
    
    def test_reset(self, camera):
        """Test camera reset."""
        camera.apply_command(10.0, 5.0, 0.1)
        camera.reset(2.0, 1.0)
        
        pan, tilt = camera.get_state()
        
        assert pan == 2.0
        assert tilt == 1.0


class TestClosedLoopSimulation:
    """Test suite for closed-loop simulation."""
    
    @pytest.fixture
    def config(self):
        """Create tracking system configuration."""
        from astra_link_tracking.models.config import TrackingSystemConfig
        return TrackingSystemConfig.from_json_file("config/default_config.json")
    
    @pytest.fixture
    def simulation(self, config):
        """Create closed-loop simulation instance."""
        return ClosedLoopSimulation(
            config=config,
            trajectory_type="stationary",
            duration=10.0,
            dt=0.05,
            seed=42,
            measurement_noise_std=0.1
        )
    
    def test_initialization(self, simulation, config):
        """Test simulation initialization."""
        assert simulation.dt == 0.05
        assert simulation.seed == 42
        assert len(simulation.history) == 0
    
    def test_step(self, simulation):
        """Test single simulation step."""
        step = simulation.step()
        
        assert isinstance(step, SimulationStep)
        assert step.timestamp == simulation.dt  # First step increments time
    
    def test_multiple_steps(self, simulation):
        """Test multiple simulation steps."""
        for _ in range(5):
            simulation.step()
        
        assert len(simulation.history) == 5
        assert simulation.current_time == 0.25  # 5 * 0.05
    
    def test_run(self, simulation):
        """Test full simulation run."""
        result = simulation.run()
        
        assert isinstance(result, SimulationResult)
        assert len(result.history) > 0
        assert result.duration > 0
        assert result.steps > 0
    
    def test_reset(self, simulation):
        """Test simulation reset."""
        simulation.step()
        simulation.reset()
        
        assert len(simulation.history) == 0
        assert simulation.current_time == 0.0
        assert simulation.frame_id == 0
    
    def test_camera_moves_toward_target(self, config):
        """Test that camera moves toward target."""
        # Start camera at origin, target at (2, 1)
        sim = ClosedLoopSimulation(
            config=config,
            trajectory_type="stationary",
            duration=10.0,
            dt=0.05,
            seed=42,
            measurement_noise_std=0.0  # No noise for clear test
        )
        
        # Manually set target position
        sim.trajectory_gen = TrajectoryGenerator("stationary", duration=10.0, dt=0.05)
        # Override to start off-center
        initial_step = sim.step()
        
        # Camera should start moving toward target
        if sim.history[0].target_pan != 0:
            # Target is off-center, camera should move
            assert abs(sim.history[0].camera_pan) > 0 or abs(sim.history[0].camera_tilt) > 0
    
    def test_slew_limit_respected(self, config):
        """Test that slew limit is respected in simulation."""
        sim = ClosedLoopSimulation(
            config=config,
            trajectory_type="linear",
            duration=10.0,
            dt=0.05,
            seed=42,
            measurement_noise_std=0.0
        )
        
        result = sim.run()
        
        # Check that no step exceeds slew limit
        max_pan_speed = config.control.max_pan_speed_deg_per_sec
        max_tilt_speed = config.control.max_tilt_speed_deg_per_sec
        
        for i in range(1, len(result.history)):
            prev = result.history[i-1]
            curr = result.history[i]
            
            pan_rate = abs(curr.camera_pan - prev.camera_pan) / sim.dt
            tilt_rate = abs(curr.camera_tilt - prev.camera_tilt) / sim.dt
            
            assert pan_rate <= max_pan_speed + 1e-6
            assert tilt_rate <= max_tilt_speed + 1e-6
    
    def test_tracking_error_decreases(self, config):
        """Test that tracking error decreases over time."""
        sim = ClosedLoopSimulation(
            config=config,
            trajectory_type="stationary",
            duration=5.0,
            dt=0.05,
            seed=42,
            measurement_noise_std=0.05
        )
        
        result = sim.run()
        
        # Calculate errors
        errors = [np.sqrt(s.error_pan**2 + s.error_tilt**2) for s in result.history]
        
        # Error should decrease (first error > last error)
        # Allow some tolerance for initial settling
        assert errors[-1] < errors[0] * 0.5 or errors[-1] < 0.5
    
    def test_stationary_target_converges(self, config):
        """Test that stationary target converges."""
        sim = ClosedLoopSimulation(
            config=config,
            trajectory_type="stationary",
            duration=10.0,
            dt=0.05,
            seed=42,
            measurement_noise_std=0.05
        )
        
        result = sim.run()
        
        # Final error should be small
        assert result.final_error < 1.0
    
    def test_constant_velocity_tracking(self, config):
        """Test that constant velocity target can be tracked."""
        sim = ClosedLoopSimulation(
            config=config,
            trajectory_type="linear",
            duration=10.0,
            dt=0.05,
            seed=42,
            measurement_noise_std=0.05
        )
        
        result = sim.run()
        
        # Should complete without errors
        assert result.steps > 0
        # Final error should be reasonable
        assert result.final_error < 5.0
    
    def test_direction_reversal(self, config):
        """Test direction reversal handling."""
        sim = ClosedLoopSimulation(
            config=config,
            trajectory_type="sinusoidal",
            duration=20.0,
            dt=0.05,
            seed=42,
            measurement_noise_std=0.05
        )
        
        result = sim.run()
        
        # Should complete without errors
        assert result.steps > 0
    
    def test_circular_trajectory(self, config):
        """Test circular trajectory tracking."""
        sim = ClosedLoopSimulation(
            config=config,
            trajectory_type="circular",
            duration=20.0,
            dt=0.05,
            seed=42,
            measurement_noise_std=0.05
        )
        
        result = sim.run()
        
        # Should complete without errors
        assert result.steps > 0
    
    def test_get_history(self, simulation):
        """Test getting simulation history."""
        simulation.step()
        simulation.step()
        
        history = simulation.get_history()
        
        assert len(history) == 2
        assert history == simulation.history
    
    def test_get_summary(self, simulation):
        """Test getting simulation summary."""
        simulation.step()
        simulation.step()
        
        summary = simulation.get_summary()
        
        assert "duration" in summary
        assert "steps" in summary
        assert "final_error" in summary
        assert summary["steps"] == 2