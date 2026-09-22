"""Attack 4: Forged ACK Injection Attack Simulation."""

from typing import List, Optional, Tuple

from ..transport.ack import AckMessage
from ..transport.selective_repeat import SenderWindow
from ..trust import SecurityLogger


class ForgedAckAttack:
    """Simulates injection of forged or malicious ACK messages into SenderWindow ARQ state."""

    def __init__(self, logger: Optional[SecurityLogger] = None):
        self.logger = logger or SecurityLogger()
        self.attempts_count: int = 0
        self.rejections_count: int = 0

    def generate_forged_ack(
        self,
        session_id: str,
        transfer_id: str,
        scenario: str = "IMPOSSIBLE_SEQUENCE",
    ) -> AckMessage:
        """Generate a forged AckMessage targeting specific sender vulnerabilities."""
        if scenario == "UNKNOWN_TERMINAL":
            return AckMessage(
                protocol_version="1.0",
                session_id="SESS_UNKNOWN_TERMINAL",
                transfer_id=transfer_id,
                direction="T2_TO_T1",
                cumulative_ack=1,
                selective_ack=[],
            )
        elif scenario == "WRONG_SESSION":
            return AckMessage(
                protocol_version="1.0",
                session_id="SESS_WRONG_999",
                transfer_id=transfer_id,
                direction="T2_TO_T1",
                cumulative_ack=1,
                selective_ack=[],
            )
        elif scenario == "WRONG_TRANSFER":
            return AckMessage(
                protocol_version="1.0",
                session_id=session_id,
                transfer_id="TX_WRONG_999",
                direction="T2_TO_T1",
                cumulative_ack=1,
                selective_ack=[],
            )
        elif scenario == "IMPOSSIBLE_SEQUENCE":
            return AckMessage(
                protocol_version="1.0",
                session_id=session_id,
                transfer_id=transfer_id,
                direction="T2_TO_T1",
                cumulative_ack=999999,  # Impossible high sequence
                selective_ack=[1000000],
            )
        elif scenario == "PREMATURE_COMPLETION":
            return AckMessage(
                protocol_version="1.0",
                session_id=session_id,
                transfer_id=transfer_id,
                direction="T2_TO_T1",
                cumulative_ack=100,  # Claiming all 100 packets confirmed when only 5 sent
                selective_ack=[],
            )
        else:
            raise ValueError(f"Unknown scenario: {scenario}")

    def test_forged_ack(
        self,
        sender_window: SenderWindow,
        ack_msg: AckMessage,
        expected_session_id: str,
        expected_transfer_id: str,
        total_packets: int,
        scenario: str = "FORGED_ACK",
    ) -> Tuple[bool, str]:
        """Process forged ACK and verify sender window state is NOT compromised."""
        self.attempts_count += 1
        old_base = sender_window.base_sequence

        self.logger.log_event(
            "FORGED_ACK_ATTEMPT",
            "SENDER",
            "ATTACKER",
            {
                "scenario": scenario,
                "claimed_ack": ack_msg.cumulative_ack,
                "current_base": old_base,
            },
        )

        # Validation logic: Sender must reject ACKs with mismatched session/transfer or impossible sequences
        if ack_msg.session_id != expected_session_id:
            self.rejections_count += 1
            self.logger.log_event("FORGED_ACK_REJECTED", "SENDER", "ATTACKER", {"reason": "SESSION_MISMATCH"})
            return False, "ACK_REJECTED: SESSION_MISMATCH"

        if ack_msg.transfer_id != expected_transfer_id:
            self.rejections_count += 1
            self.logger.log_event("FORGED_ACK_REJECTED", "SENDER", "ATTACKER", {"reason": "TRANSFER_MISMATCH"})
            return False, "ACK_REJECTED: TRANSFER_MISMATCH"

        if ack_msg.cumulative_ack > sender_window.next_sequence:
            self.rejections_count += 1
            self.logger.log_event("FORGED_ACK_REJECTED", "SENDER", "ATTACKER", {"reason": "IMPOSSIBLE_SEQUENCE"})
            return False, "ACK_REJECTED: IMPOSSIBLE_SEQUENCE"

        if ack_msg.cumulative_ack > total_packets:
            self.rejections_count += 1
            self.logger.log_event("FORGED_ACK_REJECTED", "SENDER", "ATTACKER", {"reason": "EXCEEDS_TOTAL_PACKETS"})
            return False, "ACK_REJECTED: EXCEEDS_TOTAL_PACKETS"

        # If it reached here, process through SenderWindow
        new_base, _ = sender_window.process_ack(ack_msg)
        if new_base > total_packets:
            sender_window.base_sequence = old_base  # Restore
            self.rejections_count += 1
            return False, "ACK_REJECTED: INVALID_BASE"

        return True, "ACK_ACCEPTED"
