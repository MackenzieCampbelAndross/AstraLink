"""Control module: PID control, feedforward control, slew limiting."""

from astra_link_tracking.control.pid import PIDController
from astra_link_tracking.control.feedforward import VelocityFeedforward
from astra_link_tracking.control.slew_limit import SlewLimiter, SlewLimiterPair
from astra_link_tracking.control.controller import CameraController, ControlDiagnostics

__all__ = [
    "PIDController",
    "VelocityFeedforward",
    "SlewLimiter",
    "SlewLimiterPair",
    "CameraController",
    "ControlDiagnostics",
]
