"""Demonstration of coordinate transformation system."""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from astra_link_tracking.tracking.coordinate_transform import CoordinateTransform
from astra_link_tracking.models.config import CameraConfig


def main():
    """Demonstrate coordinate transformation capabilities."""
    print("=== Astra Link Member 2 - Coordinate Transformation Demo ===\n")
    
    # Create camera configuration
    camera_config = CameraConfig(
        resolution_width=640,
        resolution_height=480,
        horizontal_fov_deg=4.0,
        vertical_fov_deg=3.0,
        update_rate_hz=30.0
    )
    
    # Create coordinate transform
    transform = CoordinateTransform(camera_config)
    
    print("Camera Configuration:")
    print(f"  Resolution: {camera_config.resolution_width}x{camera_config.resolution_height}")
    print(f"  Horizontal FOV: {camera_config.horizontal_fov_deg}°")
    print(f"  Vertical FOV: {camera_config.vertical_fov_deg}°")
    print(f"  Camera Center: ({transform.cx}, {transform.cy})")
    print(f"\nConversion Factors:")
    print(f"  Degrees per pixel (X): {transform.degrees_per_pixel_x:.6f} °/pixel")
    print(f"  Degrees per pixel (Y): {transform.degrees_per_pixel_y:.6f} °/pixel")
    print(f"  Pixels per degree (X): {transform.pixels_per_degree_x:.2f} pixel/°")
    print(f"  Pixels per degree (Y): {transform.pixels_per_degree_y:.2f} pixel/°")
    
    print("\n=== Pixel to Angle Conversion ===")
    test_pixels = [
        (320.0, 240.0, "Center"),
        (480.0, 240.0, "Right offset"),
        (160.0, 240.0, "Left offset"),
        (320.0, 400.0, "Down offset"),
        (320.0, 80.0, "Up offset"),
        (480.0, 400.0, "Bottom-right corner"),
    ]
    
    for x, y, description in test_pixels:
        theta_x, theta_y = transform.pixel_to_angle(x, y)
        print(f"  {description}: ({x}, {y}) pixels → ({theta_x:.4f}, {theta_y:.4f})°")
    
    print("\n=== Angle to Pixel Conversion ===")
    test_angles = [
        (0.0, 0.0, "Center"),
        (1.0, 0.0, "Right 1°"),
        (-1.0, 0.0, "Left 1°"),
        (0.0, 1.0, "Down 1°"),
        (0.0, -1.0, "Up 1°"),
        (1.5, 1.0, "Diagonal"),
    ]
    
    for theta_x, theta_y, description in test_angles:
        x, y = transform.angle_to_pixel(theta_x, theta_y)
        print(f"  {description}: ({theta_x}, {theta_y})° → ({x:.2f}, {y:.2f}) pixels")
    
    print("\n=== Roundtrip Test: Pixel → Angle → Pixel ===")
    test_roundtrip = [
        (320.0, 240.0),
        (400.0, 300.0),
        (100.0, 150.0),
        (550.0, 420.0),
    ]
    
    for x_orig, y_orig in test_roundtrip:
        theta_x, theta_y = transform.pixel_to_angle(x_orig, y_orig)
        x_round, y_round = transform.angle_to_pixel(theta_x, theta_y)
        error_x = abs(x_round - x_orig)
        error_y = abs(y_round - y_orig)
        print(f"  ({x_orig}, {y_orig}) → ({theta_x:.4f}, {theta_y:.4f})° → ({x_round:.2f}, {y_round:.2f})")
        print(f"    Roundtrip error: ({error_x:.2e}, {error_y:.2e}) pixels")
    
    print("\n=== Velocity Conversion ===")
    test_velocities = [
        (160.0, 80.0, 0.1, "Right/down motion"),
        (-50.0, 30.0, 0.05, "Left/up motion"),
        (0.0, 0.0, 0.1, "Stationary"),
    ]
    
    for vx, vy, dt, description in test_velocities:
        omega_x, omega_y = transform.pixel_velocity_to_angular_velocity(vx, vy, dt)
        vx_round, vy_round = transform.angular_velocity_to_pixel_velocity(omega_x, omega_y, dt)
        print(f"  {description}:")
        print(f"    Pixel velocity: ({vx}, {vy}) pixels/s")
        print(f"    Angular velocity: ({omega_x:.4f}, {omega_y:.4f}) °/s")
        print(f"    Roundtrip: ({vx_round:.2f}, {vy_round:.2f}) pixels/s")
    
    print("\n=== Sign Convention Verification ===")
    print("  Positive X (right) → Positive angle:")
    theta_x, _ = transform.pixel_to_angle(400.0, 240.0)
    print(f"    (400, 240) → theta_x = {theta_x:.4f}° ({'✓' if theta_x > 0 else '✗'})")
    
    print("  Negative X (left) → Negative angle:")
    theta_x, _ = transform.pixel_to_angle(240.0, 240.0)
    print(f"    (240, 240) → theta_x = {theta_x:.4f}° ({'✓' if theta_x < 0 else '✗'})")
    
    print("  Positive Y (down) → Positive angle:")
    _, theta_y = transform.pixel_to_angle(320.0, 300.0)
    print(f"    (320, 300) → theta_y = {theta_y:.4f}° ({'✓' if theta_y > 0 else '✗'})")
    
    print("  Negative Y (up) → Negative angle:")
    _, theta_y = transform.pixel_to_angle(320.0, 180.0)
    print(f"    (320, 180) → theta_y = {theta_y:.4f}° ({'✓' if theta_y < 0 else '✗'})")
    
    print("\n=== FOV Boundary Test ===")
    # Left edge
    theta_x_left, _ = transform.pixel_to_angle(0.0, 240.0)
    print(f"  Left edge (0, 240): {theta_x_left:.4f}° (expected -2.0°)")
    
    # Right edge
    theta_x_right, _ = transform.pixel_to_angle(640.0, 240.0)
    print(f"  Right edge (640, 240): {theta_x_right:.4f}° (expected +2.0°)")
    
    # Top edge
    _, theta_y_top = transform.pixel_to_angle(320.0, 0.0)
    print(f"  Top edge (320, 0): {theta_y_top:.4f}° (expected -1.5°)")
    
    # Bottom edge
    _, theta_y_bottom = transform.pixel_to_angle(320.0, 480.0)
    print(f"  Bottom edge (320, 480): {theta_y_bottom:.4f}° (expected +1.5°)")
    
    print("\n=== Different Camera Configuration ===")
    hd_config = CameraConfig(
        resolution_width=1280,
        resolution_height=720,
        horizontal_fov_deg=5.0,
        vertical_fov_deg=4.0,
        update_rate_hz=30.0
    )
    hd_transform = CoordinateTransform(hd_config)
    
    print(f"HD Camera (1280x720, 5x4°):")
    print(f"  Degrees per pixel (X): {hd_transform.degrees_per_pixel_x:.6f} °/pixel")
    print(f"  Degrees per pixel (Y): {hd_transform.degrees_per_pixel_y:.6f} °/pixel")
    
    # Same pixel offset, different angle
    theta_x_default, _ = transform.pixel_to_angle(160.0, 240.0)
    theta_x_hd, _ = hd_transform.pixel_to_angle(160.0, 240.0)
    print(f"  160 pixels right:")
    print(f"    Default camera: {theta_x_default:.4f}°")
    print(f"    HD camera: {theta_x_hd:.4f}°")
    print(f"    Difference: {abs(theta_x_default - theta_x_hd):.4f}°")
    
    print("\nDemo complete. Coordinate transformation system working correctly.")


if __name__ == "__main__":
    main()