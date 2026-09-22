"""Comprehensive tests for Kalman filter."""

import pytest
import numpy as np
import math

from astra_link_tracking.tracking.kalman import KalmanFilter
from astra_link_tracking.models.config import TrackingConfig


class TestKalmanFilter:
    """Test suite for Kalman filter."""
    
    @pytest.fixture
    def tracking_config(self):
        """Create tracking configuration."""
        return TrackingConfig(
            confidence_threshold=0.5,
            process_noise=0.1,
            measurement_noise=1.0,
            mahalanobis_threshold=3.0,
            confirmation_frames=3,
            maximum_missed_frames=10,
            maximum_covariance_threshold=100.0
        )
    
    @pytest.fixture
    def kalman_filter(self, tracking_config):
        """Create Kalman filter instance."""
        return KalmanFilter(tracking_config)
    
    def test_initialization(self, kalman_filter):
        """Test Kalman filter initialization."""
        assert kalman_filter.state.shape == (4,)
        assert kalman_filter.covariance.shape == (4, 4)
        assert kalman_filter.H.shape == (2, 4)
        assert kalman_filter.I.shape == (4, 4)
        assert not kalman_filter.is_initialized()
    
    def test_initialize(self, kalman_filter):
        """Test filter initialization with position and timestamp."""
        kalman_filter.initialize(1.0, 2.0, 0.0)
        
        assert kalman_filter.is_initialized()
        assert abs(kalman_filter.state[0] - 1.0) < 1e-10
        assert abs(kalman_filter.state[1] - 2.0) < 1e-10
        assert abs(kalman_filter.state[2]) < 1e-10  # Zero initial velocity
        assert abs(kalman_filter.state[3]) < 1e-10
        assert kalman_filter.last_timestamp == 0.0
    
    def test_reset(self, kalman_filter):
        """Test filter reset."""
        kalman_filter.initialize(1.0, 2.0, 0.0)
        kalman_filter.update(1.5, 2.5, 0.9)
        
        # Reset to new state
        kalman_filter.reset(5.0, 6.0, 10.0)
        
        assert abs(kalman_filter.state[0] - 5.0) < 1e-10
        assert abs(kalman_filter.state[1] - 6.0) < 1e-10
        assert kalman_filter.last_timestamp == 10.0
    
    def test_predict_not_initialized(self, kalman_filter):
        """Test prediction when filter not initialized."""
        with pytest.raises(ValueError, match="not initialized"):
            kalman_filter.predict(1.0)
    
    def test_predict_stationary_target(self, kalman_filter):
        """Test prediction for stationary target."""
        kalman_filter.initialize(0.0, 0.0, 0.0)
        
        # Predict forward 1 second
        state, cov = kalman_filter.predict(1.0)
        
        # Position should remain near zero (with some process noise)
        assert abs(state[0]) < 0.5  # Allow some drift
        assert abs(state[1]) < 0.5
        # Velocity should remain near zero
        assert abs(state[2]) < 0.1
        assert abs(state[3]) < 0.1
    
    def test_predict_constant_velocity(self, kalman_filter):
        """Test prediction for constant velocity target."""
        kalman_filter.initialize(0.0, 0.0, 0.0)
        
        # Set initial velocity
        kalman_filter.state[2] = 1.0  # 1 degree/second in X
        kalman_filter.state[3] = 0.5  # 0.5 degree/second in Y
        
        # Predict forward 1 second
        state, cov = kalman_filter.predict(1.0)
        
        # Position should advance by velocity * dt
        assert abs(state[0] - 1.0) < 0.1  # ~1 degree
        assert abs(state[1] - 0.5) < 0.1  # ~0.5 degree
        # Velocity should remain constant
        assert abs(state[2] - 1.0) < 0.1
        assert abs(state[3] - 0.5) < 0.1
    
    def test_predict_multiple_steps(self, kalman_filter):
        """Test prediction over multiple time steps."""
        kalman_filter.initialize(0.0, 0.0, 0.0)
        kalman_filter.state[2] = 1.0
        kalman_filter.state[3] = 0.5
        
        # Predict in steps
        for i in range(1, 6):
            state, cov = kalman_filter.predict(float(i))
            expected_x = 1.0 * i
            expected_y = 0.5 * i
            assert abs(state[0] - expected_x) < 0.2
            assert abs(state[1] - expected_y) < 0.2
    
    def test_update_not_initialized(self, kalman_filter):
        """Test update when filter not initialized."""
        with pytest.raises(ValueError, match="not initialized"):
            kalman_filter.update(1.0, 2.0, 0.9)
    
    def test_update_stationary_target(self, kalman_filter):
        """Test update for stationary target with noisy measurements."""
        kalman_filter.initialize(0.0, 0.0, 0.0)
        
        # Add noisy measurements around origin
        measurements = [
            (0.1, -0.05, 0.9),
            (-0.05, 0.1, 0.8),
            (0.02, -0.03, 0.95),
            (-0.01, 0.02, 0.85),
            (0.0, 0.0, 0.9),
        ]
        
        for i, (mx, my, conf) in enumerate(measurements):
            kalman_filter.predict(float(i + 1))
            kalman_filter.update(mx, my, conf)
        
        # Final estimate should be near origin
        pos = kalman_filter.get_position()
        assert abs(pos[0]) < 0.05
        assert abs(pos[1]) < 0.05
    
    def test_update_constant_velocity(self, kalman_filter):
        """Test update for constant velocity target."""
        kalman_filter.initialize(0.0, 0.0, 0.0)
        
        # Generate measurements for constant velocity motion
        # v_x = 1.0 deg/s, v_y = 0.5 deg/s
        measurements = []
        for i in range(10):
            t = float(i)
            true_x = 1.0 * t
            true_y = 0.5 * t
            # Add measurement noise
            noise_x = np.random.normal(0, 0.1)
            noise_y = np.random.normal(0, 0.1)
            measurements.append((true_x + noise_x, true_y + noise_y, 0.9))
        
        for i, (mx, my, conf) in enumerate(measurements):
            kalman_filter.predict(float(i + 1))
            kalman_filter.update(mx, my, conf)
        
        # Final velocity estimate should be close to true velocity
        vel = kalman_filter.get_velocity()
        assert abs(vel[0] - 1.0) < 0.2
        assert abs(vel[1] - 0.5) < 0.2
    
    def test_noisy_measurements(self, kalman_filter):
        """Test filter behavior with noisy measurements."""
        kalman_filter.initialize(0.0, 0.0, 0.0)
        
        # Generate noisy measurements
        np.random.seed(42)
        for i in range(20):
            t = float(i)
            true_x = 0.5 * t  # Constant velocity
            true_y = 0.3 * t
            noise_x = np.random.normal(0, 0.5)  # High noise
            noise_y = np.random.normal(0, 0.5)
            
            kalman_filter.predict(t + 1.0)
            kalman_filter.update(true_x + noise_x, true_y + noise_y, 0.7)
        
        # Filter should still track despite noise
        pos = kalman_filter.get_position()
        vel = kalman_filter.get_velocity()
        
        # Velocity should be reasonably estimated
        assert abs(vel[0] - 0.5) < 0.3
        assert abs(vel[1] - 0.3) < 0.3
    
    def test_missing_measurements(self, kalman_filter):
        """Test filter behavior with missing measurements."""
        kalman_filter.initialize(0.0, 0.0, 0.0)
        kalman_filter.state[2] = 1.0
        kalman_filter.state[3] = 0.5
        
        # Add some measurements
        kalman_filter.predict(1.0)
        kalman_filter.update(1.0, 0.5, 0.9)
        
        # Skip some measurements (predict only)
        kalman_filter.predict(2.0)
        kalman_filter.predict(3.0)
        kalman_filter.predict(4.0)
        
        # Add measurement again
        kalman_filter.predict(5.0)
        kalman_filter.update(5.0, 2.5, 0.9)
        
        # Filter should have continued prediction during missing measurements
        pos = kalman_filter.get_position()
        vel = kalman_filter.get_velocity()
        
        # Position should be reasonable
        assert abs(pos[0] - 5.0) < 1.0
        assert abs(pos[1] - 2.5) < 1.0
    
    def test_irregular_timestamps(self, kalman_filter):
        """Test filter with irregular time steps."""
        kalman_filter.initialize(0.0, 0.0, 0.0)
        kalman_filter.state[2] = 1.0
        kalman_filter.state[3] = 0.5
        
        # Irregular time steps
        timestamps = [0.0, 0.5, 1.3, 2.1, 3.0, 4.5]
        
        for i, t in enumerate(timestamps[1:], 1):
            true_x = 1.0 * t
            true_y = 0.5 * t
            
            kalman_filter.predict(t)
            kalman_filter.update(true_x, true_y, 0.9)
        
        # Should handle irregular dt correctly
        pos = kalman_filter.get_position()
        vel = kalman_filter.get_velocity()
        
        assert abs(vel[0] - 1.0) < 0.2
        assert abs(vel[1] - 0.5) < 0.2
    
    def test_low_confidence(self, kalman_filter):
        """Test adaptive measurement covariance with low confidence."""
        kalman_filter.initialize(0.0, 0.0, 0.0)
        
        # High confidence measurement
        kalman_filter.predict(1.0)
        state_high, cov_high = kalman_filter.update(1.0, 1.0, 0.95)
        
        # Reset
        kalman_filter.reset(0.0, 0.0, 0.0)
        
        # Low confidence measurement
        kalman_filter.predict(1.0)
        state_low, cov_low = kalman_filter.update(1.0, 1.0, 0.1)
        
        # Low confidence should result in less aggressive update
        # (state should be closer to initial state)
        assert abs(state_low[0]) < abs(state_high[0])
        assert abs(state_low[1]) < abs(state_high[1])
    
    def test_adaptive_covariance_bounds(self, kalman_filter):
        """Test that adaptive covariance respects bounds."""
        kalman_filter.initialize(0.0, 0.0, 0.0)
        
        # Very high confidence (should clamp to min)
        kalman_filter.predict(1.0)
        kalman_filter.update(1.0, 1.0, 1.0)
        
        # Very low confidence (should clamp to max)
        kalman_filter.reset(0.0, 0.0, 0.0)
        kalman_filter.predict(1.0)
        kalman_filter.update(1.0, 1.0, 0.0)
        
        # Should not raise errors even with extreme confidence values
        kalman_filter.reset(0.0, 0.0, 0.0)
        kalman_filter.predict(1.0)
        kalman_filter.update(1.0, 1.0, 0.001)  # Very low confidence
    
    def test_predict_only(self, kalman_filter):
        """Test predict_only without updating filter state."""
        kalman_filter.initialize(0.0, 0.0, 0.0)
        kalman_filter.state[2] = 1.0
        kalman_filter.state[3] = 0.5
        
        # Predict only
        pred_state, pred_cov = kalman_filter.predict_only(1.0)
        
        # Original state should be unchanged
        assert abs(kalman_filter.state[0]) < 1e-10
        assert abs(kalman_filter.state[1]) < 1e-10
        
        # Predicted state should show motion
        assert abs(pred_state[0] - 1.0) < 0.1
        assert abs(pred_state[1] - 0.5) < 0.1
    
    def test_get_position(self, kalman_filter):
        """Test getting position estimate."""
        kalman_filter.initialize(1.5, 2.5, 0.0)
        
        pos = kalman_filter.get_position()
        assert isinstance(pos, tuple)
        assert len(pos) == 2
        assert abs(pos[0] - 1.5) < 1e-10
        assert abs(pos[1] - 2.5) < 1e-10
    
    def test_get_velocity(self, kalman_filter):
        """Test getting velocity estimate."""
        kalman_filter.initialize(0.0, 0.0, 0.0)
        kalman_filter.state[2] = 1.5
        kalman_filter.state[3] = 2.5
        
        vel = kalman_filter.get_velocity()
        assert isinstance(vel, tuple)
        assert len(vel) == 2
        assert abs(vel[0] - 1.5) < 1e-10
        assert abs(vel[1] - 2.5) < 1e-10
    
    def test_get_position_covariance(self, kalman_filter):
        """Test getting position covariance."""
        kalman_filter.initialize(0.0, 0.0, 0.0)
        
        pos_cov = kalman_filter.get_position_covariance()
        assert pos_cov.shape == (2, 2)
        assert pos_cov[0, 0] > 0  # Should have some uncertainty
        assert pos_cov[1, 1] > 0
    
    def test_get_velocity_covariance(self, kalman_filter):
        """Test getting velocity covariance."""
        kalman_filter.initialize(0.0, 0.0, 0.0)
        
        vel_cov = kalman_filter.get_velocity_covariance()
        assert vel_cov.shape == (2, 2)
        assert vel_cov[0, 0] > 0
        assert vel_cov[1, 1] > 0
    
    def test_get_state(self, kalman_filter):
        """Test getting full state vector."""
        kalman_filter.initialize(1.0, 2.0, 0.0)
        kalman_filter.state[2] = 0.5
        kalman_filter.state[3] = 0.3
        
        state = kalman_filter.get_state()
        assert state.shape == (4,)
        assert abs(state[0] - 1.0) < 1e-10
        assert abs(state[1] - 2.0) < 1e-10
        assert abs(state[2] - 0.5) < 1e-10
        assert abs(state[3] - 0.3) < 1e-10
    
    def test_get_covariance(self, kalman_filter):
        """Test getting full covariance matrix."""
        kalman_filter.initialize(0.0, 0.0, 0.0)
        
        cov = kalman_filter.get_covariance()
        assert cov.shape == (4, 4)
        assert np.allclose(cov, cov.T)  # Should be symmetric
    
    def test_state_transition_matrix(self, kalman_filter):
        """Test state transition matrix construction."""
        dt = 0.5
        F = kalman_filter._build_state_transition_matrix(dt)
        
        assert F.shape == (4, 4)
        assert abs(F[0, 0] - 1.0) < 1e-10
        assert abs(F[0, 2] - dt) < 1e-10
        assert abs(F[1, 3] - dt) < 1e-10
        assert abs(F[2, 2] - 1.0) < 1e-10
        assert abs(F[3, 3] - 1.0) < 1e-10
    
    def test_process_noise_covariance(self, kalman_filter):
        """Test process noise covariance construction."""
        dt = 0.5
        Q = kalman_filter._build_process_noise_covariance(dt)
        
        assert Q.shape == (4, 4)
        assert np.allclose(Q, Q.T)  # Should be symmetric
        assert np.all(Q >= 0)  # Should be positive semi-definite
    
    def test_measurement_matrix(self, kalman_filter):
        """Test measurement matrix."""
        H = kalman_filter.H
        
        assert H.shape == (2, 4)
        assert abs(H[0, 0] - 1.0) < 1e-10
        assert abs(H[1, 1] - 1.0) < 1e-10
        # Other elements should be zero
        assert abs(H[0, 1]) < 1e-10
        assert abs(H[0, 2]) < 1e-10
        assert abs(H[0, 3]) < 1e-10
    
    def test_invalid_timestamp(self, kalman_filter):
        """Test handling of invalid timestamps."""
        kalman_filter.initialize(0.0, 0.0, 0.0)
        
        # Timestamp not greater than last timestamp
        with pytest.raises(ValueError, match="must be greater"):
            kalman_filter.predict(0.0)
        
        with pytest.raises(ValueError, match="must be greater"):
            kalman_filter.predict(-1.0)
    
    def test_covariance_symmetry(self, kalman_filter):
        """Test that covariance matrix remains symmetric."""
        kalman_filter.initialize(0.0, 0.0, 0.0)
        
        for i in range(10):
            kalman_filter.predict(float(i + 1))
            kalman_filter.update(float(i), float(i), 0.9)
            
            cov = kalman_filter.get_covariance()
            assert np.allclose(cov, cov.T, atol=1e-10)
    
    def test_covariance_positive_definite(self, kalman_filter):
        """Test that covariance matrix remains positive definite."""
        kalman_filter.initialize(0.0, 0.0, 0.0)
        
        for i in range(10):
            kalman_filter.predict(float(i + 1))
            kalman_filter.update(float(i), float(i), 0.9)
            
            cov = kalman_filter.get_covariance()
            # Check eigenvalues are positive
            eigenvalues = np.linalg.eigvals(cov)
            assert np.all(eigenvalues > -1e-10)  # Allow small numerical errors
    
    def test_numerical_stability(self, kalman_filter):
        """Test numerical stability with many updates."""
        kalman_filter.initialize(0.0, 0.0, 0.0)
        
        # Many updates
        for i in range(100):
            kalman_filter.predict(float(i + 1))
            kalman_filter.update(float(i) * 0.1, float(i) * 0.05, 0.9)
        
        # Should not produce NaN or infinity
        state = kalman_filter.get_state()
        cov = kalman_filter.get_covariance()
        
        assert np.all(np.isfinite(state))
        assert np.all(np.isfinite(cov))
    
    def test_confidence_scaling(self, kalman_filter):
        """Test that confidence properly scales measurement noise."""
        kalman_filter.initialize(0.0, 0.0, 0.0)
        
        # High confidence should give low measurement noise
        R_high = kalman_filter._compute_adaptive_measurement_covariance(0.95)
        
        # Low confidence should give high measurement noise
        R_low = kalman_filter._compute_adaptive_measurement_covariance(0.1)
        
        assert R_low[0, 0] > R_high[0, 0]
        assert R_low[1, 1] > R_high[1, 1]
    
    def test_zero_confidence_clamping(self, kalman_filter):
        """Test that zero confidence is clamped to avoid division by zero."""
        kalman_filter.initialize(0.0, 0.0, 0.0)
        
        # Should not raise error with zero confidence
        R = kalman_filter._compute_adaptive_measurement_covariance(0.0)
        
        assert np.all(np.isfinite(R))
        assert R[0, 0] > 0
        assert R[1, 1] > 0