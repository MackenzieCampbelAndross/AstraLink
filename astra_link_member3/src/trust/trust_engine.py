"""Trust Engine evaluating tracking, authentication, freshness, and physical consistency."""

from dataclasses import dataclass
from typing import Any, Dict, Optional

from src.optical_challenge import PhysicalValidationResult
from src.tracking import TrackingState
from .events import SecurityLogger
from .security_state import SecurityState


@dataclass(frozen=True)
class TrustEvaluationResult:
    """Structured result of TrustEngine evaluation."""

    security_state: SecurityState
    trust_authorized: bool
    tracking_valid: bool
    motion_consistent: bool
    authentication_valid: bool
    freshness_valid: bool
    physical_valid: bool
    reason: str
    details: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "security_state": self.security_state.value,
            "trust_authorized": self.trust_authorized,
            "tracking_valid": self.tracking_valid,
            "motion_consistent": self.motion_consistent,
            "authentication_valid": self.authentication_valid,
            "freshness_valid": self.freshness_valid,
            "physical_valid": self.physical_valid,
            "reason": self.reason,
            "details": self.details,
        }

    def __repr__(self) -> str:
        return (
            f"TrustEvaluationResult(state={self.security_state.value}, authorized={self.trust_authorized}, "
            f"reason={self.reason!r})"
        )


class TrustEngine:
    """Evaluates multi-domain security criteria to establish terminal trust state."""

    def __init__(self, min_motion_consistency: float = 0.80):
        self.min_motion_consistency = float(min_motion_consistency)

    def evaluate(
        self,
        terminal_id: str,
        remote_terminal_id: str,
        tracking_state: TrackingState,
        authentication_valid: bool,
        freshness_valid: bool = True,
        physical_validation_result: Optional[PhysicalValidationResult] = None,
        logger: Optional[SecurityLogger] = None,
    ) -> TrustEvaluationResult:
        """Evaluate tracking, authentication, freshness, and optical response consistency."""
        tracking_valid = tracking_state.is_locked if tracking_state else False
        motion_consistent = (
            tracking_state.motion_consistency >= self.min_motion_consistency if tracking_state else False
        )
        phys_valid = physical_validation_result.valid if physical_validation_result else True

        if logger and tracking_valid:
            logger.log_event("TRACKING_LOCKED", terminal_id, remote_terminal_id, {"state": tracking_state.tracking_state})
            logger.log_event("LOCKED_UNVERIFIED", terminal_id, remote_terminal_id)

        # Hard Gate 1: Tracking State
        if not tracking_valid:
            if logger:
                logger.log_event("TRUST_DEGRADED", terminal_id, remote_terminal_id, {"reason": "TRACKING_NOT_LOCKED"})
            return TrustEvaluationResult(
                security_state=SecurityState.BLOCKED,
                trust_authorized=False,
                tracking_valid=False,
                motion_consistent=motion_consistent,
                authentication_valid=authentication_valid,
                freshness_valid=freshness_valid,
                physical_valid=phys_valid,
                reason=f"TARGET_TRACKING_NOT_LOCKED ({tracking_state.tracking_state if tracking_state else 'NONE'})",
                details={"tracking_state": tracking_state.tracking_state if tracking_state else "NONE"},
            )

        # Hard Gate 2: Cryptographic Authentication
        if not authentication_valid:
            if logger:
                logger.log_event("TRANSMISSION_BLOCKED", terminal_id, remote_terminal_id, {"reason": "AUTHENTICATION_INVALID"})
            return TrustEvaluationResult(
                security_state=SecurityState.UNTRUSTED,
                trust_authorized=False,
                tracking_valid=True,
                motion_consistent=motion_consistent,
                authentication_valid=False,
                freshness_valid=freshness_valid,
                physical_valid=phys_valid,
                reason="CRYPTOGRAPHIC_AUTHENTICATION_FAILED",
                details={},
            )

        # Hard Gate 3: Temporal Freshness
        if not freshness_valid:
            if logger:
                logger.log_event("TRANSMISSION_BLOCKED", terminal_id, remote_terminal_id, {"reason": "FRESHNESS_INVALID"})
            return TrustEvaluationResult(
                security_state=SecurityState.UNTRUSTED,
                trust_authorized=False,
                tracking_valid=True,
                motion_consistent=motion_consistent,
                authentication_valid=True,
                freshness_valid=False,
                physical_valid=phys_valid,
                reason="TEMPORAL_FRESHNESS_FAILED",
                details={},
            )

        # Hard Gate 4: Motion Consistency
        if not motion_consistent:
            if logger:
                logger.log_event("TRUST_DEGRADED", terminal_id, remote_terminal_id, {"reason": "LOW_MOTION_CONSISTENCY"})
            return TrustEvaluationResult(
                security_state=SecurityState.DEGRADED,
                trust_authorized=False,
                tracking_valid=True,
                motion_consistent=False,
                authentication_valid=True,
                freshness_valid=True,
                physical_valid=phys_valid,
                reason=f"MOTION_CONSISTENCY_TOO_LOW ({tracking_state.motion_consistency:.2f} < {self.min_motion_consistency:.2f})",
                details={"motion_consistency": tracking_state.motion_consistency},
            )

        # Hard Gate 5: Physical Consistency
        if physical_validation_result and not physical_validation_result.valid:
            if logger:
                logger.log_event("PHYSICAL_VALIDATION_FAILURE", terminal_id, remote_terminal_id, {"reason": physical_validation_result.reason})
                logger.log_event("TRUST_DEGRADED", terminal_id, remote_terminal_id, {"reason": "PHYSICAL_VALIDATION_FAILED"})
            return TrustEvaluationResult(
                security_state=SecurityState.DEGRADED,
                trust_authorized=False,
                tracking_valid=True,
                motion_consistent=True,
                authentication_valid=True,
                freshness_valid=True,
                physical_valid=False,
                reason=f"PHYSICAL_CONSISTENCY_FAILED ({physical_validation_result.reason})",
                details=physical_validation_result.to_dict(),
            )

        # All 5 Gates Pass
        if logger:
            if physical_validation_result:
                logger.log_event("PHYSICAL_VALIDATION_SUCCESS", terminal_id, remote_terminal_id)
            logger.log_event("TRUST_AUTHORIZED", terminal_id, remote_terminal_id)

        return TrustEvaluationResult(
            security_state=SecurityState.AUTHORIZED,
            trust_authorized=True,
            tracking_valid=True,
            motion_consistent=True,
            authentication_valid=True,
            freshness_valid=True,
            physical_valid=True,
            reason="TRUST_AUTHORIZED_SUCCESS",
            details={},
        )
