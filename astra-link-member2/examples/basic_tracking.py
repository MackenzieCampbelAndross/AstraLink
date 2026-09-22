"""Basic tracking example demonstrating new data contracts and configuration system."""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from astra_link_tracking.models.interfaces import DetectionResult, TrackingMode, TrackingState, CameraCommand
from astra_link_tracking.models.config import TrackingSystemConfig


def main():
    """Run basic tracking example."""
    # Load configuration
    config_path = Path(__file__).parent.parent / "config" / "default_config.json"
    config = TrackingSystemConfig.from_json_file(str(config_path))
    config.validate()
    
    print("=== Astra Link Member 2 - Data Contracts & Configuration Demo ===\n")
    
    print("Configuration loaded and validated:")
    print(f"  Camera resolution: {config.camera.resolution_width}x{config.camera.resolution_height}")
    print(f"  Horizontal FOV: {config.camera.horizontal_fov_deg}°")
    print(f"  Vertical FOV: {config.camera.vertical_fov_deg}°")
    print(f"  Update rate: {config.camera.update_rate_hz} Hz")
    print(f"  Control rate: {config.control.control_rate_hz} Hz")
    print(f"  Pixel to angle X: {config.camera.pixel_to_angle_x:.6f} rad/pixel")
    print(f"  Pixel to angle Y: {config.camera.pixel_to_angle_y:.6f} rad/pixel")
    print(f"  Angle to pixel X: {config.camera.angle_to_pixel_x:.2f} pixel/rad")
    print(f"  Angle to pixel Y: {config.camera.angle_to_pixel_y:.2f} pixel/rad")
    
    print("\nDemonstrating new DetectionResult data contract:")
    detection = DetectionResult(
        timestamp=1.0,
        frame_id=42,
        centroid_x=320.0,
        centroid_y=240.0,
        confidence=0.95,
        visible=True,
        detector_id="beacon_detector_v1",
        bbox=(300, 220, 340, 260),
        detection_area=1600.0,
        metadata={"quality": "high", "snr": 15.3}
    )
    
    print(f"  Timestamp: {detection.timestamp} s")
    print(f"  Frame ID: {detection.frame_id}")
    print(f"  Centroid: ({detection.centroid_x}, {detection.centroid_y}) pixels")
    print(f"  Confidence: {detection.confidence}")
    print(f"  Visible: {detection.visible}")
    print(f"  Detector ID: {detection.detector_id}")
    print(f"  Bounding box: {detection.bbox}")
    print(f"  Detection area: {detection.detection_area} pixels²")
    print(f"  Metadata: {detection.metadata}")
    
    print("\nDemonstrating new TrackingState data contract:")
    tracking_state = TrackingState(
        timestamp=1.0,
        state=TrackingMode.LOCKED,
        predicted_x=320.0,
        predicted_y=240.0,
        angular_x=0.035,
        angular_y=0.026,
        velocity_x=5.0,
        velocity_y=3.0,
        motion_consistency=True,
        prediction_uncertainty=0.5,
        measurement_accepted=True,
        confidence=0.92,
        time_since_last_detection=0.05,
        tracking_id="session_12345"
    )
    
    print(f"  Timestamp: {tracking_state.timestamp} s")
    print(f"  State: {tracking_state.state.value}")
    print(f"  Predicted position: ({tracking_state.predicted_x}, {tracking_state.predicted_y}) pixels")
    print(f"  Angular position: ({tracking_state.angular_x:.4f}, {tracking_state.angular_y:.4f}) rad")
    print(f"  Velocity: ({tracking_state.velocity_x}, {tracking_state.velocity_y}) pixels/s")
    print(f"  Motion consistent: {tracking_state.motion_consistency}")
    print(f"  Prediction uncertainty: {tracking_state.prediction_uncertainty} pixels²")
    print(f"  Measurement accepted: {tracking_state.measurement_accepted}")
    print(f"  Confidence: {tracking_state.confidence}")
    print(f"  Time since last detection: {tracking_state.time_since_last_detection} s")
    print(f"  Tracking ID: {tracking_state.tracking_id}")
    
    print("\nDemonstrating new CameraCommand data contract:")
    camera_command = CameraCommand(
        timestamp=1.0,
        pan_command=0.035,
        tilt_command=0.026,
        slew_rate=(0.01, 0.008),
        command_mode="tracking",
        diagnostics={"settling_time": 0.05, "overshoot": 0.02}
    )
    
    print(f"  Timestamp: {camera_command.timestamp} s")
    print(f"  Pan command: {camera_command.pan_command:.4f} rad")
    print(f"  Tilt command: {camera_command.tilt_command:.4f} rad")
    print(f"  Slew rate: ({camera_command.slew_rate[0]:.4f}, {camera_command.slew_rate[1]:.4f}) rad/s")
    print(f"  Command mode: {camera_command.command_mode}")
    print(f"  Diagnostics: {camera_command.diagnostics}")
    
    print("\nDemonstrating TrackingMode enum:")
    print(f"  Available modes: {[mode.value for mode in TrackingMode]}")
    print(f"  Current mode: {tracking_state.state.value}")
    print(f"  Mode type: {type(tracking_state.state)}")
    
    print("\nDemonstrating configuration modification:")
    original_resolution = config.camera.resolution_width
    config.camera.resolution_width = 1280
    config.camera.horizontal_fov_deg = 5.0
    config.validate()
    print(f"  Original resolution: {original_resolution}")
    print(f"  New resolution: {config.camera.resolution_width}")
    print(f"  New pixel to angle X: {config.camera.pixel_to_angle_x:.6f} rad/pixel")
    
    print("\nExample complete. All data contracts and configuration system working correctly.")


if __name__ == "__main__":
    main()
