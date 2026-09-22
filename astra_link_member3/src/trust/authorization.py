"""Programmatic transmission authorization gate for Astra Link."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .events import SecurityLogger
from .trust_engine import TrustEvaluationResult


@dataclass(frozen=True)
class TransmissionAuthorizationResult:
    """Structured result returned by the TransmissionAuthorizationGate."""

    authorized: bool
    allowed: bool
    reason: str
    failed_conditions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "authorized": self.authorized,
            "allowed": self.allowed,
            "reason": self.reason,
            "failed_conditions": list(self.failed_conditions),
        }

    def __repr__(self) -> str:
        return (
            f"TransmissionAuthorizationResult(allowed={self.allowed}, "
            f"reason={self.reason!r}, failed={self.failed_conditions})"
        )


class TransmissionAuthorizationGate:
    """Enforces programmatic transmission authorization gates.
    
    This gate cannot be bypassed by GUI or higher-level application logic.
    """

    @staticmethod
    def can_transmit(
        trust_result: TrustEvaluationResult,
        logger: Optional[SecurityLogger] = None,
        terminal_id: str = "T1",
        remote_terminal_id: str = "T2",
    ) -> TransmissionAuthorizationResult:
        """Evaluate if transmission is permitted based on TrustEvaluationResult.
        
        Mandatory authorization requirements:
            - tracking_valid == True
            - motion_consistent == True
            - authentication_valid == True
            - freshness_valid == True
            - physical_valid == True
            - trust_authorized == True
        """
        if not isinstance(trust_result, TrustEvaluationResult):
            if logger:
                logger.log_event("TRANSMISSION_BLOCKED", terminal_id, remote_terminal_id, {"reason": "INVALID_TRUST_RESULT"})
            return TransmissionAuthorizationResult(
                authorized=False,
                allowed=False,
                reason="INVALID_TRUST_RESULT_OBJECT",
                failed_conditions=["INVALID_TRUST_RESULT_OBJECT"],
            )

        failed = []
        if not trust_result.tracking_valid:
            failed.append("TRACKING_NOT_LOCKED")
        if not trust_result.motion_consistent:
            failed.append("MOTION_INCONSISTENT")
        if not trust_result.authentication_valid:
            failed.append("AUTHENTICATION_INVALID")
        if not trust_result.freshness_valid:
            failed.append("FRESHNESS_INVALID")
        if not trust_result.physical_valid:
            failed.append("PHYSICAL_VALIDATION_FAILED")
        if not trust_result.trust_authorized:
            failed.append("TRUST_NOT_AUTHORIZED")

        if failed:
            if logger:
                logger.log_event(
                    "TRANSMISSION_BLOCKED",
                    terminal_id,
                    remote_terminal_id,
                    {"reason": trust_result.reason, "failed_conditions": failed},
                )
            return TransmissionAuthorizationResult(
                authorized=False,
                allowed=False,
                reason=trust_result.reason,
                failed_conditions=failed,
            )

        if logger:
            logger.log_event("TRANSMISSION_AUTHORIZED", terminal_id, remote_terminal_id)

        return TransmissionAuthorizationResult(
            authorized=True,
            allowed=True,
            reason="TRANSMISSION_PERMITTED",
            failed_conditions=[],
        )
