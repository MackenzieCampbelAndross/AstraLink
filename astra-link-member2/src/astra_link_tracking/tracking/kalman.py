"""Kalman filter for state estimation.

Implements a linear constant-velocity Kalman filter for tracking beacon state.
State vector: [theta_x, theta_y, v_x, v_y]
- theta_x, theta_y: angular position in degrees
- v_x, v_y: angular velocity in degrees/second
"""

from typing import Tuple, Optional
import numpy as np

from astra_link_tracking.models.config import TrackingConfig


class KalmanFilter:
    """Kalman filter for tracking beacon state (position and velocity).
    
    Uses a linear constant-velocity model with adaptive measurement covariance
    based on detection confidence.
    """
    
    def __init__(self, tracking_config: TrackingConfig):
        """Initialize Kalman filter with tracking configuration.
        
        Args:
            tracking_config: Tracking configuration with Kalman parameters
        """
        self.config = tracking_config
        
        # Process noise parameters
        self.process_noise_pos = tracking_config.process_noise
        self.process_noise_vel = tracking_config.process_noise
        
        # Measurement noise parameters
        self.measurement_noise_base = tracking_config.measurement_noise
        self.measurement_noise_min = tracking_config.measurement_noise * 0.1  # Lower bound
        self.measurement_noise_max = tracking_config.measurement_noise * 10.0  # Upper bound
        
        # Initial covariance
        self.initial_covariance = tracking_config.maximum_covariance_threshold
        
        # State vector: [theta_x, theta_y, v_x, v_y]
        self.state = np.zeros(4)
        self.covariance = np.eye(4) * self.initial_covariance
        
        # Measurement matrix H: maps state to measurement space
        # H = [[1, 0, 0, 0], [0, 1, 0, 0]]
        self.H = np.array([
            [1.0, 0.0, 0.0, 0.0],
            [0.0, 1.0, 0.0, 0.0]
        ])
        
        # Identity matrix
        self.I = np.eye(4)
        
        # Timing
        self.last_timestamp = None
        self.initialized = False
    
    def initialize(self, theta_x: float, theta_y: float, timestamp: float):
        """Initialize filter with initial position and timestamp.
        
        Args:
            theta_x: Initial angular position X (degrees)
            theta_y: Initial angular position Y (degrees)
            timestamp: Initial timestamp (seconds)
        """
        self.state = np.array([theta_x, theta_y, 0.0, 0.0])
        self.covariance = np.eye(4) * self.initial_covariance
        self.last_timestamp = timestamp
        self.initialized = True
    
    def _build_state_transition_matrix(self, dt: float) -> np.ndarray:
        """Build state transition matrix F for given time step.
        
        F = [[1, 0, dt, 0],
             [0, 1, 0, dt],
             [0, 0, 1, 0],
             [0, 0, 0, 1]]
        
        Args:
            dt: Time step in seconds
            
        Returns:
            4x4 state transition matrix
        """
        return np.array([
            [1.0, 0.0, dt, 0.0],
            [0.0, 1.0, 0.0, dt],
            [0.0, 0.0, 1.0, 0.0],
            [0.0, 0.0, 0.0, 1.0]
        ])
    
    def _build_process_noise_covariance(self, dt: float) -> np.ndarray:
        """Build process noise covariance matrix Q for given time step.
        
        Q models uncertainty in state transition due to unmodeled dynamics.
        Uses constant velocity model with position and velocity noise.
        
        Args:
            dt: Time step in seconds
            
        Returns:
            4x4 process noise covariance matrix
        """
        # Discrete-time process noise for constant velocity model
        # Q = [[Q_pos, Q_pos_vel],
        #      [Q_vel_pos, Q_vel]]
        # where Q_pos = (noise_pos * dt^4 / 4) * I
        #       Q_pos_vel = (noise_pos * dt^3 / 2) * I
        #       Q_vel = (noise_pos * dt^2 + noise_vel * dt) * I
        
        dt2 = dt * dt
        dt3 = dt2 * dt
        dt4 = dt3 * dt
        
        q_pos = (self.process_noise_pos * dt4 / 4.0)
        q_pos_vel = (self.process_noise_pos * dt3 / 2.0)
        q_vel = (self.process_noise_pos * dt2 + self.process_noise_vel * dt)
        
        Q = np.zeros((4, 4))
        Q[0, 0] = q_pos
        Q[1, 1] = q_pos
        Q[0, 2] = q_pos_vel
        Q[1, 3] = q_pos_vel
        Q[2, 0] = q_pos_vel
        Q[3, 1] = q_pos_vel
        Q[2, 2] = q_vel
        Q[3, 3] = q_vel
        
        return Q
    
    def _compute_adaptive_measurement_covariance(self, confidence: float) -> np.ndarray:
        """Compute adaptive measurement covariance based on confidence.
        
        Higher confidence → smaller measurement noise
        Lower confidence → larger measurement noise
        
        R = R_base / confidence, clamped to [R_min, R_max]
        
        Args:
            confidence: Detection confidence in [0, 1]
            
        Returns:
            2x2 measurement noise covariance matrix
        """
        # Clamp confidence to avoid division by zero
        confidence_clamped = max(0.01, min(1.0, confidence))
        
        # Adaptive measurement noise
        adaptive_noise = self.measurement_noise_base / confidence_clamped
        
        # Clamp to bounds
        adaptive_noise = max(self.measurement_noise_min, 
                           min(self.measurement_noise_max, adaptive_noise))
        
        return np.eye(2) * adaptive_noise
    
    def predict(self, timestamp: float) -> Tuple[np.ndarray, np.ndarray]:
        """Predict state forward to given timestamp.
        
        Args:
            timestamp: Target timestamp (seconds)
            
        Returns:
            (predicted_state, predicted_covariance)
            
        Raises:
            ValueError: If filter not initialized or timestamp invalid
        """
        if not self.initialized:
            raise ValueError("Kalman filter not initialized. Call initialize() first.")
        
        if self.last_timestamp is None:
            raise ValueError("Last timestamp not set.")
        
        if timestamp <= self.last_timestamp:
            raise ValueError(f"Timestamp {timestamp} must be greater than last_timestamp {self.last_timestamp}")
        
        dt = timestamp - self.last_timestamp
        
        # Build state transition matrix
        F = self._build_state_transition_matrix(dt)
        
        # Build process noise covariance
        Q = self._build_process_noise_covariance(dt)
        
        # Predict state: x_pred = F * x
        self.state = F @ self.state
        
        # Predict covariance: P_pred = F * P * F^T + Q
        self.covariance = F @ self.covariance @ F.T + Q
        
        # Update timestamp
        self.last_timestamp = timestamp
        
        return self.state.copy(), self.covariance.copy()
    
    def predict_only(self, dt: float) -> Tuple[np.ndarray, np.ndarray]:
        """Predict state forward by dt seconds without updating timestamp.
        
        Useful for lookahead predictions without updating filter state.
        
        Args:
            dt: Time step in seconds
            
        Returns:
            (predicted_state, predicted_covariance)
        """
        if not self.initialized:
            raise ValueError("Kalman filter not initialized. Call initialize() first.")
        
        # Build state transition matrix
        F = self._build_state_transition_matrix(dt)
        
        # Build process noise covariance
        Q = self._build_process_noise_covariance(dt)
        
        # Predict state
        pred_state = F @ self.state
        
        # Predict covariance
        pred_covariance = F @ self.covariance @ F.T + Q
        
        return pred_state, pred_covariance
    
    def update(self, theta_x: float, theta_y: float, confidence: float) -> Tuple[np.ndarray, np.ndarray]:
        """Update filter with position measurement.
        
        Args:
            theta_x: Measured angular position X (degrees)
            theta_y: Measured angular position Y (degrees)
            confidence: Detection confidence in [0, 1]
            
        Returns:
            (updated_state, updated_covariance)
            
        Raises:
            ValueError: If filter not initialized
        """
        if not self.initialized:
            raise ValueError("Kalman filter not initialized. Call initialize() first.")
        
        # Measurement vector
        z = np.array([theta_x, theta_y])
        
        # Compute adaptive measurement covariance
        R = self._compute_adaptive_measurement_covariance(confidence)
        
        # Innovation: y = z - H * x
        y = z - self.H @ self.state
        
        # Innovation covariance: S = H * P * H^T + R
        S = self.H @ self.covariance @ self.H.T + R
        
        # Kalman gain: K = P * H^T * S^-1
        try:
            K = self.covariance @ self.H.T @ np.linalg.inv(S)
        except np.linalg.LinAlgError:
            # Fallback: use pseudo-inverse if S is singular
            K = self.covariance @ self.H.T @ np.linalg.pinv(S)
        
        # Update state: x = x + K * y
        self.state = self.state + K @ y
        
        # Joseph form covariance update for numerical stability
        # P = (I - K * H) * P * (I - K * H)^T + K * R * K^T
        I_KH = self.I - K @ self.H
        self.covariance = I_KH @ self.covariance @ I_KH.T + K @ R @ K.T
        
        return self.state.copy(), self.covariance.copy()
    
    def get_state(self) -> np.ndarray:
        """Get current state vector.
        
        Returns:
            State vector [theta_x, theta_y, v_x, v_y]
        """
        return self.state.copy()
    
    def get_covariance(self) -> np.ndarray:
        """Get current state covariance matrix.
        
        Returns:
            4x4 state covariance matrix
        """
        return self.covariance.copy()
    
    def get_position(self) -> Tuple[float, float]:
        """Get current position estimate.
        
        Returns:
            (theta_x, theta_y) position estimate in degrees
        """
        return (float(self.state[0]), float(self.state[1]))
    
    def get_velocity(self) -> Tuple[float, float]:
        """Get current velocity estimate.
        
        Returns:
            (v_x, v_y) velocity estimate in degrees/second
        """
        return (float(self.state[2]), float(self.state[3]))
    
    def get_position_covariance(self) -> np.ndarray:
        """Get position covariance matrix.
        
        Returns:
            2x2 position covariance matrix (degrees^2)
        """
        return self.covariance[:2, :2].copy()
    
    def get_velocity_covariance(self) -> np.ndarray:
        """Get velocity covariance matrix.
        
        Returns:
            2x2 velocity covariance matrix ((degrees/s)^2)
        """
        return self.covariance[2:, 2:].copy()
    
    def reset(self, theta_x: float = 0.0, theta_y: float = 0.0, timestamp: float = 0.0):
        """Reset filter to initial state.
        
        Args:
            theta_x: Initial angular position X (degrees), default 0.0
            theta_y: Initial angular position Y (degrees), default 0.0
            timestamp: Initial timestamp (seconds), default 0.0
        """
        self.initialize(theta_x, theta_y, timestamp)
    
    def is_initialized(self) -> bool:
        """Check if filter is initialized.
        
        Returns:
            True if initialized, False otherwise
        """
        return self.initialized
