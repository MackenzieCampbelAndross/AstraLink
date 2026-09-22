"""Comprehensive tests for PID controller."""

import pytest

from astra_link_tracking.control.pid import PIDController


class TestPIDController:
    """Test suite for PID controller."""
    
    @pytest.fixture
    def pid_controller(self):
        """Create a PID controller instance."""
        return PIDController(kp=1.0, ki=0.1, kd=0.01, output_limits=(-10.0, 10.0))
    
    def test_initialization(self, pid_controller):
        """Test PID controller initialization."""
        assert pid_controller.kp == 1.0
        assert pid_controller.ki == 0.1
        assert pid_controller.kd == 0.01
        assert pid_controller.output_limits == (-10.0, 10.0)
        assert pid_controller.integral == 0.0
        assert pid_controller.last_error is None
        assert pid_controller.last_output is None
    
    def test_p_only(self):
        """Test P-only operation (ki=0, kd=0)."""
        pid = PIDController(kp=2.0, ki=0.0, kd=0.0)
        
        error = 5.0
        dt = 0.1
        output = pid.update(error, dt)
        
        # P-only: output = kp * error
        assert output == 10.0
        assert pid.integral == 0.0
    
    def test_pi_control(self, pid_controller):
        """Test PI control (kd=0)."""
        pid = PIDController(kp=1.0, ki=0.5, kd=0.0)
        
        error = 2.0
        dt = 0.1
        
        # First update
        output1 = pid.update(error, dt)
        
        # Second update with same error
        output2 = pid.update(error, dt)
        
        # Integral should have accumulated
        assert output2 > output1
    
    def test_full_pid(self, pid_controller):
        """Test full PID control."""
        error = 5.0
        dt = 0.1
        output = pid_controller.update(error, dt)
        
        assert isinstance(output, float)
        # With positive error and positive gains, output should be positive
        assert output > 0
    
    def test_static_target(self, pid_controller):
        """Test static target (error goes to zero)."""
        # Start with large error
        error = 10.0
        dt = 0.1
        
        for _ in range(10):
            output = pid_controller.update(error, dt)
            # Error should decrease over time with integral action
            error -= output * dt
        
        # Error should be smaller
        assert abs(error) < 10.0
    
    def test_constant_velocity(self, pid_controller):
        """Test tracking constant velocity target."""
        # Simulate target moving at constant velocity
        error = 0.0
        dt = 0.1
        
        for i in range(20):
            # Target moves away at constant rate
            error += 0.5 * dt
            output = pid_controller.update(error, dt)
            
            # Output should track the motion
            assert output > 0
    
    def test_direction_reversal(self, pid_controller):
        """Test direction reversal (error sign change)."""
        # Positive error
        error = 5.0
        dt = 0.1
        output1 = pid_controller.update(error, dt)
        
        # Reset integral for clean test
        pid_controller.reset()
        
        # Negative error
        error = -5.0
        output2 = pid_controller.update(error, dt)
        
        # Output should have opposite sign
        assert output1 > 0
        assert output2 < 0
    
    def test_output_limits(self, pid_controller):
        """Test output limiting."""
        # Very large error should be limited
        large_error = 1000.0
        output = pid_controller.update(large_error, 0.1)
        
        assert output <= pid_controller.output_limits[1]
        assert output >= pid_controller.output_limits[0]
    
    def test_lower_limit(self, pid_controller):
        """Test lower output limit."""
        pid = PIDController(kp=1.0, ki=0.0, kd=0.0, output_limits=(-5.0, 5.0))
        
        # Large negative error
        large_error = -1000.0
        output = pid.update(large_error, 0.1)
        
        assert output >= pid.output_limits[0]
        assert output == -5.0
    
    def test_upper_limit(self, pid_controller):
        """Test upper output limit."""
        pid = PIDController(kp=1.0, ki=0.0, kd=0.0, output_limits=(-5.0, 5.0))
        
        # Large positive error
        large_error = 1000.0
        output = pid.update(large_error, 0.1)
        
        assert output <= pid.output_limits[1]
        assert output == 5.0
    
    def test_integral_windup_prevention(self):
        """Test integral anti-windup."""
        pid = PIDController(kp=1.0, ki=1.0, kd=0.0, output_limits=(-5.0, 5.0))
        
        # Saturate at upper limit
        error = 10.0
        dt = 0.1
        
        # Drive to saturation
        for _ in range(20):
            output = pid.update(error, dt)
        
        assert output == 5.0  # Saturated
        
        # Record integral
        integral_at_saturation = pid.get_integral()
        
        # Continue with same error (should not increase integral due to anti-windup)
        for _ in range(10):
            output = pid.update(error, dt)
        
        # Integral should not have increased significantly
        assert pid.get_integral() <= integral_at_saturation + 1e-6
    
    def test_integral_reset_on_error_sign_change(self):
        """Test that integral can decrease when error sign changes."""
        pid = PIDController(kp=1.0, ki=1.0, kd=0.0, output_limits=(-10.0, 10.0))
        
        # Positive error
        error = 5.0
        dt = 0.1
        for _ in range(10):
            pid.update(error, dt)
        
        integral_before = pid.get_integral()
        
        # Negative error (should decrease integral)
        error = -5.0
        for _ in range(10):
            pid.update(error, dt)
        
        # Integral should have decreased
        assert pid.get_integral() < integral_before
    
    def test_derivative_with_actual_dt(self, pid_controller):
        """Test derivative uses actual dt."""
        # First update
        error1 = 5.0
        dt1 = 0.1
        output1 = pid_controller.update(error1, dt1)
        
        # Second update with different error
        error2 = 3.0
        dt2 = 0.05  # Different dt
        output2 = pid_controller.update(error2, dt2)
        
        # Derivative should account for actual dt
        assert output1 != output2
    
    def test_variable_dt(self, pid_controller):
        """Test variable dt handling."""
        error = 5.0
        
        # Different dt values
        outputs = []
        for dt in [0.05, 0.1, 0.2, 0.15]:
            pid_controller.reset()
            output = pid_controller.update(error, dt)
            outputs.append(output)
        
        # Outputs should vary with dt due to integral and derivative
        assert len(set(outputs)) > 1
    
    def test_zero_dt_protection(self, pid_controller):
        """Test that zero dt raises error."""
        error = 5.0
        dt = 0.0
        
        with pytest.raises(ValueError, match="dt must be positive"):
            pid_controller.update(error, dt)
    
    def test_negative_dt_protection(self, pid_controller):
        """Test that negative dt raises error."""
        error = 5.0
        dt = -0.1
        
        with pytest.raises(ValueError, match="dt must be positive"):
            pid_controller.update(error, dt)
    
    def test_invalid_dt_protection(self, pid_controller):
        """Test that invalid dt raises error."""
        error = 5.0
        dt = -1e-10  # Very small negative
        
        with pytest.raises(ValueError, match="dt must be positive"):
            pid_controller.update(error, dt)
    
    def test_derivative_first_update(self, pid_controller):
        """Test derivative on first update (should be zero)."""
        error = 5.0
        dt = 0.1
        
        # First update - no last_error, derivative should be zero
        output = pid_controller.update(error, dt)
        
        # Derivative term should be zero on first update
        assert pid_controller.last_error == error
    
    def test_reset(self, pid_controller):
        """Test PID controller reset."""
        pid_controller.update(5.0, 0.1)
        pid_controller.reset()
        
        assert pid_controller.integral == 0.0
        assert pid_controller.last_error is None
        assert pid_controller.last_output is None
    
    def test_get_integral(self, pid_controller):
        """Test getting integral value."""
        error = 5.0
        dt = 0.1
        
        pid_controller.update(error, dt)
        integral = pid_controller.get_integral()
        
        assert integral > 0
        assert integral == pid_controller.integral
    
    def test_unlimited_output(self):
        """Test unlimited output (no limits)."""
        pid = PIDController(kp=1.0, ki=0.0, kd=0.0, output_limits=(-float('inf'), float('inf')))
        
        large_error = 1000.0
        output = pid.update(large_error, 0.1)
        
        # Should not be limited
        assert output == 1000.0
    
    def test_one_sided_limit(self):
        """Test one-sided output limit."""
        pid = PIDController(kp=1.0, ki=0.0, kd=0.0, output_limits=(-float('inf'), 5.0))
        
        # Should limit upper bound only
        output = pid.update(1000.0, 0.1)
        assert output == 5.0
        
        # Should not limit lower bound
        output = pid.update(-1000.0, 0.1)
        assert output == -1000.0
