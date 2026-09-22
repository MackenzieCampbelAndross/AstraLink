"""Integrated Tracking & Security Pipeline.

Connects Member 2 Optical Tracking output through the TrackingAdapter into Member 3 Security Validation,
Trust Engine evaluation, and Transmission Authorization.

Pipeline Flow:
    Member 2 Tracker
           ↓
    M2 TrackingState
           ↓
    Integration Adapter (TrackingAdapter)
           ↓
    Member 3 Tracking Validity Evaluator
           ↓
    Member 3 Trust Engine
           ↓
    Member 3 Transmission Authorization Gate
"""

import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

_repo_root = Path(__file__).resolve().parent.parent
_m2_src = _repo_root / "astra-link-member2" / "src"
_m3_root = _repo_root / "astra_link_member3"

if _m2_src.exists() and str(_m2_src) not in sys.path:
    sys.path.insert(0, str(_m2_src))
if _m3_root.exists() and str(_m3_root) not in sys.path:
    sys.path.insert(0, str(_m3_root))

from .adapter import TrackingAdapter
from src.tracking.tracking_state import TrackingValidityEvaluator, TrackingState as M3TrackingState
from src.trust.trust_engine import TrustEngine, TrustEvaluationResult
from src.trust.authorization import TransmissionAuthorizationGate, TransmissionAuthorizationResult
from src.optical_challenge.physical_validation import PhysicalValidationResult


class IntegratedTrackingSecurityPipeline:
    """Integrated End-to-End Pipeline connecting Member 2 Tracking telemetry to Member 3 Security Gates."""

    def __init__(self, min_motion_consistency: float = 0.80):
        self.min_motion_consistency = float(min_motion_consistency)
        self.adapter = TrackingAdapter()
        self.tracking_evaluator = TrackingValidityEvaluator(min_motion_consistency=self.min_motion_consistency)
        self.trust_engine = TrustEngine(min_motion_consistency=self.min_motion_consistency)
        self.gate = TransmissionAuthorizationGate()

    def process_telemetry(
        self,
        m2_tracking_state: Any,
        terminal_id: str,
        remote_terminal_id: str,
        authentication_valid: bool = True,
        freshness_valid: bool = True,
        physical_validation_result: Optional[PhysicalValidationResult] = None,
    ) -> Tuple[M3TrackingState, TrustEvaluationResult, TransmissionAuthorizationResult]:
        """Execute the integrated pipeline.

        Args:
            m2_tracking_state: Member 2 TrackingState instance.
            terminal_id: Local terminal identifier.
            remote_terminal_id: Remote target terminal identifier.
            authentication_valid: Result of cryptographic mutual authentication.
            freshness_valid: Temporal freshness validation result.
            physical_validation_result: Optical challenge physical response validation result.

        Returns:
            Tuple containing:
                - adapted_m3_state (M3TrackingState)
                - trust_result (TrustEvaluationResult)
                - authorization_result (TransmissionAuthorizationResult)
        """
        # Step 1: Adapt Member 2 TrackingState -> Member 3 Security TrackingState
        m3_tracking_state = self.adapter.adapt(m2_tracking_state)

        # Step 2: Member 3 Tracking Validity Evaluation
        is_tracking_valid, tracking_reason = self.tracking_evaluator.evaluate(m3_tracking_state)

        # Step 3: Member 3 Multi-Domain Trust Engine Evaluation
        trust_result = self.trust_engine.evaluate(
            terminal_id=terminal_id,
            remote_terminal_id=remote_terminal_id,
            tracking_state=m3_tracking_state,
            authentication_valid=authentication_valid,
            freshness_valid=freshness_valid,
            physical_validation_result=physical_validation_result,
        )

        # Step 4: Transmission Authorization Gate Decision
        authorization_result = self.gate.can_transmit(
            trust_result=trust_result,
            terminal_id=terminal_id,
            remote_terminal_id=remote_terminal_id,
        )

        return m3_tracking_state, trust_result, authorization_result
