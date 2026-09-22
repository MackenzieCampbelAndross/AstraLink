"""Physical consistency validator comparing Member 2 predictions with optical responses under uncertainty."""

import math
from dataclasses import dataclass
from typing import Dict, List, Optional

from src.tracking import TrackingState
from .probe_generator import OpticalChallenge
from .probe_response import OpticalResponse


@dataclass(frozen=True)
class PhysicalValidationResult:
    """Structured result of physical consistency evaluation."""

    valid: bool
    position_error: float
    velocity_consistency: float
    signal_valid: bool
    reason: str

    def to_dict(self) -> Dict[str, float]:
        return {
            "valid": self.valid,
            "position_error": round(self.position_error, 4),
            "velocity_consistency": round(self.velocity_consistency, 4),
            "signal_valid": self.signal_valid,
            "reason": self.reason,
        }

    def __repr__(self) -> str:
        return (
            f"PhysicalValidationResult(valid={self.valid}, error={self.position_error:.4f}, "
            f"signal_valid={self.signal_valid}, reason={self.reason!r})"
        )


class PhysicalConsistencyValidator:
    """Validates physical plausibility of optical responses using Member 2 covariance uncertainty."""

    def __init__(
        self,
        minimum_motion_consistency: float = 0.80,
        minimum_signal_quality: float = 0.50,
        uncertainty_sigma_threshold: float = 3.0,
    ):
        self.minimum_motion_consistency = float(minimum_motion_consistency)
        self.minimum_signal_quality = float(minimum_signal_quality)
        self.uncertainty_sigma_threshold = float(uncertainty_sigma_threshold)

    def validate(
        self,
        challenge: OpticalChallenge,
        responses: List[OpticalResponse],
        tracking_state: TrackingState,
        timeout_seconds: float = 0.500,
    ) -> PhysicalValidationResult:
        """Validate physical optical responses against tracking predictions and covariance uncertainty."""
        if not isinstance(challenge, OpticalChallenge):
            return PhysicalValidationResult(False, 999.0, 0.0, False, "INVALID_CHALLENGE_OBJECT")

        if not responses or not isinstance(responses, list):
            return PhysicalValidationResult(False, 999.0, 0.0, False, "EMPTY_OPTICAL_RESPONSES")

        if not isinstance(tracking_state, TrackingState):
            return PhysicalValidationResult(False, 999.0, 0.0, False, "INVALID_TRACKING_STATE")

        # 1. Match challenge probes to responses and check challenge_id
        probe_map = {p.probe_id: p for p in challenge.probes}
        total_error = 0.0
        response_count = 0

        for resp in responses:
            if resp.challenge_id != challenge.challenge_id:
                return PhysicalValidationResult(
                    False, 999.0, tracking_state.motion_consistency, False, "CHALLENGE_ID_MISMATCH"
                )

            if resp.probe_id not in probe_map:
                return PhysicalValidationResult(
                    False, 999.0, tracking_state.motion_consistency, False, f"UNKNOWN_PROBE_ID_{resp.probe_id}"
                )

            # Check timestamp freshness against challenge creation
            if resp.timestamp < challenge.creation_timestamp:
                return PhysicalValidationResult(
                    False, 999.0, tracking_state.motion_consistency, False, "STALE_OPTICAL_RESPONSE_TIMESTAMP"
                )

            if (resp.timestamp - challenge.creation_timestamp) > timeout_seconds:
                return PhysicalValidationResult(
                    False, 999.0, tracking_state.motion_consistency, False, "OPTICAL_CHALLENGE_TIMEOUT"
                )

            # Check signal quality
            if resp.signal_quality < self.minimum_signal_quality:
                return PhysicalValidationResult(
                    False,
                    999.0,
                    tracking_state.motion_consistency,
                    False,
                    f"SIGNAL_QUALITY_TOO_LOW ({resp.signal_quality:.2f} < {self.minimum_signal_quality:.2f})",
                )

            probe = probe_map[resp.probe_id]
            dx = resp.angular_response_x - probe.expected_angular_x
            dy = resp.angular_response_y - probe.expected_angular_y
            err = math.sqrt(dx * dx + dy * dy)
            total_error += err
            response_count += 1

        avg_error = total_error / max(1, response_count)

        # 2. Check Member 2 motion consistency
        if tracking_state.motion_consistency < self.minimum_motion_consistency:
            return PhysicalValidationResult(
                False,
                avg_error,
                tracking_state.motion_consistency,
                True,
                f"MOTION_CONSISTENCY_TOO_LOW ({tracking_state.motion_consistency:.2f} < {self.minimum_motion_consistency:.2f})",
            )

        # 3. Covariance-aware uncertainty validation
        cov = tracking_state.prediction_covariance
        var_x = cov[0] if len(cov) > 0 else 0.1
        var_y = cov[1] if len(cov) > 1 else 0.1
        sigma = math.sqrt(var_x + var_y)
        allowed_uncertainty = self.uncertainty_sigma_threshold * sigma

        if avg_error > allowed_uncertainty:
            return PhysicalValidationResult(
                False,
                avg_error,
                tracking_state.motion_consistency,
                True,
                f"POSITION_ERROR_EXCEEDS_UNCERTAINTY (error={avg_error:.4f} > max_allowed={allowed_uncertainty:.4f})",
            )

        return PhysicalValidationResult(
            True,
            avg_error,
            tracking_state.motion_consistency,
            True,
            "PHYSICAL_VALIDATION_SUCCESS",
        )
