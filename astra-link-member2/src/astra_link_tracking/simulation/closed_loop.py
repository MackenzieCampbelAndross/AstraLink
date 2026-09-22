"""Closed-loop simulation for testing Member 2."""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import numpy as np

from astra_link_tracking.simulation.trajectories import TrajectoryGenerator
from astra_link_tracking.simulation.virtual_camera import VirtualCamera
from astra_link_tracking.models.config import TrackingSystemConfig
from astra_link_tracking.models.interfaces import DetectionResult, TrackingState, CameraCommand, TrackingMode
from astra_link_tracking.tracking.kalman import KalmanFilter
from astra_link_tracking.tracking.motion_consistency import MotionConsistencyChecker
from astra_link_tracking.tracking.state_machine import TrackingStateMachine
from astra_link_tracking.control.controller import CameraController
from astra_link_tracking.tracking.coordinate_transform import CoordinateTransform


@dataclass
class SimulationStep:
    """Single step of simulation history."""
    timestamp: float
    target_pan: float  # Ground truth target pan (degrees, absolute)
    target_tilt: float  # Ground truth target tilt (degrees, absolute)
    camera_pan: float  # Camera pan angle (degrees, absolute)
    camera_tilt: float  # Camera tilt angle (degrees, absolute)
    relative_pan: float  # Target relative to camera (degrees)
    relative_tilt: float  # Target relative to camera (degrees)
    detection_pan: Optional[float]  # Measured target pan (degrees, absolute, with noise)
    detection_tilt: Optional[float]  # Measured target tilt (degrees, absolute, with noise)
    estimated_pan: float  # Kalman estimate pan (degrees, absolute)
    estimated_tilt: float  # Kalman estimate tilt (degrees, absolute)
    velocity_x: float  # Estimated velocity X (degrees/second)
    velocity_y: float  # Estimated velocity Y (degrees/second)
    command_pan: float  # Camera command pan (degrees, absolute)
    command_tilt: float  # Camera command tilt (degrees, absolute)
    tracking_mode: TrackingMode
    error_pan: float  # Tracking error pan (degrees)
    error_tilt: float  # Tracking error tilt (degrees)


@dataclass
class SimulationResult:
    """Result of closed-loop simulation."""
    history: List[SimulationStep] = field(default_factory=list)
    final_error: float = 0.0
    final_mode: TrackingMode = TrackingMode.SEARCH
    duration: float = 0.0
    steps: int = 0


