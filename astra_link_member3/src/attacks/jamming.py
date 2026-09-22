"""Attacks 8 & 9: Inconsistent Motion Anomaly & Optical Jamming / Degradation Simulation."""

from typing import Optional, Tuple

from ..optical_challenge import OpticalResponseSimulator, PhysicalConsistencyValidator, ProbeGenerator
from ..tracking import TrackingState
from ..trust import SecurityLogger, SecurityState, TransmissionAuthorizationGate, TrustEngine


class OpticalJammingAttack:
    """Simulates physical motion anomalies and optical jamming/degradation scenarios."""

    def __init__(
        self,
        trust_engine: Optional[TrustEngine] = None,
        logger: Optional[SecurityLogger] = None,
    ):
        self.trust_engine = trust_engine or TrustEngine()
        self.logger = logger or SecurityLogger()
        self.attempts_count: int = 0
        self.degradations_count: int = 0
        self.blocked_count: int = 0

    def test_inconsistent_motion_anomaly(
        self,
        terminal_id: str = "T1",
        remote_terminal_id: str = "T2",
    ) -> Tuple[bool, str]:
        """Attack 8: Valid cryptographic identity but low motion consistency / physical anomaly."""
        self.attempts_count += 1

        # Motion consistency low (0.35 < min_threshold 0.80)
        anomalous_tracking = TrackingState(
            timestamp=100.0,
            tracking_state="LOCKED",
            predicted_x=10.0,
            predicted_y=20.0,
            angular_x=0.01,
            angular_y=0.02,
            velocity_x=10.0,  # Sudden velocity jump
            velocity_y=20.0,
            motion_consistency=0.35,
        )

        trust_res = self.trust_engine.evaluate(
            terminal_id=terminal_id,
            remote_terminal_id=remote_terminal_id,
            tracking_state=anomalous_tracking,
            authentication_valid=True,
            freshness_valid=True,
        )

        auth_gate = TransmissionAuthorizationGate.can_transmit(
            trust_result=trust_res,
            logger=self.logger,
            terminal_id=terminal_id,
            remote_terminal_id=remote_terminal_id,
        )

        if not auth_gate.authorized:
            self.degradations_count += 1
            self.blocked_count += 1
            self.logger.log_event(
                "TRUST_DEGRADED",
                terminal_id,
                remote_terminal_id,
                {"reason": trust_res.reason, "security_state": trust_res.security_state.value},
            )
            self.logger.log_event(
                "TRANSMISSION_BLOCKED",
                terminal_id,
                remote_terminal_id,
                {"reason": trust_res.reason},
            )
            return False, f"MOTION_ANOMALY_BLOCKED: state={trust_res.security_state.value}, reason={trust_res.reason}"

        return True, "MOTION_ANOMALY_ACCEPTED_UNEXPECTED"

    def test_optical_jamming_degradation(
        self,
        terminal_id: str = "T1",
        remote_terminal_id: str = "T2",
    ) -> Tuple[bool, str]:
        """Attack 9: Optical jamming / high noise / beacon dropout."""
        self.attempts_count += 1

        # Beacon dropped / LOST due to jamming
        jammed_tracking = TrackingState(
            timestamp=100.0,
            tracking_state="LOST",
            predicted_x=0.0,
            predicted_y=0.0,
            angular_x=0.0,
            angular_y=0.0,
            velocity_x=0.0,
            velocity_y=0.0,
            motion_consistency=0.0,
        )

        trust_res = self.trust_engine.evaluate(
            terminal_id=terminal_id,
            remote_terminal_id=remote_terminal_id,
            tracking_state=jammed_tracking,
            authentication_valid=True,
            freshness_valid=True,
        )

        auth_gate = TransmissionAuthorizationGate.can_transmit(
            trust_result=trust_res,
            logger=self.logger,
            terminal_id=terminal_id,
            remote_terminal_id=remote_terminal_id,
        )

        if not auth_gate.authorized:
            self.blocked_count += 1
            self.logger.log_event(
                "TRANSMISSION_BLOCKED",
                terminal_id,
                remote_terminal_id,
                {"reason": "OPTICAL_JAMMING_BEACON_LOST"},
            )
            return False, f"OPTICAL_JAMMING_SUSPENDED: {trust_res.reason}"

        return True, "JAMMING_IGNORED_UNEXPECTED"
