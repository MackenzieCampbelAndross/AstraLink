"""Comprehensive tests for motion consistency checker."""

import pytest
import numpy as np

from astra_link_tracking.tracking.motion_consistency import MotionConsistencyChecker, MotionConsistencyResult
from astra_link_tracking.models.config import TrackingConfig


class TestMotionConsistencyChecker:
    """Test suite for motion consistency checker."""
    
    @pytest.fixture
    def tracking_config(self):
        """Create tracking configuration."""
        return TrackingConfig(
            confidence_threshold=0.5,
            process_noise=0.1,
            measurement_noise=1.0,
            mahalanobis_threshold=9.21,  # 99% confidence for 2D
            confirmation_frames=3,
            maximum_missed_frames=10,
            maximum_covariance_threshold=100.0
        )
    
    @pytest.fixture
    def consistency_checker(self, tracking_config):
        """Create motion consistency checker instance."""
        return MotionConsistencyChecker(tracking_config)
    
    @pytest.fixture
    def predicted_state(self):
        """Create sample predicted state."""
        return np.array([1.0, 2.0, 0.5, 0.3])  # [theta_x, theta_y, v_x, v_y]
    
    @pytest.fixture
    def predicted_covariance(self):
        """Create sample predicted covariance."""
        cov = np.eye(4) * 0.5
        cov[2:, 2:] = np.eye(2) * 0.1  # Less uncertainty in velocity
        return cov
    
    @pytest.fixture
    def measurement_covariance(self):
        """Create sample measurement covariance."""
        return np.eye(2) * 1.0
    
    def test_initialization(self, consistency_checker):
        """Test motion consistency checker initialization."""
        assert consistency_checker.mahalanobis_threshold == 9.21
        assert consistency_checker.H.shape == (2, 4)
        assert consistency_checker.confidence_threshold == 0.5
    
    def test_normal_trajectory(self, consistency_checker, predicted_state, 
                                predicted_covariance, measurement_covariance):
        """Test motion consistency for normal trajectory."""
        # Measurement close to prediction
        measurement = (1.1, 2.1)  # Small innovation
        
        result = consistency_checker.check(
            measurement, predicted_state, predicted_covariance,
            measurement_covariance, visible=True, confidence=0.9
        )
        
        # Should pass gate
        assert result.gate_passed is True
        assert result.should_accept is True
        assert result.motion_consistency_score > 0.5
        assert result.recommended_covariance_multiplier == 1.0
    
    def test_moderate_noise(self, consistency_checker, predicted_state,
                           predicted_covariance, measurement_covariance):
        """Test motion consistency with moderate noise."""
        # Measurement with moderate innovation
        measurement = (1.5, 2.5)  # Larger innovation
        
        result = consistency_checker.check(
            measurement, predicted_state, predicted_covariance,
            measurement_covariance, visible=True, confidence=0.8
        )
        
        # Should still pass gate with moderate noise
        assert result.gate_passed is True
        assert result.motion_consistency_score > 0.0
        assert result.innovation_magnitude > 0
    
    def test_extreme_outlier(self, consistency_checker, predicted_state,
                             predicted_covariance, measurement_covariance):
        """Test motion consistency with extreme outlier."""
        # Measurement far from prediction
        measurement = (10.0, 20.0)  # Extreme outlier
        
        result = consistency_checker.check(
            measurement, predicted_state, predicted_covariance,
            measurement_covariance, visible=True, confidence=0.9
        )
        
        # Should fail gate
        assert result.gate_passed is False
        assert result.should_accept is False
        assert result.motion_consistency_score < 0.1
        assert result.mahalanobis_distance_squared > result.gate_threshold
    
    def test_high_confidence_outlier(self, consistency_checker, predicted_state,
                                  predicted_covariance, measurement_covariance):
        """Test that high confidence outlier is still rejected (CASE 4)."""
        # High confidence but inconsistent measurement
        measurement = (10.0, 20.0)  # Extreme outlier
        
        result = consistency_checker.check(
            measurement, predicted_state, predicted_covariance,
            measurement_covariance, visible=True, confidence=0.95
        )
        
        # Should reject despite high confidence
        assert result.should_accept is False
        assert result.gate_passed is False
        assert result.confidence == 0.95
    
    def test_low_confidence_normal(self, consistency_checker, predicted_state,
                                   predicted_covariance, measurement_covariance):
        """Test low confidence but statistically consistent (CASE 3)."""
        # Low confidence but close to prediction
        measurement = (1.1, 2.1)
        
        result = consistency_checker.check(
            measurement, predicted_state, predicted_covariance,
            measurement_covariance, visible=True, confidence=0.3
        )
        
        # Should accept with increased covariance multiplier
        assert result.should_accept is True
        assert result.gate_passed is True
        assert result.recommended_covariance_multiplier > 1.0
    
    def test_low_confidence_inconsistent(self, consistency_checker, predicted_state,
                                        predicted_covariance, measurement_covariance):
        """Test low confidence and inconsistent measurement."""
        # Low confidence and far from prediction
        measurement = (5.0, 10.0)
        
        result = consistency_checker.check(
            measurement, predicted_state, predicted_covariance,
            measurement_covariance, visible=True, confidence=0.2
        )
        
        # Should reject
        assert result.should_accept is False
        assert result.recommended_covariance_multiplier == 1.0
    
    def test_invisible_detection(self, consistency_checker, predicted_state,
                                 predicted_covariance, measurement_covariance):
        """Test invisible detection handling."""
        # Invisible detection
        measurement = (1.1, 2.1)
        
        result = consistency_checker.check(
            measurement, predicted_state, predicted_covariance,
            measurement_covariance, visible=False, confidence=0.0
        )
        
        # Should reject invisible detection
        assert result.should_accept is False
        assert result.visible is False
    
    def test_perfect_match(self, consistency_checker, predicted_state,
                           predicted_covariance, measurement_covariance):
        """Test with perfect measurement match."""
        # Exact match to prediction
        measurement = (1.0, 2.0)
        
        result = consistency_checker.check(
            measurement, predicted_state, predicted_covariance,
            measurement_covariance, visible=True, confidence=0.9
        )
        
        # Should pass with high consistency score
        assert result.gate_passed is True
        assert result.should_accept is True
        assert result.innovation_magnitude < 1e-10
        assert result.mahalanobis_distance_squared < 1e-10
        assert result.motion_consistency_score > 0.99
    
    def test_innovation_components(self, consistency_checker, predicted_state,
                                    predicted_covariance, measurement_covariance):
        """Test innovation calculation."""
        measurement = (1.5, 2.5)
        
        result = consistency_checker.check(
            measurement, predicted_state, predicted_covariance,
            measurement_covariance, visible=True, confidence=0.9
        )
        
        # Innovation should be measurement - prediction
        assert abs(result.innovation_x - 0.5) < 1e-10
        assert abs(result.innovation_y - 0.5) < 1e-10
        assert abs(result.innovation_magnitude - np.sqrt(0.5**2 + 0.5**2)) < 1e-10
    
    def test_mahalanobis_distance_calculation(self, consistency_checker, predicted_state,
                                             predicted_covariance, measurement_covariance):
        """Test Mahalanobis distance calculation."""
        # Perfect match should give zero distance
        measurement = (1.0, 2.0)
        
        result = consistency_checker.check(
            measurement, predicted_state, predicted_covariance,
            measurement_covariance, visible=True, confidence=0.9
        )
        
        assert result.mahalanobis_distance_squared < 1e-10
        
        # Different measurement should give positive distance
        measurement = (2.0, 3.0)
        
        result = consistency_checker.check(
            measurement, predicted_state, predicted_covariance,
            measurement_covariance, visible=True, confidence=0.9
        )
        
        assert result.mahalanobis_distance_squared > 0
    
    def test_consistency_score_range(self, consistency_checker, predicted_state,
                                    predicted_covariance, measurement_covariance):
        """Test that consistency score is in [0, 1]."""
        # Perfect match should give score near 1
        measurement = (1.0, 2.0)
        result = consistency_checker.check(
            measurement, predicted_state, predicted_covariance,
            measurement_covariance, visible=True, confidence=0.9
        )
        assert 0.0 <= result.motion_consistency_score <= 1.0
        assert result.motion_consistency_score > 0.9
        
        # Extreme outlier should give score near 0
        measurement = (100.0, 200.0)
        result = consistency_checker.check(
            measurement, predicted_state, predicted_covariance,
            measurement_covariance, visible=True, confidence=0.9
        )
        assert 0.0 <= result.motion_consistency_score <= 1.0
        assert result.motion_consistency_score < 0.1
    
    def test_covariance_multiplier_calculation(self, consistency_checker, predicted_state,
                                                predicted_covariance, measurement_covariance):
        """Test covariance multiplier for low confidence."""
        # Low confidence should increase multiplier
        measurement = (1.1, 2.1)
        
        result = consistency_checker.check(
            measurement, predicted_state, predicted_covariance,
            measurement_covariance, visible=True, confidence=0.1
        )
        
        assert result.recommended_covariance_multiplier > 1.0
        assert result.recommended_covariance_multiplier <= 10.0  # Should be capped
    
    def test_covariance_multiplier_bounds(self, consistency_checker, predicted_state,
                                          predicted_covariance, measurement_covariance):
        """Test that covariance multiplier is bounded."""
        # Very low confidence
        measurement = (1.1, 2.1)
        
        result = consistency_checker.check(
            measurement, predicted_state, predicted_covariance,
            measurement_covariance, visible=True, confidence=0.001
        )
        
        # Should be capped at 10x
        assert result.recommended_covariance_multiplier <= 10.0
        
        # Normal confidence should give 1x
        result = consistency_checker.check(
            measurement, predicted_state, predicted_covariance,
            measurement_covariance, visible=True, confidence=0.9
        )
        
        assert result.recommended_covariance_multiplier == 1.0
    
    def test_different_gate_thresholds(self, tracking_config, predicted_state,
                                       predicted_covariance, measurement_covariance):
        """Test with different gate thresholds."""
        # Strict threshold
        tracking_config.mahalanobis_threshold = 4.0
        checker_strict = MotionConsistencyChecker(tracking_config)
        
        measurement = (2.0, 3.0)
        result_strict = checker_strict.check(
            measurement, predicted_state, predicted_covariance,
            measurement_covariance, visible=True, confidence=0.9
        )
        
        # Loose threshold
        tracking_config.mahalanobis_threshold = 20.0
        checker_loose = MotionConsistencyChecker(tracking_config)
        
        result_loose = checker_loose.check(
            measurement, predicted_state, predicted_covariance,
            measurement_covariance, visible=True, confidence=0.9
        )
        
        # Loose threshold should be more permissive
        assert result_loose.motion_consistency_score >= result_strict.motion_consistency_score
    
    def test_result_dataclass(self, consistency_checker, predicted_state,
                               predicted_covariance, measurement_covariance):
        """Test that result is properly structured."""
        measurement = (1.1, 2.1)
        
        result = consistency_checker.check(
            measurement, predicted_state, predicted_covariance,
            measurement_covariance, visible=True, confidence=0.9
        )
        
        # Check all fields are present
        assert hasattr(result, 'innovation_x')
        assert hasattr(result, 'innovation_y')
        assert hasattr(result, 'innovation_magnitude')
        assert hasattr(result, 'mahalanobis_distance_squared')
        assert hasattr(result, 'gate_passed')
        assert hasattr(result, 'motion_consistency_score')
        assert hasattr(result, 'should_accept')
        assert hasattr(result, 'recommended_covariance_multiplier')
        assert hasattr(result, 'gate_threshold')
        assert hasattr(result, 'visible')
        assert hasattr(result, 'confidence')
    
    def test_result_string_representation(self, consistency_checker, predicted_state,
                                          predicted_covariance, measurement_covariance):
        """Test result string representation."""
        measurement = (1.1, 2.1)
        
        result = consistency_checker.check(
            measurement, predicted_state, predicted_covariance,
            measurement_covariance, visible=True, confidence=0.9
        )
        
        # Should have string representation
        result_str = str(result)
        assert len(result_str) > 0
        assert 'MotionConsistencyResult' in result_str
    
    def test_high_measurement_covariance(self, consistency_checker, predicted_state,
                                         predicted_covariance):
        """Test with high measurement covariance."""
        # High measurement covariance should be more permissive
        high_meas_cov = np.eye(2) * 10.0
        measurement = (2.0, 3.0)
        
        result = consistency_checker.check(
            measurement, predicted_state, predicted_covariance,
            high_meas_cov, visible=True, confidence=0.9
        )
        
        # Should pass more easily with high measurement noise
        assert result.gate_passed is True
    
    def test_low_measurement_covariance(self, consistency_checker, predicted_state,
                                        predicted_covariance):
        """Test with low measurement covariance."""
        # Low measurement covariance should be stricter
        low_meas_cov = np.eye(2) * 0.1
        measurement = (1.5, 2.5)
        
        result = consistency_checker.check(
            measurement, predicted_state, predicted_covariance,
            low_meas_cov, visible=True, confidence=0.9
        )
        
        # Should be stricter with low measurement noise
        # (innovation should contribute more to Mahalanobis distance)
        assert result.mahalanobis_distance_squared > 0
    
    def test_get_gate_threshold(self, consistency_checker):
        """Test getting gate threshold."""
        threshold = consistency_checker.get_gate_threshold()
        assert threshold == 9.21
    
    def test_set_gate_threshold(self, consistency_checker):
        """Test setting gate threshold."""
        consistency_checker.set_gate_threshold(15.0)
        assert consistency_checker.get_gate_threshold() == 15.0
    
    def test_set_invalid_gate_threshold(self, consistency_checker):
        """Test setting invalid gate threshold."""
        with pytest.raises(ValueError, match="must be positive"):
            consistency_checker.set_gate_threshold(0.0)
        
        with pytest.raises(ValueError, match="must be positive"):
            consistency_checker.set_gate_threshold(-1.0)
    
    def test_reset(self, consistency_checker):
        """Test reset functionality."""
        # Currently no persistent state, but should not error
        consistency_checker.reset()
        
        # Should still work after reset
        predicted_state = np.array([1.0, 2.0, 0.5, 0.3])
        predicted_covariance = np.eye(4) * 0.5
        measurement_covariance = np.eye(2) * 1.0
        
        result = consistency_checker.check(
            (1.1, 2.1), predicted_state, predicted_covariance,
            measurement_covariance, visible=True, confidence=0.9
        )
        
        assert result is not None
    
    def test_deterministic_behavior(self, consistency_checker, predicted_state,
                                   predicted_covariance, measurement_covariance):
        """Test that behavior is deterministic."""
        measurement = (1.5, 2.5)
        
        # Run same check multiple times
        results = []
        for _ in range(5):
            result = consistency_checker.check(
                measurement, predicted_state, predicted_covariance,
                measurement_covariance, visible=True, confidence=0.9
            )
            results.append(result)
        
        # All results should be identical
        for i in range(1, len(results)):
            assert results[i].mahalanobis_distance_squared == results[0].mahalanobis_distance_squared
            assert results[i].gate_passed == results[0].gate_passed
            assert results[i].motion_consistency_score == results[0].motion_consistency_score
            assert results[i].should_accept == results[0].should_accept
    
    def test_case_1_visible_valid_gate_passes(self, consistency_checker, predicted_state,
                                            predicted_covariance, measurement_covariance):
        """Test CASE 1: visible + valid + gate passes → accept normally."""
        measurement = (1.1, 2.1)  # Small innovation
        
        result = consistency_checker.check(
            measurement, predicted_state, predicted_covariance,
            measurement_covariance, visible=True, confidence=0.9
        )
        
        assert result.should_accept is True
        assert result.recommended_covariance_multiplier == 1.0
    
    def test_case_2_visible_valid_gate_fails(self, consistency_checker, predicted_state,
                                            predicted_covariance, measurement_covariance):
        """Test CASE 2: visible + valid + gate fails → reject."""
        measurement = (20.0, 30.0)  # Extreme outlier
        
        result = consistency_checker.check(
            measurement, predicted_state, predicted_covariance,
            measurement_covariance, visible=True, confidence=0.9
        )
        
        assert result.should_accept is False
        assert result.gate_passed is False
    
    def test_case_3_low_confidence_consistent(self, consistency_checker, predicted_state,
                                            predicted_covariance, measurement_covariance):
        """Test CASE 3: low confidence + statistically consistent → accept with caution."""
        measurement = (1.1, 2.1)  # Small innovation
        
        result = consistency_checker.check(
            measurement, predicted_state, predicted_covariance,
            measurement_covariance, visible=True, confidence=0.3
        )
        
        assert result.should_accept is True
        assert result.recommended_covariance_multiplier > 1.0
    
    def test_case_4_high_confidence_inconsistent(self, consistency_checker, predicted_state,
                                            predicted_covariance, measurement_covariance):
        """Test CASE 4: high confidence + wildly inconsistent → do NOT blindly trust."""
        measurement = (20.0, 30.0)  # Extreme outlier
        
        result = consistency_checker.check(
            measurement, predicted_state, predicted_covariance,
            measurement_covariance, visible=True, confidence=0.95
        )
        
        # Should reject despite high confidence
        assert result.should_accept is False
        assert result.gate_passed is False
        assert result.confidence == 0.95
    
    def test_confidence_threshold_boundary(self, consistency_checker, predicted_state,
                                          predicted_covariance, measurement_covariance):
        """Test behavior at confidence threshold boundary."""
        measurement = (1.1, 2.1)
        
        # Just above threshold
        result_above = consistency_checker.check(
            measurement, predicted_state, predicted_covariance,
            measurement_covariance, visible=True, confidence=0.51
        )
        
        # Just below threshold
        result_below = consistency_checker.check(
            measurement, predicted_state, predicted_covariance,
            measurement_covariance, visible=True, confidence=0.49
        )
        
        # Above threshold should accept normally
        assert result_above.recommended_covariance_multiplier == 1.0
        
        # Below threshold should increase multiplier
        assert result_below.recommended_covariance_multiplier > 1.0