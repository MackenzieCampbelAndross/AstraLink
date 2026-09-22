"""Motion consistency checking for anomaly detection.

Implements Mahalanobis distance-based gating to determine if new detections
are statistically consistent with Kalman filter predictions.

Statistical Background:
- Mahalanobis distance follows chi-squared distribution with k degrees of freedom
- For 2D measurements (k=2), threshold of 9.21 corresponds to 99% confidence
- Default threshold is configurable to trade off false positives vs missed detections
"""

from dataclasses import dataclass
from typing import Tuple, Optional
import numpy as np

from astra_link_tracking.models.config import TrackingConfig


@dataclass
class MotionConsistencyResult:
    """Result of motion consistency check.
    
    Contains all diagnostics for determining measurement acceptance.
    """
    innovation_x: float  # Innovation in X (degrees)
    innovation_y: float  # Innovation in Y (degrees)
    innovation_magnitude: float  # Magnitude of innovation vector (degrees)
    mahalanobis_distance_squared: float  # Squared Mahalanobis distance
    gate_passed: bool  # Whether measurement passed Mahalanobis gate
    motion_consistency_score: float  # Normalized consistency score [0, 1]
    should_accept: bool  # Whether measurement should be accepted
    recommended_covariance_multiplier: float  # Suggested measurement noise multiplier
    gate_threshold: float  # Configured gate threshold
    visible: bool  # Whether detection was visible
    confidence: float  # Detection confidence [0, 1]
    
    def __str__(self) -> str:
        """String representation for debugging."""
        return (f"MotionConsistencyResult(innovation=({self.innovation_x:.4f}, {self.innovation_y:.4f}), "
                f"mahalanobis2={self.mahalanobis_distance_squared:.4f}, "
                f"gate_passed={self.gate_passed}, score={self.motion_consistency_score:.4f}, "
                f"should_accept={self.should_accept})")