class ClosedLoopSimulation:
    """Closed-loop simulation for testing Member 2.
    
    Simulates the full loop:
    1. Generate ground-truth target position
    2. Calculate target relative to camera
    3. Generate noisy detection
    4. Feed to Member 2 tracker
    5. Generate camera command
    6. Apply command through camera slew limits
    7. Repeat
    """
    
    def __init__(
        self,
        config: TrackingSystemConfig,
        trajectory_type: str = "stationary",
        duration: float = 60.0,
        dt: float = 0.05,
        seed: Optional[int] = 42,
        measurement_noise_std: float = 0.1
    ):
        """Initialize closed-loop simulation.
        
        Args:
            config: Tracking system configuration
            trajectory_type: Type of trajectory (stationary, linear, circular, figure8, sinusoidal, random, spiral)
            duration: Simulation duration in seconds
            dt: Time step in seconds
            seed: Random seed for reproducibility
            measurement_noise_std: Standard deviation of measurement noise (degrees)
        """
        self.config = config
        self.dt = dt
        self.seed = seed
        
        # Set random seed
        if seed is not None:
            np.random.seed(seed)
        
        # Initialize trajectory generator
        self.trajectory_gen = TrajectoryGenerator(
            trajectory_type=trajectory_type,
            duration=duration,
            dt=dt,
            seed=seed
        )
        
        # Initialize virtual camera
        self.camera = VirtualCamera(
            config.camera,
            config.control,
            measurement_noise_std=measurement_noise_std
        )
        
        # Initialize Member 2 components
        self.kalman = KalmanFilter(config.tracking)
        self.motion_consistency = MotionConsistencyChecker(config.tracking)
        self.state_machine = TrackingStateMachine(config.tracking)
        self.controller = CameraController(config.control)
        self.coord_transform = CoordinateTransform(config.camera)
        
        # Simulation state
        self.history: List[SimulationStep] = []
        self.current_time = 0.0
        self.frame_id = 0
    
    def reset(self):
        """Reset simulation to initial state."""
        self.camera.reset()
        # Reset Kalman filter with default initial state
        self.kalman.initialize(0.0, 0.0, 0.0)  # Start at timestamp 0
        self.motion_consistency.reset()
        self.state_machine.reset()
        self.controller.reset()
        self.history.clear()
        self.current_time = 0.0
        self.frame_id = 0
        
        # Re-seed if seed was provided
        if self.seed is not None:
            np.random.seed(self.seed)
    
    def step(self) -> SimulationStep:
        """Execute one simulation step.
        
        Returns:
            SimulationStep with all step data
        """
        # Increment time first to ensure dt > 0
        self.current_time += self.dt
        
        # Get target position from trajectory
        target_data = self.trajectory_gen.generate()
        if self.frame_id < len(target_data):
            _, (target_pan, target_tilt), (target_vel_x, target_vel_y) = target_data[self.frame_id]
        else:
            # Trajectory ended, hold last position
            _, (target_pan, target_tilt), (target_vel_x, target_vel_y) = target_data[-1]
        
        # Get camera state
        camera_pan, camera_tilt = self.camera.get_state()
        
        # Calculate target relative to camera
        relative_pan, relative_tilt = self.camera.get_relative_angle(target_pan, target_tilt)
        
        # Generate noisy detection
        measured_pan, measured_tilt = self.camera.observe_target(target_pan, target_tilt)
        
        # Convert to pixel coordinates for Kalman filter
        pixel_x, pixel_y = self.camera.angle_to_pixel(relative_pan, relative_tilt)
        
        # Determine if target is visible (within FOV)
        fov_half_x = self.config.camera.horizontal_fov_deg / 2
        fov_half_y = self.config.camera.vertical_fov_deg / 2
        visible = abs(relative_pan) <= fov_half_x and abs(relative_tilt) <= fov_half_y
        
        # Create detection result
        detection = DetectionResult(
            timestamp=self.current_time,
            frame_id=self.frame_id,
            centroid_x=pixel_x if visible else None,
            centroid_y=pixel_y if visible else None,
            confidence=0.9 if visible else 0.0,
            visible=visible
        )
        
        # Update Kalman filter
        if visible and detection.centroid_x is not None:
            # Convert pixel to angular
            angle_x, angle_y = self.camera.pixel_to_angle(detection.centroid_x, detection.centroid_y)
            
            # Initialize Kalman on first detection
            if not self.kalman.initialized:
                self.kalman.initialize(angle_x, angle_y, self.current_time)
            else:
                # Update Kalman
                self.kalman.predict(self.current_time)
                self.kalman.update(angle_x, angle_y, detection.confidence)
        else:
            # Prediction only (if initialized) or do nothing
            if self.kalman.initialized:
                self.kalman.predict(self.current_time)
        
        # Get Kalman estimate
        estimated_state = self.kalman.get_state()
        estimated_covariance = self.kalman.get_covariance()
        estimated_pan_rel = estimated_state[0]  # Relative angle
        estimated_tilt_rel = estimated_state[1]
        velocity_x = estimated_state[2]
        velocity_y = estimated_state[3]
        
        # Convert to absolute angles
        estimated_pan = camera_pan + estimated_pan_rel
        estimated_tilt = camera_tilt + estimated_tilt_rel
        
        # Motion consistency check
        measurement_covariance = np.eye(2) * self.config.tracking.measurement_noise
        consistency_result = self.motion_consistency.check(
            (estimated_pan_rel, estimated_tilt_rel),
            estimated_state,
            estimated_covariance,
            measurement_covariance,
            visible,
            detection.confidence
        )
        
        # Update state machine
        diagnostics = self.state_machine.update(
            self.current_time,
            visible,
            detection.centroid_x is not None,
            detection.confidence,
            consistency_result.gate_passed,
            estimated_covariance[0, 0]  # Position uncertainty
        )
        
        # Generate camera command
        tracking_mode = self.state_machine.get_mode()
        command, control_diagnostics = self.controller.update(
            target_pan, target_tilt, velocity_x, velocity_y,
            tracking_mode, self.dt, self.current_time
        )
        
        # Apply command through camera slew limits
        self.camera.apply_command(command.pan_command, command.tilt_command, self.dt)
        
        # Calculate tracking error
        error_pan = target_pan - camera_pan
        error_tilt = target_tilt - camera_tilt
        
        # Record step
        step = SimulationStep(
            timestamp=self.current_time,
            target_pan=target_pan,
            target_tilt=target_tilt,
            camera_pan=camera_pan,
            camera_tilt=camera_tilt,
            relative_pan=relative_pan,
            relative_tilt=relative_tilt,
            detection_pan=measured_pan if visible else None,
            detection_tilt=measured_tilt if visible else None,
            estimated_pan=estimated_pan,
            estimated_tilt=estimated_tilt,
            velocity_x=velocity_x,
            velocity_y=velocity_y,
            command_pan=command.pan_command,
            command_tilt=command.tilt_command,
            tracking_mode=tracking_mode,
            error_pan=error_pan,
            error_tilt=error_tilt
        )
        
        self.history.append(step)
        self.frame_id += 1
        
        return step
    
    def run(self) -> SimulationResult:
        """Run full simulation.
        
        Returns:
            SimulationResult with history and summary
        """
        self.reset()
        
        # Generate full trajectory
        trajectory = self.trajectory_gen.generate()
        total_steps = len(trajectory)
        
        # Run all steps
        for _ in range(total_steps):
            self.step()
        
        # Calculate final error
        if self.history:
            final_step = self.history[-1]
            final_error = np.sqrt(final_step.error_pan**2 + final_step.error_tilt**2)
        else:
            final_error = 0.0
        
        return SimulationResult(
            history=self.history.copy(),
            final_error=final_error,
            final_mode=self.state_machine.get_mode(),
            duration=self.current_time,
            steps=len(self.history)
        )
    
    def get_history(self) -> List[SimulationStep]:
        """Get simulation history.
        
        Returns:
            List of SimulationStep
        """
        return self.history.copy()
    
    def get_summary(self) -> Dict[str, Any]:
        """Get simulation summary.
        
        Returns:
            Dictionary with summary statistics
        """
        if not self.history:
            return {}
        
        errors = [np.sqrt(s.error_pan**2 + s.error_tilt**2) for s in self.history]
        
        return {
            "duration": self.current_time,
            "steps": len(self.history),
            "final_error": errors[-1],
            "mean_error": np.mean(errors),
            "max_error": np.max(errors),
            "min_error": np.min(errors),
            "final_mode": self.history[-1].tracking_mode.value,
            "camera_pan": self.history[-1].camera_pan,
            "camera_tilt": self.history[-1].camera_tilt
        }