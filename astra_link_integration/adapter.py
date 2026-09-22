"""Integration Adapter between Member 2 (Tracking & Vision) and Member 3 (Security & Trust).

Converts Member 2's TrackingState telemetry output into Member 3's Security TrackingState schema,
resolving type and field mismatches while strictly preserving security semantics.
"""

import sys
from pathlib import Path
from typing import Any, List, Tuple
import numpy as np

# Ensure Member 2 and Member 3 source paths are available
_repo_root = Path(__file__).resolve().parent.parent
_m2_src = _repo_root / "astra-link-member2" / "src"
_m3_root = _repo_root / "astra_link_member3"

if _m2_src.exists() and str(_m2_src) not in sys.path:
    sys.path.insert(0, str(_m2_src))
if _m3_root.exists() and str(_m3_root) not in sys.path:
    sys.path.insert(0, str(_m3_root))

from astra_link_tracking.models.interfaces import TrackingState as M2TrackingState, TrackingMode
from src.tracking.tracking_state import TrackingState as M3TrackingState


class TrackingAdapter:
    """Explicit boundary adapter mapping Member 2 telemetry outputs to Member 3 security inputs."""

    @staticmethod
    def adapt(m2_state: Any) -> M3TrackingState:
        """Convert a Member 2 TrackingState object into a Member 3 TrackingState dataclass.

        Contract Mapping:
            - timestamp: float -> timestamp: float
            - state: TrackingMode / str -> tracking_state: str ("LOCKED", "COASTING", "LOST", "SEARCH")
            - predicted_x: float -> predicted_x: float
            - predicted_y: float -> predicted_y: float
            - angular_x: float -> angular_x: float
            - angular_y: float -> angular_y: float
            - velocity_x: float -> velocity_x: float
            - velocity_y: float -> velocity_y: float
            - motion_consistency: bool/float + confidence -> motion_consistency: float [0.0, 1.0]
            - position_covariance / prediction_uncertainty -> prediction_covariance: List[float]

        Args:
            m2_state: Member 2 TrackingState instance (or object matching M2 contract).

        Returns:
            M3TrackingState: Member 3 Security TrackingState instance.

        Raises:
            ValueError: If m2_state is None, malformed, or missing required telemetry attributes.
        """
        if m2_state is None:
            raise ValueError("TrackingState cannot be None")

        # Required fields validation
        required_attrs = [
            "timestamp",
            "state",
            "predicted_x",
            "predicted_y",
            "angular_x",
            "angular_y",
            "velocity_x",
            "velocity_y",
        ]
        for attr in required_attrs:
            if not hasattr(m2_state, attr):
                raise ValueError(f"Malformed TrackingState: missing attribute '{attr}'")

        try:
            timestamp = float(m2_state.timestamp)
            predicted_x = float(m2_state.predicted_x)
            predicted_y = float(m2_state.predicted_y)
            angular_x = float(m2_state.angular_x)
            angular_y = float(m2_state.angular_y)
            velocity_x = float(m2_state.velocity_x)
            velocity_y = float(m2_state.velocity_y)
        except (TypeError, ValueError) as e:
            raise ValueError(f"Malformed TrackingState: numerical field conversion error: {e}")

        # Map state (TrackingMode enum or string) -> uppercase string
        raw_state = getattr(m2_state, "state", None)
        if isinstance(raw_state, TrackingMode):
            tracking_state = raw_state.value.upper()
        elif isinstance(raw_state, str):
            tracking_state = raw_state.upper()
        else:
            raise ValueError(f"Malformed TrackingState: invalid state type '{type(raw_state)}'")

        # Map motion consistency:
        # Member 2 uses boolean motion_consistency + float confidence [0.0, 1.0].
        # Member 3 expects a float score [0.0, 1.0].
        raw_consistency = getattr(m2_state, "motion_consistency", None)
        confidence = float(getattr(m2_state, "confidence", 1.0))

        if isinstance(raw_consistency, bool):
            if not raw_consistency:
                # Physically inconsistent motion -> 0.0 float score
                motion_consistency = 0.0
            else:
                # Physically consistent motion -> map confidence score (clamped [0.0, 1.0])
                motion_consistency = max(0.0, min(1.0, confidence))
        elif isinstance(raw_consistency, (float, int)):
            motion_consistency = max(0.0, min(1.0, float(raw_consistency)))
        else:
            raise ValueError(f"Malformed TrackingState: invalid motion_consistency type '{type(raw_consistency)}'")

        # Map prediction covariance / uncertainty:
        # Member 2 uses position_covariance (2x2 ndarray) or prediction_uncertainty (float).
        # Member 3 expects prediction_covariance (List[float]).
        pos_cov = getattr(m2_state, "position_covariance", None)
        pred_uncert = getattr(m2_state, "prediction_uncertainty", None)

        if pos_cov is not None:
            if isinstance(pos_cov, np.ndarray):
                if pos_cov.ndim == 2 and pos_cov.shape[0] >= 2 and pos_cov.shape[1] >= 2:
                    prediction_covariance = [float(pos_cov[0, 0]), float(pos_cov[1, 1])]
                else:
                    prediction_covariance = [float(x) for x in pos_cov.flatten()[:2]]
            elif isinstance(pos_cov, (list, tuple)) and len(pos_cov) >= 2:
                prediction_covariance = [float(pos_cov[0]), float(pos_cov[1])]
            else:
                prediction_covariance = [0.1, 0.1]
        elif pred_uncert is not None:
            uncert_val = float(pred_uncert)
            prediction_covariance = [uncert_val, uncert_val]
        else:
            prediction_covariance = [0.1, 0.1]

        return M3TrackingState(
            timestamp=timestamp,
            tracking_state=tracking_state,
            predicted_x=predicted_x,
            predicted_y=predicted_y,
            angular_x=angular_x,
            angular_y=angular_y,
            velocity_x=velocity_x,
            velocity_y=velocity_y,
            motion_consistency=motion_consistency,
            prediction_covariance=prediction_covariance,
        )
