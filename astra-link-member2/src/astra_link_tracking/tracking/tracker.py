"""Main tracker integrating coordinate transforms, Kalman filter, motion consistency, state machine, control, and reacquisition."""

from typing import Optional, Tuple, Dict, Any, Union
import numpy as np
import uuid

from astra_link_tracking.models.config import TrackingSystemConfig, CameraConfig, ControlConfig, TrackingConfig, ReacquisitionConfig
from astra_link_tracking.models.interfaces import (
    DetectionResult,
    CameraCommand,
    TrackingState,
    TrackingMode,
)
from astra_link_tracking.tracking.coordinate_transform import CoordinateTransform
from astra_link_tracking.tracking.kalman import KalmanFilter
from astra_link_tracking.tracking.motion_consistency import MotionConsistencyChecker
from astra_link_tracking.tracking.state_machine import TrackingStateMachine
from astra_link_tracking.control.controller import CameraController
from astra_link_tracking.reacquisition.reacquisition_controller import ReacquisitionController


class Tracker:
    """Main optical tracker integrating all Member 2 tracking & control components.
    
    Coordinates:
        DetectionResult -> Pixel/Angular Transform -> Kalman Filter (predict/update)
        -> Mahalanobis/Motion Consistency Gate -> Tracking State Machine
        -> Automatic Reacquisition Search -> Camera Controller -> TrackingState & CameraCommand
    """

    def __init__(self, config: Optional[Union[TrackingSystemConfig, Dict[str, Any]]] = None):
        """Initialize tracker with configuration.

        Args:
            config: TrackingSystemConfig instance, configuration dictionary, or None for defaults.
        """
        if config is None:
            self.sys_config = TrackingSystemConfig()
        elif isinstance(config, TrackingSystemConfig):
            self.sys_config = config
        elif isinstance(config, dict):
            if "CAMERA" in config or "TRACKING" in config:
                self.sys_config = TrackingSystemConfig.from_dict(config)
            elif "tracking" in config or "camera" in config:
                camera_dict = config.get("camera", config.get("tracking", {}).get("camera", {}))
                control_dict = config.get("control", config.get("tracking", {}).get("control", {}))
                self.sys_config = TrackingSystemConfig(
                    camera=CameraConfig(**camera_dict) if isinstance(camera_dict, dict) and camera_dict else CameraConfig(),
                    control=ControlConfig(**control_dict) if isinstance(control_dict, dict) and control_dict else ControlConfig(),
                    tracking=TrackingConfig(),
                )
            else:
                self.sys_config = TrackingSystemConfig()
        else:
            self.sys_config = TrackingSystemConfig()

        self.sys_config.validate()

        # Initialize tracking sub-components
        self.coord_transform = CoordinateTransform(self.sys_config.camera)
        self.kalman = KalmanFilter(self.sys_config.tracking)
        self.motion_checker = MotionConsistencyChecker(self.sys_config.tracking)
        self.state_machine = TrackingStateMachine(self.sys_config.tracking)
        self.controller = CameraController(self.sys_config.control)
        self.reacquisition = ReacquisitionController(
            config=self.sys_config.reacquisition,
            control_config=self.sys_config.control,
            tracking_config=self.sys_config.tracking,
        )

        # Operational tracker state
        self.tracking_id = str(uuid.uuid4())
        self.current_time = 0.0
        self.current_pan = 0.0
        self.current_tilt = 0.0
        self.frame_id = 0

    def update(
        self,
        detection: Optional[DetectionResult],
        dt: float = 0.05
    ) -> Tuple[TrackingState, CameraCommand]:
        """Update tracker with a new detection frame.

        Args:
            detection: DetectionResult from optical sensor, or None if no detection.
            dt: Default time step in seconds if detection timestamp is omitted.

        Returns:
            Tuple of (TrackingState, CameraCommand).
        """
        # 1. Determine timestamp & step
        if detection and detection.timestamp > 0.0:
            timestamp = float(detection.timestamp)
        else:
            timestamp = self.current_time + dt if self.current_time > 0.0 else dt

        dt_step = max(0.001, timestamp - self.current_time) if self.current_time > 0.0 else dt
        self.current_time = timestamp
        self.frame_id = detection.frame_id if detection else self.frame_id + 1

        # 2. Check measurement visibility and valid centroids
        visible = bool(
            detection
            and detection.visible
            and detection.centroid_x is not None
            and detection.centroid_y is not None
        )
        confidence = float(detection.confidence) if (detection and visible) else 0.0

        # 3. Kalman prediction & measurement update
        if visible and detection.centroid_x is not None and detection.centroid_y is not None:
            angle_x, angle_y = self.coord_transform.pixel_to_angle(
                float(detection.centroid_x),
                float(detection.centroid_y)
            )

            if not self.kalman.initialized:
                self.kalman.initialize(angle_x, angle_y, timestamp)
            else:
                self.kalman.predict(timestamp)
                self.kalman.update(angle_x, angle_y, confidence)
        else:
            if self.kalman.initialized:
                self.kalman.predict(timestamp)

        # 4. Extract state estimates and covariance
        if self.kalman.initialized:
            estimated_state = self.kalman.get_state()  # [angle_x, angle_y, vel_x, vel_y]
            estimated_cov = self.kalman.get_covariance()
        else:
            estimated_state = np.zeros(4)
            estimated_cov = np.eye(4) * 10.0

        angle_x = float(estimated_state[0])
        angle_y = float(estimated_state[1])
        vel_x = float(estimated_state[2])
        vel_y = float(estimated_state[3])
        pos_cov_2x2 = estimated_cov[:2, :2]
        pos_uncertainty = float(estimated_cov[0, 0])

        # 5. Check motion & Mahalanobis consistency
        measurement_cov = np.eye(2) * self.sys_config.tracking.measurement_noise
        consistency_result = self.motion_checker.check(
            (angle_x, angle_y),
            estimated_state,
            estimated_cov,
            measurement_cov,
            visible,
            confidence
        )
        is_consistent = bool(consistency_result.gate_passed)

        # 6. Update tracking state machine
        diag = self.state_machine.update(
            timestamp=timestamp,
            detection_visible=visible,
            detection_valid=visible,
            confidence=confidence,
            gate_passed=is_consistent,
            prediction_uncertainty=pos_uncertainty,
        )
        current_mode = self.state_machine.get_mode()

        # 7. Handle automatic reacquisition in COASTING or LOST modes
        target_pan = self.current_pan + angle_x
        target_tilt = self.current_tilt + angle_y

        if current_mode in (TrackingMode.COASTING, TrackingMode.LOST):
            if not self.reacquisition.is_active():
                self.reacquisition.start(
                    position=(target_pan, target_tilt),
                    velocity=(vel_x, vel_y),
                    covariance=pos_cov_2x2,
                    timestamp=timestamp
                )

            if detection and visible:
                reacquired = self.reacquisition.process_detection(
                    detection=detection,
                    estimated_state=estimated_state,
                    estimated_covariance=estimated_cov,
                    timestamp=timestamp
                )
                if reacquired:
                    # Transition back to LOCKED upon confirmed reacquisition
                    self.state_machine.consecutive_valid_frames = self.state_machine.confirmation_frames
                    self.state_machine.current_mode = TrackingMode.LOCKED
                    current_mode = TrackingMode.LOCKED
                    self.reacquisition.reset()

            if current_mode != TrackingMode.LOCKED:
                search_target = self.reacquisition.step(dt_step, (self.current_pan, self.current_tilt))
                target_pan, target_tilt = search_target[0], search_target[1]
        else:
            if self.reacquisition.is_active():
                self.reacquisition.reset()

        # 8. Generate PTZ camera command
        allow_lost_control = (current_mode in (TrackingMode.COASTING, TrackingMode.LOST))
        command, control_diag = self.controller.update(
            target_pan=target_pan,
            target_tilt=target_tilt,
            velocity_x=vel_x,
            velocity_y=vel_y,
            tracking_mode=current_mode,
            dt=dt_step,
            timestamp=timestamp,
            allow_lost_control=allow_lost_control
        )
        self.current_pan = command.pan_command
        self.current_tilt = command.tilt_command

        # 9. Convert angular estimates back to pixel domain for output interface
        pred_pixel_x, pred_pixel_y = self.coord_transform.angle_to_pixel(angle_x, angle_y)
        try:
            vel_pixel_x, vel_pixel_y = self.coord_transform.angular_velocity_to_pixel_velocity(vel_x, vel_y, dt_step)
        except ValueError:
            vel_pixel_x, vel_pixel_y = 0.0, 0.0

        # Construct TrackingState dataclass conforming to Member 2 interface
        tracking_state = TrackingState(
            timestamp=timestamp,
            state=current_mode,
            predicted_x=pred_pixel_x,
            predicted_y=pred_pixel_y,
            angular_x=angle_x,
            angular_y=angle_y,
            velocity_x=vel_pixel_x,
            velocity_y=vel_pixel_y,
            motion_consistency=is_consistent,
            prediction_uncertainty=pos_uncertainty,
            measurement_accepted=is_consistent and visible,
            confidence=confidence if (visible and is_consistent) else 0.0,
            time_since_last_detection=diag.time_since_last_detection,
            position_covariance=pos_cov_2x2,
            tracking_id=self.tracking_id,
            diagnostics={
                "frame_id": self.frame_id,
                "gate_passed": is_consistent,
                "reacquisition_active": self.reacquisition.is_active(),
            }
        )

        # Construct CameraCommand dataclass conforming to Member 2 interface
        camera_command = CameraCommand(
            timestamp=timestamp,
            pan_command=command.pan_command,
            tilt_command=command.tilt_command,
            slew_rate=command.slew_rate,
            command_mode=current_mode.value,
            diagnostics={
                "error_x": control_diag.error_x,
                "error_y": control_diag.error_y,
                "pid_x": control_diag.pid_x,
                "pid_y": control_diag.pid_y,
            }
        )

        return tracking_state, camera_command

    def reset(self):
        """Reset tracker to initial state."""
        self.kalman.reset((0.0, 0.0))
        self.motion_checker.reset()
        self.state_machine.reset()
        self.controller.reset()
        self.reacquisition.reset()
        self.tracking_id = str(uuid.uuid4())
        self.current_time = 0.0
        self.current_pan = 0.0
        self.current_tilt = 0.0
        self.frame_id = 0
