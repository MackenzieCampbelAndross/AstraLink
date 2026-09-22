"""Member 2 Tracking State data models and validation helper."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple


@dataclass(frozen=True)
class TrackingState:
    """Represents the optical tracking state input provided by Member 2."""

    timestamp: float
    tracking_state: str
    predicted_x: float
    predicted_y: float
    angular_x: float
    angular_y: float
    velocity_x: float
    velocity_y: float
    motion_consistency: float
    prediction_covariance: List[float] = field(default_factory=lambda: [0.1, 0.1])

    @property
    def is_locked(self) -> bool:
        """Return True if tracking_state is LOCKED."""
        return self.tracking_state.upper() == "LOCKED"

    def to_dict(self) -> Dict[str, Any]:
        """Serialize tracking state to dictionary."""
        return {
            "timestamp": self.timestamp,
            "tracking_state": self.tracking_state,
            "predicted_x": self.predicted_x,
            "predicted_y": self.predicted_y,
            "angular_x": self.angular_x,
            "angular_y": self.angular_y,
            "velocity_x": self.velocity_x,
            "velocity_y": self.velocity_y,
            "motion_consistency": self.motion_consistency,
            "prediction_covariance": list(self.prediction_covariance),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TrackingState":
        """Deserialize tracking state from dictionary."""
        required = [
            "timestamp",
            "tracking_state",
            "predicted_x",
            "predicted_y",
            "angular_x",
            "angular_y",
            "velocity_x",
            "velocity_y",
            "motion_consistency",
        ]
        for f in required:
            if f not in data:
                raise ValueError(f"Missing required TrackingState field: {f}")

        cov = data.get("prediction_covariance", [0.1, 0.1])
        return cls(
            timestamp=float(data["timestamp"]),
            tracking_state=str(data["tracking_state"]),
            predicted_x=float(data["predicted_x"]),
            predicted_y=float(data["predicted_y"]),
            angular_x=float(data["angular_x"]),
            angular_y=float(data["angular_y"]),
            velocity_x=float(data["velocity_x"]),
            velocity_y=float(data["velocity_y"]),
            motion_consistency=float(data["motion_consistency"]),
            prediction_covariance=[float(x) for x in cov],
        )

    def __repr__(self) -> str:
        return (
            f"TrackingState(state={self.tracking_state!r}, angular=({self.angular_x:.3f}, {self.angular_y:.3f}), "
            f"motion_consistency={self.motion_consistency:.2f})"
        )


class TrackingValidityEvaluator:
    """Evaluates whether Member 2 tracking state is valid for security processing."""

    def __init__(self, min_motion_consistency: float = 0.80):
        self.min_motion_consistency = float(min_motion_consistency)

    def evaluate(self, state: TrackingState) -> Tuple[bool, str]:
        """Evaluate tracking validity.
        
        Returns:
            Tuple of (is_valid: bool, reason: str)
        """
        if not isinstance(state, TrackingState):
            return False, "INVALID_TRACKING_OBJECT"

        if not state.is_locked:
            return False, f"TARGET_NOT_LOCKED_{state.tracking_state.upper()}"

        if state.motion_consistency < self.min_motion_consistency:
            return False, f"MOTION_CONSISTENCY_TOO_LOW ({state.motion_consistency:.2f} < {self.min_motion_consistency:.2f})"

        return True, "TRACKING_VALID_LOCKED"
