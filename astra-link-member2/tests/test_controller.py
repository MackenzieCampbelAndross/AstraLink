"""Comprehensive tests for camera controller."""

import pytest

from astra_link_tracking.control.controller import CameraController, ControlDiagnostics
from astra_link_tracking.models.interfaces import TrackingMode, CameraCommand
from astra_link_tracking.models.config import ControlConfig


class TestCameraController:
    """Test suite for camera controller."""
    
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
    def controller(self, control_config):
        """Create camera controller instance."""
        return CameraController(control_config)
    
    def test_initialization(self, controller, control_config):
        """Test controller initialization."""
        assert controller.pan_pid.kp == control_config.kp
        assert controller.tilt_pid.kp == control_config.kp
        assert controller.feedforward.gain == control_config.feedforward_gain
        assert controller.slew_limiters.pan_limiter.max_rate == control_config.max_pan_speed_deg_per_sec
        assert controller.slew_limiters.tilt_limiter.max_rate == control_config.max_tilt_speed_deg_per_sec
    
    def test_static_target(self, controller):
        """Test static target tracking."""
        target_pan = 10.0
        target_tilt = 5.0
        velocity_x = 0.0
        velocity_y = 0.0
        tracking_mode = TrackingMode.LOCKED
        dt = 0.05
        timestamp = 1.0
        
        # Multiple updates to converge
        for i in range(10):
            command, diagnostics = controller.update(
                target_pan, target_tilt, velocity_x, velocity_y,
                tracking_mode, dt, timestamp + i * dt
            )
        
        # Should converge toward target
        assert abs(command.pan_command - target_pan) < 1.0
        assert abs(command.tilt_command - target_tilt) < 1.0
    
    def test_constant_velocity(self, controller):
        """Test tracking constant velocity target."""
        # Target moving at constant velocity
        target_pan = 0.0
        target_tilt = 0.0
        velocity_x = 1.0  # degrees/second
        velocity_y = 0.5  # degrees/second
        tracking_mode = TrackingMode.LOCKED
        dt = 0.05
        timestamp = 1.0
        
        for i in range(20):
            # Target moves
            target_pan += velocity_x * dt
            target_tilt += velocity_y * dt
            
            command, diagnostics = controller.update(
                target_pan, target_tilt, velocity_x, velocity_y,
                tracking_mode, dt, timestamp + i * dt
            )
        
        # Should track with some lag due to PID
        assert abs(command.pan_command - target_pan) < 2.0
        assert abs(command.tilt_command - target_tilt) < 2.0
    
    def test_direction_reversal(self, controller):
        """Test direction reversal."""
        # Start with positive target
        target_pan = 10.0
        target_tilt = 5.0
        velocity_x = 0.0
        velocity_y = 0.0
        tracking_mode = TrackingMode.LOCKED
        dt = 0.05
        timestamp = 1.0
        
        # Converge to first target
        for i in range(10):
            controller.update(target_pan, target_tilt, velocity_x, velocity_y,
                           tracking_mode, dt, timestamp + i * dt)
        
        # Reverse direction
        target_pan = -10.0
        target_tilt = -5.0
        
        command, diagnostics = controller.update(
            target_pan, target_tilt, velocity_x, velocity_y,
            tracking_mode, dt, timestamp + 10 * dt
        )
        
        # Should start moving in opposite direction (check slew rate)
        assert diagnostics.slew_rate_x < 0
        assert diagnostics.slew_rate_y < 0
    
    def test_saturation(self, controller):
        """Test output saturation handling."""
        # Very large error
        target_pan = 1000.0
        target_tilt = 1000.0
        velocity_x = 0.0
        velocity_y = 0.0
        tracking_mode = TrackingMode.LOCKED
        dt = 0.05
        timestamp = 1.0
        
        command, diagnostics = controller.update(
            target_pan, target_tilt, velocity_x, velocity_y,
            tracking_mode, dt, timestamp
        )
        
        # Slew limiting should prevent instant movement
        max_delta = controller.slew_limiters.pan_limiter.max_rate * dt
        assert abs(command.pan_command - controller.current_pan) <= max_delta + 1e-6
    
    def test_integral_windup_prevention(self, controller):
        """Test integral anti-windup in full controller."""
        # Large error to drive to saturation
        target_pan = 1000.0
        target_tilt = 0.0
        velocity_x = 0.0
        velocity_y = 0.0
        tracking_mode = TrackingMode.LOCKED
        dt = 0.05
        timestamp = 1.0
        
        # Drive to saturation
        for i in range(20):
            controller.update(target_pan, target_tilt, velocity_x, velocity_y,
                           tracking_mode, dt, timestamp + i * dt)
        
        integral_before = controller.pan_pid.get_integral()
        
        # Continue with same error
        for i in range(10):
            controller.update(target_pan, target_tilt, velocity_x, velocity_y,
                           tracking_mode, dt, timestamp + 20 * dt + i * dt)
        
        # Integral should not have increased significantly due to anti-windup
        integral_after = controller.pan_pid.get_integral()
        assert integral_after <= integral_before + 1e-6
    
    def test_slew_limiting(self, controller):
        """Test independent slew limiting."""
        # Initialize at origin
        controller.reset(0.0, 0.0)
        
        # Try to move very fast
        target_pan = 100.0
        target_tilt = 100.0
        velocity_x = 0.0
        velocity_y = 0.0
        tracking_mode = TrackingMode.LOCKED
        dt = 0.05
        timestamp = 1.0
        
        command, diagnostics = controller.update(
            target_pan, target_tilt, velocity_x, velocity_y,
            tracking_mode, dt, timestamp
        )
        
        # Pan slew rate should be limited
        assert abs(diagnostics.slew_rate_x) <= controller.slew_limiters.pan_limiter.max_rate
        
        # Tilt slew rate should be limited (different limit)
        assert abs(diagnostics.slew_rate_y) <= controller.slew_limiters.tilt_limiter.max_rate
    
    def test_irregular_dt(self, controller):
        """Test irregular dt handling."""
        target_pan = 10.0
        target_tilt = 5.0
        velocity_x = 0.0
        velocity_y = 0.0
        tracking_mode = TrackingMode.LOCKED
        timestamp = 1.0
        
        # Variable dt values
        dts = [0.03, 0.07, 0.05, 0.04, 0.06]
        
        for dt in dts:
            command, diagnostics = controller.update(
                target_pan, target_tilt, velocity_x, velocity_y,
                tracking_mode, dt, timestamp
            )
            timestamp += dt
        
        # Should handle variable dt without errors
        assert command is not None
    
    def test_zero_dt_protection(self, controller):
        """Test that zero dt raises error."""
        with pytest.raises(ValueError, match="dt must be positive"):
            controller.update(10.0, 5.0, 0.0, 0.0, TrackingMode.LOCKED, 0.0, 1.0)
    
    def test_lost_state_no_control(self, controller):
        """Test that controller does not move when LOST."""
        # Initialize
        controller.reset(0.0, 0.0)
        
        target_pan = 10.0
        target_tilt = 5.0
        velocity_x = 0.0
        velocity_y = 0.0
        tracking_mode = TrackingMode.LOST
        dt = 0.05
        timestamp = 1.0
        
        command, diagnostics = controller.update(
            target_pan, target_tilt, velocity_x, velocity_y,
            tracking_mode, dt, timestamp
        )
        
        # Should hold position
        assert command.pan_command == 0.0
        assert command.tilt_command == 0.0
        assert command.command_mode == "hold"
    
    def test_lost_state_with_allow_control(self, controller):
        """Test that controller can move when LOST with allow_lost_control=True."""
        # Initialize
        controller.reset(0.0, 0.0)
        
        target_pan = 10.0
        target_tilt = 5.0
        velocity_x = 0.0
        velocity_y = 0.0
        tracking_mode = TrackingMode.LOST
        dt = 0.05
        timestamp = 1.0
        
        command, diagnostics = controller.update(
            target_pan, target_tilt, velocity_x, velocity_y,
            tracking_mode, dt, timestamp, allow_lost_control=True
        )
        
        # Should move (for reacquisition)
        assert command.pan_command != 0.0 or command.tilt_command != 0.0
        assert command.command_mode == "tracking"
    
    def test_diagnostics_structure(self, controller):
        """Test that diagnostics are properly structured."""
        command, diagnostics = controller.update(
            10.0, 5.0, 0.0, 0.0, TrackingMode.LOCKED, 0.05, 1.0
        )
        
        # Check all fields
        assert isinstance(diagnostics, ControlDiagnostics)
        assert hasattr(diagnostics, 'error_x')
        assert hasattr(diagnostics, 'error_y')
        assert hasattr(diagnostics, 'pid_x')
        assert hasattr(diagnostics, 'pid_y')
        assert hasattr(diagnostics, 'feedforward_x')
        assert hasattr(diagnostics, 'feedforward_y')
        assert hasattr(diagnostics, 'raw_x')
        assert hasattr(diagnostics, 'raw_y')
        assert hasattr(diagnostics, 'limited_x')
        assert hasattr(diagnostics, 'limited_y')
        assert hasattr(diagnostics, 'slew_rate_x')
        assert hasattr(diagnostics, 'slew_rate_y')
    
    def test_feedforward_contribution(self, controller):
        """Test that feedforward contributes to output."""
        target_pan = 10.0
        target_tilt = 5.0
        velocity_x = 2.0  # Moving right
        velocity_y = 1.0  # Moving down
        tracking_mode = TrackingMode.LOCKED
        dt = 0.05
        timestamp = 1.0
        
        command, diagnostics = controller.update(
            target_pan, target_tilt, velocity_x, velocity_y,
            tracking_mode, dt, timestamp
        )
        
        # Feedforward should contribute
        expected_ff_x = controller.feedforward.gain * velocity_x
        expected_ff_y = controller.feedforward.gain * velocity_y
        
        assert abs(diagnostics.feedforward_x - expected_ff_x) < 1e-6
        assert abs(diagnostics.feedforward_y - expected_ff_y) < 1e-6
    
    def test_command_structure(self, controller):
        """Test that CameraCommand is properly structured."""
        command, diagnostics = controller.update(
            10.0, 5.0, 0.0, 0.0, TrackingMode.LOCKED, 0.05, 1.0
        )
        
        # Check all fields
        assert isinstance(command, CameraCommand)
        assert hasattr(command, 'timestamp')
        assert hasattr(command, 'pan_command')
        assert hasattr(command, 'tilt_command')
        assert hasattr(command, 'slew_rate')
        assert hasattr(command, 'command_mode')
    
    def test_reset(self, controller):
        """Test controller reset."""
        controller.update(10.0, 5.0, 0.0, 0.0, TrackingMode.LOCKED, 0.05, 1.0)
        
        controller.reset()
        
        assert controller.current_pan == 0.0
        assert controller.current_tilt == 0.0
        assert controller.position_initialized is False
    
    def test_reset_with_initial_positions(self, controller):
        """Test reset with initial positions."""
        controller.reset(initial_pan=5.0, initial_tilt=3.0)
        
        assert controller.current_pan == 5.0
        assert controller.current_tilt == 3.0
        assert controller.position_initialized is False
    
    def test_p_only_mode(self, control_config):
        """Test P-only mode (ki=0, kd=0)."""
        control_config.ki = 0.0
        control_config.kd = 0.0
        controller = CameraController(control_config)
        
        command, diagnostics = controller.update(
            10.0, 5.0, 0.0, 0.0, TrackingMode.LOCKED, 0.05, 1.0
        )
        
        # Should work with P-only
        assert command is not None
        assert controller.pan_pid.get_integral() == 0.0
    
    def test_locked_mode_command_mode(self, controller):
        """Test command mode in LOCKED state."""
        command, diagnostics = controller.update(
            10.0, 5.0, 0.0, 0.0, TrackingMode.LOCKED, 0.05, 1.0
        )
        
        assert command.command_mode == "tracking"
    
    def test_coasting_mode_allows_control(self, controller):
        """Test that COASTING mode allows control."""
        command, diagnostics = controller.update(
            10.0, 5.0, 0.0, 0.0, TrackingMode.COASTING, 0.05, 1.0
        )
        
        # Should allow control
        assert command.command_mode == "tracking"
    
    def test_search_mode_allows_control(self, controller):
        """Test that SEARCH mode allows control."""
        command, diagnostics = controller.update(
            10.0, 5.0, 0.0, 0.0, TrackingMode.SEARCH, 0.05, 1.0
        )
        
        # Should allow control
        assert command.command_mode == "tracking"