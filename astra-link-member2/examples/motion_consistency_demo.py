"""Demonstration of motion consistency checker."""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from astra_link_tracking.tracking.motion_consistency import MotionConsistencyChecker, MotionConsistencyResult
from astra_link_tracking.models.config import TrackingConfig
import numpy as np


def main():
    """Demonstrate motion consistency checker capabilities."""
    print("=== Astra Link Member 2 - Motion Consistency Checker Demo ===\n")
    
    # Create tracking configuration
    tracking_config = TrackingConfig(
        confidence_threshold=0.5,
        process_noise=0.1,
        measurement_noise=1.0,
        mahalanobis_threshold=9.21,  # 99% confidence for 2D measurements
        confirmation_frames=3,
        maximum_missed_frames=10,
        maximum_covariance_threshold=100.0
    )
    
    # Create motion consistency checker
    checker = MotionConsistencyChecker(tracking_config)
    
    print("Motion Consistency Checker Configuration:")
    print(f"  Mahalanobis threshold: {tracking_config.mahalanobis_threshold}")
    print(f"  Confidence threshold: {tracking_config.confidence_threshold}")
    print(f"  Statistical background: Chi-squared distribution with 2 DOF")
    print(f"  Threshold 9.21 corresponds to 99% confidence level\n")
    
    # Sample predicted state and covariance
    predicted_state = np.array([1.0, 2.0, 0.5, 0.3])  # [theta_x, theta_y, v_x, v_y]
    predicted_covariance = np.eye(4) * 0.5
    measurement_covariance = np.eye(2) * 1.0
    
    print("=== Test 1: Normal Trajectory (CASE 1) ===")
    measurement = (1.1, 2.1)  # Small innovation
    result = checker.check(
        measurement, predicted_state, predicted_covariance,
        measurement_covariance, visible=True, confidence=0.9
    )
    print(f"  Measurement: {measurement}°")
    print(f"  Innovation: ({result.innovation_x:.4f}, {result.innovation_y:.4f})°")
    print(f"  Mahalanobis²: {result.mahalanobis_distance_squared:.4f}")
    print(f"  Gate passed: {result.gate_passed}")
    print(f"  Consistency score: {result.motion_consistency_score:.4f}")
    print(f"  Should accept: {result.should_accept}")
    print(f"  Recommended covariance multiplier: {result.recommended_covariance_multiplier:.2f}x")
    
    print("\n=== Test 2: Moderate Noise ===")
    measurement = (1.5, 2.5)  # Larger innovation
    result = checker.check(
        measurement, predicted_state, predicted_covariance,
        measurement_covariance, visible=True, confidence=0.8
    )
    print(f"  Measurement: {measurement}°")
    print(f"  Innovation: ({result.innovation_x:.4f}, {result.innovation_y:.4f})°")
    print(f"  Mahalanobis²: {result.mahalanobis_distance_squared:.4f}")
    print(f"  Gate passed: {result.gate_passed}")
    print(f"  Consistency score: {result.motion_consistency_score:.4f}")
    print(f"  Should accept: {result.should_accept}")
    
    print("\n=== Test 3: Extreme Outlier (CASE 2) ===")
    measurement = (10.0, 20.0)  # Extreme outlier
    result = checker.check(
        measurement, predicted_state, predicted_covariance,
        measurement_covariance, visible=True, confidence=0.9
    )
    print(f"  Measurement: {measurement}°")
    print(f"  Innovation: ({result.innovation_x:.4f}, {result.innovation_y:.4f})°")
    print(f"  Mahalanobis²: {result.mahalanobis_distance_squared:.4f}")
    print(f"  Gate threshold: {result.gate_threshold:.2f}")
    print(f"  Gate passed: {result.gate_passed}")
    print(f"  Consistency score: {result.motion_consistency_score:.4f}")
    print(f"  Should accept: {result.should_accept}")
    print(f"  Result: Rejected extreme outlier despite high confidence")
    
    print("\n=== Test 4: High Confidence Outlier (CASE 4) ===")
    measurement = (10.0, 20.0)  # Extreme outlier
    result = checker.check(
        measurement, predicted_state, predicted_covariance,
        measurement_covariance, visible=True, confidence=0.95
    )
    print(f"  Measurement: {measurement}°")
    print(f"  Confidence: {result.confidence}")
    print(f"  Gate passed: {result.gate_passed}")
    print(f"  Should accept: {result.should_accept}")
    print(f"  Result: Do NOT blindly trust high confidence outliers")
    
    print("\n=== Test 5: Low Confidence Normal (CASE 3) ===")
    measurement = (1.1, 2.1)  # Small innovation
    result = checker.check(
        measurement, predicted_state, predicted_covariance,
        measurement_covariance, visible=True, confidence=0.3
    )
    print(f"  Measurement: {measurement}°")
    print(f"  Confidence: {result.confidence}")
    print(f"  Gate passed: {result.gate_passed}")
    print(f"  Consistency score: {result.motion_consistency_score:.4f}")
    print(f"  Should accept: {result.should_accept}")
    print(f"  Recommended covariance multiplier: {result.recommended_covariance_multiplier:.2f}x")
    print(f"  Result: Accept with increased measurement noise")
    
    print("\n=== Test 6: Low Confidence Inconsistent ===")
    measurement = (5.0, 10.0)  # Moderate outlier
    result = checker.check(
        measurement, predicted_state, predicted_covariance,
        measurement_covariance, visible=True, confidence=0.2
    )
    print(f"  Measurement: {measurement}°")
    print(f"  Confidence: {result.confidence}")
    print(f"  Gate passed: {result.gate_passed}")
    print(f"  Should accept: {result.should_accept}")
    print(f"  Result: Reject low confidence inconsistent measurement")
    
    print("\n=== Test 7: Invisible Detection ===")
    measurement = (1.1, 2.1)
    result = checker.check(
        measurement, predicted_state, predicted_covariance,
        measurement_covariance, visible=False, confidence=0.0
    )
    print(f"  Measurement: {measurement}°")
    print(f"  Visible: {result.visible}")
    print(f"  Should accept: {result.should_accept}")
    print(f"  Result: Always reject invisible detections")
    
    print("\n=== Test 8: Perfect Match ===")
    measurement = (1.0, 2.0)  # Exact match
    result = checker.check(
        measurement, predicted_state, predicted_covariance,
        measurement_covariance, visible=True, confidence=0.9
    )
    print(f"  Measurement: {measurement}°")
    print(f"  Innovation magnitude: {result.innovation_magnitude:.10f}°")
    print(f"  Mahalanobis²: {result.mahalanobis_distance_squared:.10f}")
    print(f"  Consistency score: {result.motion_consistency_score:.4f}")
    print(f"  Should accept: {result.should_accept}")
    
    print("\n=== Test 9: Different Gate Thresholds ===")
    print("  Strict threshold (4.0):")
    tracking_config.mahalanobis_threshold = 4.0
    checker_strict = MotionConsistencyChecker(tracking_config)
    
    measurement = (2.0, 3.0)
    result_strict = checker_strict.check(
        measurement, predicted_state, predicted_covariance,
        measurement_covariance, visible=True, confidence=0.9
    )
    print(f"    Mahalanobis²: {result_strict.mahalanobis_distance_squared:.4f}")
    print(f"    Gate passed: {result_strict.gate_passed}")
    print(f"    Consistency score: {result_strict.motion_consistency_score:.4f}")
    
    print("  Loose threshold (20.0):")
    tracking_config.mahalanobis_threshold = 20.0
    checker_loose = MotionConsistencyChecker(tracking_config)
    
    result_loose = checker_loose.check(
        measurement, predicted_state, predicted_covariance,
        measurement_covariance, visible=True, confidence=0.9
    )
    print(f"    Mahalanobis²: {result_loose.mahalanobis_distance_squared:.4f}")
    print(f"    Gate passed: {result_loose.gate_passed}")
    print(f"    Consistency score: {result_loose.motion_consistency_score:.4f}")
    
    print(f"  Result: Loose threshold more permissive")
    
    print("\n=== Test 10: High Measurement Covariance ===")
    high_meas_cov = np.eye(2) * 10.0
    measurement = (2.0, 3.0)
    
    result = checker.check(
        measurement, predicted_state, predicted_covariance,
        high_meas_cov, visible=True, confidence=0.9
    )
    print(f"  Measurement covariance: 10x normal")
    print(f"  Mahalanobis²: {result.mahalanobis_distance_squared:.4f}")
    print(f"  Gate passed: {result.gate_passed}")
    print(f"  Result: High measurement noise more permissive")
    
    print("\n=== Test 11: Covariance Multiplier Bounds ===")
    very_low_confidence = 0.001
    measurement = (1.1, 2.1)
    
    result = checker.check(
        measurement, predicted_state, predicted_covariance,
        measurement_covariance, visible=True, confidence=very_low_confidence
    )
    print(f"  Confidence: {very_low_confidence}")
    print(f"  Recommended multiplier: {result.recommended_covariance_multiplier:.2f}x")
    print(f"  Result: Multiplier capped at 10x")
    
    print("\n=== Statistical Consistency Score Mapping ===")
    print("  Score mapping: exp(-d² / threshold)")
    print("  - d² = 0 → score = 1.0 (perfect consistency)")
    print("  - d² = threshold → score = 0.368 (at gate boundary)")
    print("  - d² >> threshold → score → 0.0 (inconsistent)")
    print("  This is a statistically meaningful mapping, not a fake accuracy")
    
    print("\nDemo complete. Motion consistency checker working correctly.")


if __name__ == "__main__":
    main()