class MotionConsistencyChecker:
    """Checks for motion anomalies using Mahalanobis distance gating.
    
    Determines whether new detections are statistically consistent with
    Kalman filter predictions using chi-squared statistical gating.
    """
    
    def __init__(self, tracking_config: TrackingConfig):
        """Initialize motion consistency checker with configuration.
        
        Args:
            tracking_config: Tracking configuration with Mahalanobis threshold
        """
        self.mahalanobis_threshold = tracking_config.mahalanobis_threshold
        self.confidence_threshold = tracking_config.confidence_threshold
        
        # Default Mahalanobis threshold for 2D measurements
        # 9.21 corresponds to 99% confidence level for chi-squared with 2 DOF
        # This is configurable based on desired false positive rate
        if self.mahalanobis_threshold <= 0:
            self.mahalanobis_threshold = 9.21
        
        # Measurement matrix H (2x4)
        self.H = np.array([
            [1.0, 0.0, 0.0, 0.0],
            [0.0, 1.0, 0.0, 0.0]
        ])
    
    def check(
        self,
        measurement: Tuple[float, float],
        predicted_state: np.ndarray,
        predicted_covariance: np.ndarray,
        measurement_covariance: np.ndarray,
        visible: bool,
        confidence: float
    ) -> MotionConsistencyResult:
        """Check if measurement is consistent with prediction.
        
        Computes Mahalanobis distance and applies statistical gating.
        
        Args:
            measurement: (theta_x, theta_y) measurement in degrees
            predicted_state: Predicted state vector [theta_x, theta_y, v_x, v_y]
            predicted_covariance: Predicted state covariance (4x4)
            measurement_covariance: Measurement noise covariance (2x2)
            visible: Whether detection is visible
            confidence: Detection confidence [0, 1]
            
        Returns:
            MotionConsistencyResult with all diagnostics
        """
        # Convert measurement to numpy array
        z = np.array(measurement)
        
        # Extract predicted position
        predicted_position = predicted_state[:2]
        
        # Compute innovation: y = z - H @ x_pred
        innovation = z - predicted_position
        innovation_x = float(innovation[0])
        innovation_y = float(innovation[1])
        innovation_magnitude = float(np.linalg.norm(innovation))
        
        # Compute innovation covariance: S = H @ P @ H.T + R
        S = self.H @ predicted_covariance @ self.H.T + measurement_covariance
        
        # Compute Mahalanobis distance: d2 = y.T @ inv(S) @ y
        try:
            S_inv = np.linalg.inv(S)
        except np.linalg.LinAlgError:
            # Fallback to pseudo-inverse if singular
            S_inv = np.linalg.pinv(S)
        
        mahalanobis_distance_squared = float(innovation.T @ S_inv @ innovation)
        
        # Apply Mahalanobis gate
        gate_passed = mahalanobis_distance_squared <= self.mahalanobis_threshold
        
        # Compute normalized consistency score
        # Score = exp(-d2 / threshold) gives [0, 1] range
        # Higher score = more consistent
        motion_consistency_score = np.exp(-mahalanobis_distance_squared / self.mahalanobis_threshold)
        motion_consistency_score = float(np.clip(motion_consistency_score, 0.0, 1.0))
        
        # Determine acceptance based on 4 cases
        should_accept, recommended_multiplier = self._determine_acceptance(
            visible, confidence, gate_passed, motion_consistency_score
        )
        
        return MotionConsistencyResult(
            innovation_x=innovation_x,
            innovation_y=innovation_y,
            innovation_magnitude=innovation_magnitude,
            mahalanobis_distance_squared=mahalanobis_distance_squared,
            gate_passed=gate_passed,
            motion_consistency_score=motion_consistency_score,
            should_accept=should_accept,
            recommended_covariance_multiplier=recommended_multiplier,
            gate_threshold=self.mahalanobis_threshold,
            visible=visible,
            confidence=confidence
        )
    
    def _determine_acceptance(
        self,
        visible: bool,
        confidence: float,
        gate_passed: bool,
        consistency_score: float
    ) -> Tuple[bool, float]:
        """Determine whether to accept measurement based on case analysis.
        
        CASE 1: visible + valid + gate passes → accept normally
        CASE 2: visible + valid + gate fails → reject or heavily downweight
        CASE 3: low confidence + statistically consistent → allow with larger covariance
        CASE 4: high confidence + wildly inconsistent → do NOT blindly trust
        
        Args:
            visible: Whether detection is visible
            confidence: Detection confidence [0, 1]
            gate_passed: Whether Mahalanobis gate passed
            consistency_score: Normalized consistency score [0, 1]
            
        Returns:
            (should_accept, recommended_covariance_multiplier)
        """
        # Invisible detections are always rejected
        if not visible:
            return False, 1.0
        
        # CASE 1: Visible, high confidence, gate passes → accept normally
        if confidence >= self.confidence_threshold and gate_passed:
            return True, 1.0
        
        # CASE 2: Visible, gate fails → reject
        if not gate_passed:
            return False, 1.0
        
        # CASE 3: Low confidence but statistically consistent → accept with caution
        if confidence < self.confidence_threshold:
            if gate_passed and consistency_score > 0.5:
                # Accept but increase measurement covariance
                multiplier = 1.0 / max(0.1, confidence)  # Higher multiplier for lower confidence
                multiplier = min(multiplier, 10.0)  # Cap at 10x
                return True, multiplier
            else:
                # Low confidence and inconsistent → reject
                return False, 1.0
        
        # CASE 4: High confidence but inconsistent → do not blindly trust
        # (This case is handled by the gate check above, but kept for completeness)
        if confidence >= self.confidence_threshold and not gate_passed:
            return False, 1.0
        
        # Default: reject
        return False, 1.0
    
    def get_gate_threshold(self) -> float:
        """Get current Mahalanobis gate threshold.
        
        Returns:
            Current threshold value
        """
        return self.mahalanobis_threshold
    
    def set_gate_threshold(self, threshold: float):
        """Set Mahalanobis gate threshold.
        
        Args:
            threshold: New threshold value (must be positive)
            
        Raises:
            ValueError: If threshold is not positive
        """
        if threshold <= 0:
            raise ValueError(f"Mahalanobis threshold must be positive, got {threshold}")
        self.mahalanobis_threshold = threshold
    
    def reset(self):
        """Reset motion consistency checker state."""
        # No persistent state to reset in current implementation
        pass
