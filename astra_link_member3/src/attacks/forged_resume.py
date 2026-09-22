"""Attack 5: Forged Resume Checkpoint Attack Simulation."""

import time
from typing import Optional, Tuple

from ..recovery.resume import ResumeProtocolHandler, ResumeResponse, ResumeValidationError
from ..trust import SecurityLogger


class ForgedResumeAttack:
    """Simulates injection of fake or malicious resume responses into transfer recovery state."""

    def __init__(self, logger: Optional[SecurityLogger] = None):
        self.logger = logger or SecurityLogger()
        self.attempts_count: int = 0
        self.rejections_count: int = 0

    def generate_forged_resume_response(
        self,
        transfer_id: str,
        session_id: str,
        tracking_epoch: int,
        total_packets: int,
        scenario: str = "EXCESSIVE_CHECKPOINT",
    ) -> ResumeResponse:
        """Generate forged ResumeResponse."""
        now = round(time.time(), 3)
        if scenario == "EXCESSIVE_CHECKPOINT":
            return ResumeResponse(
                transfer_id=transfer_id,
                receiver_verified_checkpoint=10000,  # Far higher than real checkpoint
                total_packets=total_packets,
                tracking_epoch=tracking_epoch,
                session_id=session_id,
                timestamp=now,
                status="ACCEPTED",
                reason="RESUME_AUTHORIZED",
            )
        elif scenario == "NEGATIVE_CHECKPOINT":
            return ResumeResponse(
                transfer_id=transfer_id,
                receiver_verified_checkpoint=-1,
                total_packets=total_packets,
                tracking_epoch=tracking_epoch,
                session_id=session_id,
                timestamp=now,
                status="ACCEPTED",
                reason="RESUME_AUTHORIZED",
            )
        elif scenario == "EXCEEDS_TOTAL_PACKETS":
            return ResumeResponse(
                transfer_id=transfer_id,
                receiver_verified_checkpoint=total_packets + 500,
                total_packets=total_packets,
                tracking_epoch=tracking_epoch,
                session_id=session_id,
                timestamp=now,
                status="ACCEPTED",
                reason="RESUME_AUTHORIZED",
            )
        elif scenario == "WRONG_TRANSFER":
            return ResumeResponse(
                transfer_id="TX_FORGED_999",
                receiver_verified_checkpoint=50,
                total_packets=total_packets,
                tracking_epoch=tracking_epoch,
                session_id=session_id,
                timestamp=now,
                status="ACCEPTED",
                reason="RESUME_AUTHORIZED",
            )
        elif scenario == "WRONG_SESSION":
            return ResumeResponse(
                transfer_id=transfer_id,
                receiver_verified_checkpoint=50,
                total_packets=total_packets,
                tracking_epoch=tracking_epoch,
                session_id="SESS_FORGED_999",
                timestamp=now,
                status="ACCEPTED",
                reason="RESUME_AUTHORIZED",
            )
        elif scenario == "WRONG_EPOCH":
            return ResumeResponse(
                transfer_id=transfer_id,
                receiver_verified_checkpoint=50,
                total_packets=total_packets,
                tracking_epoch=tracking_epoch + 5,
                session_id=session_id,
                timestamp=now,
                status="ACCEPTED",
                reason="RESUME_AUTHORIZED",
            )
        else:
            raise ValueError(f"Unknown scenario: {scenario}")

    def test_forged_resume(
        self,
        response: ResumeResponse,
        expected_transfer_id: str,
        expected_epoch: int,
        expected_session_id: str,
        sender_checkpoint: int,
        total_packets: int,
        scenario: str = "FORGED_RESUME",
    ) -> Tuple[bool, str]:
        """Validate forged resume response and verify rejection."""
        self.attempts_count += 1
        self.logger.log_event(
            "FORGED_RESUME_ATTEMPT",
            "SENDER",
            "ATTACKER",
            {
                "scenario": scenario,
                "claimed_checkpoint": response.receiver_verified_checkpoint,
                "expected_session": expected_session_id[:8],
            },
        )

        try:
            ResumeProtocolHandler.validate_response(
                response=response,
                expected_transfer_id=expected_transfer_id,
                expected_epoch=expected_epoch,
                expected_session_id=expected_session_id,
                sender_checkpoint=sender_checkpoint,
                total_packets=total_packets,
            )
            return True, "FORGED_RESUME_ACCEPTED_UNEXPECTED"
        except ResumeValidationError as e:
            self.rejections_count += 1
            self.logger.log_event(
                "FORGED_RESUME_REJECTED",
                "SENDER",
                "ATTACKER",
                {"scenario": scenario, "reason": str(e)},
            )
            return False, f"FORGED_RESUME_REJECTED: {e}"
