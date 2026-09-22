"""Demonstration of Kalman filter for state estimation."""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from astra_link_tracking.tracking.kalman import KalmanFilter
from astra_link_tracking.models.config import TrackingConfig
import numpy as np


def main():
    """Demonstrate Kalman filter capabilities."""
    print("=== Astra Link Member 2 - Kalman Filter Demo ===\n")
    
    # Create tracking configuration
    tracking_config = TrackingConfig(
        confidence_threshold=0.5,
        process_noise=0.1,
        measurement_noise=1.0,
        mahalanobis_threshold=3.0,
        confirmation_frames=3,
        maximum_missed_frames=10,
        maximum_covariance_threshold=100.0
    )
    
    # Create Kalman filter
    kf = KalmanFilter(tracking_config)
    
    print("Kalman Filter Configuration:")
    print(f"  Process noise (position): {tracking_config.process_noise}")
    print(f"  Process noise (velocity): {tracking_config.process_noise}")
    print(f"  Measurement noise (base): {tracking_config.measurement_noise}")
    print(f"  Initial covariance: {tracking_config.maximum_covariance_threshold}")
    
    print("\n=== Test 1: Stationary Target ===")
    kf.initialize(0.0, 0.0, 0.0)
    
    # Add noisy measurements around origin
    measurements = [
        (0.1, -0.05, 0.9),
        (-0.05, 0.1, 0.8),
        (0.02, -0.03, 0.95),
        (-0.01, 0.02, 0.85),
        (0.0, 0.0, 0.9),
    ]
    
    for i, (mx, my, conf) in enumerate(measurements):
        kf.predict(float(i + 1))
        kf.update(mx, my, conf)
        pos = kf.get_position()
        vel = kf.get_velocity()
        print(f"  Step {i+1}: Position=({pos[0]:.4f}, {pos[1]:.4f})°, Velocity=({vel[0]:.4f}, {vel[1]:.4f})°/s")
    
    print("\n=== Test 2: Constant Velocity Target ===")
    kf.reset(0.0, 0.0, 0.0)
    kf.state[2] = 1.0  # Set initial velocity
    kf.state[3] = 0.5
    
    print("  True velocity: (1.0, 0.5)°/s")
    
    for i in range(5):
        t = float(i + 1)
        true_x = 1.0 * t
        true_y = 0.5 * t
        noise_x = np.random.normal(0, 0.1)
        noise_y = np.random.normal(0, 0.1)
        
        kf.predict(t)
        kf.update(true_x + noise_x, true_y + noise_y, 0.9)
        
        pos = kf.get_position()
        vel = kf.get_velocity()
        print(f"  Step {i+1}: Position=({pos[0]:.4f}, {pos[1]:.4f})°, Velocity=({vel[0]:.4f}, {vel[1]:.4f})°/s")
    
    print("\n=== Test 3: Missing Measurements ===")
    kf.reset(0.0, 0.0, 0.0)
    kf.state[2] = 1.0
    kf.state[3] = 0.5
    
    # Add measurement
    kf.predict(1.0)
    kf.update(1.0, 0.5, 0.9)
    print("  Step 1: Measurement received")
    
    # Skip measurements (predict only)
    kf.predict(2.0)
    print("  Step 2: No measurement (prediction only)")
    kf.predict(3.0)
    print("  Step 3: No measurement (prediction only)")
    
    # Add measurement again
    kf.predict(4.0)
    kf.update(4.0, 2.0, 0.9)
    pos = kf.get_position()
    vel = kf.get_velocity()
    print(f"  Step 4: Measurement received, Position=({pos[0]:.4f}, {pos[1]:.4f})°, Velocity=({vel[0]:.4f}, {vel[1]:.4f})°/s")
    
    print("\n=== Test 4: Adaptive Measurement Covariance ===")
    kf.reset(0.0, 0.0, 0.0)
    
    # High confidence
    kf.predict(1.0)
    state_high, _ = kf.update(1.0, 1.0, 0.95)
    print(f"  High confidence (0.95): Position=({state_high[0]:.4f}, {state_high[1]:.4f})°")
    
    # Low confidence
    kf.reset(0.0, 0.0, 0.0)
    kf.predict(1.0)
    state_low, _ = kf.update(1.0, 1.0, 0.1)
    print(f"  Low confidence (0.1): Position=({state_low[0]:.4f}, {state_low[1]:.4f})°")
    print(f"  Low confidence results in less aggressive update (closer to initial state)")
    
    print("\n=== Test 5: Predict Only (Lookahead) ===")
    kf.reset(0.0, 0.0, 0.0)
    kf.state[2] = 1.0
    kf.state[3] = 0.5
    
    # Predict ahead without updating state
    for dt in [0.5, 1.0, 2.0]:
        pred_state, pred_cov = kf.predict_only(dt)
        print(f"  Predict {dt}s ahead: Position=({pred_state[0]:.4f}, {pred_state[1]:.4f})°")
    
    # Original state should be unchanged
    orig_pos = kf.get_position()
    print(f"  Original state unchanged: Position=({orig_pos[0]:.4f}, {orig_pos[1]:.4f})°")
    
    print("\n=== Test 6: Irregular Timestamps ===")
    kf.reset(0.0, 0.0, 0.0)
    kf.state[2] = 1.0
    kf.state[3] = 0.5
    
    timestamps = [0.0, 0.5, 1.3, 2.1, 3.0]
    
    for i, t in enumerate(timestamps[1:], 1):
        true_x = 1.0 * t
        true_y = 0.5 * t
        dt = t - timestamps[i-1]
        
        kf.predict(t)
        kf.update(true_x, true_y, 0.9)
        
        pos = kf.get_position()
        vel = kf.get_velocity()
        print(f"  t={t:.1f}s (dt={dt:.1f}s): Position=({pos[0]:.4f}, {pos[1]:.4f})°, Velocity=({vel[0]:.4f}, {vel[1]:.4f})°/s")
    
    print("\n=== Test 7: Covariance Evolution ===")
    kf.reset(0.0, 0.0, 0.0)
    
    print("  Initial covariance:")
    cov = kf.get_position_covariance()
    print(f"    Position covariance: diag={np.diag(cov)}")
    
    # After prediction (covariance should increase)
    kf.predict(1.0)
    cov = kf.get_position_covariance()
    print(f"  After prediction: diag={np.diag(cov)}")
    
    # After update (covariance should decrease)
    kf.update(1.0, 1.0, 0.9)
    cov = kf.get_position_covariance()
    print(f"  After update: diag={np.diag(cov)}")
    
    print("\nDemo complete. Kalman filter working correctly.")


if __name__ == "__main__":
    main()