"""SecureSender managing authorization enforcement, sliding window flow control, and selective retransmission."""

from typing import List, Optional, Tuple

from src.session import SessionManager, SessionState
from src.trust import SecurityLogger, TransmissionAuthorizationGate, TrustEvaluationResult
from .ack import AckMessage
from .cipher import InvalidPacketError, PacketCipher, TransportError
from .metrics import TransportMetrics
from .packet import EncryptedPacket
from .packetizer import Packetizer
from .selective_repeat import MaxRetriesExceededError, SenderWindow


class UnauthorizedTransmissionError(TransportError):
    """Raised when transmission is attempted without valid authentication, session, or trust authorization."""
    pass


class SecureSender:
    """Handles secure payload transmission, sliding window flow control, and selective ARQ retransmission."""

    def __init__(
        self,
        session_manager: SessionManager,
        packetizer: Optional[Packetizer] = None,
        window_size: int = 32,
        max_retries: int = 5,
    ):
        if not isinstance(session_manager, SessionManager):
            raise TypeError("Expected SessionManager instance.")

        self.session_manager = session_manager
        self.packetizer = packetizer or Packetizer(packet_size=4096)
        self.window_size = window_size
        self.max_retries = max_retries
        self.metrics = TransportMetrics()

    def send_payload(
        self,
        session_id: str,
        transfer_id: str,
        payload: bytes,
        direction: str,
        trust_result: TrustEvaluationResult,
        logger: Optional[SecurityLogger] = None,
    ) -> List[EncryptedPacket]:
        """Encrypt and transmit byte payload as a sequence of EncryptedPackets."""
        if not isinstance(payload, bytes):
            raise TypeError("Payload must be bytes.")

        # 1. Enforce active session validity
        if not self.session_manager.is_session_valid(session_id):
            if logger:
                logger.log_event("TRANSMISSION_BLOCKED", "SENDER", "RECEIVER", {"reason": "SESSION_INACTIVE_OR_EXPIRED"})
            raise UnauthorizedTransmissionError(
                f"Transmission BLOCKED: Secure session '{session_id}' is inactive or expired."
            )

        # 2. Enforce Phase 3 Transmission Authorization Gate
        gate_res = TransmissionAuthorizationGate.can_transmit(
            trust_result, logger=logger, terminal_id="T1", remote_terminal_id="T2"
        )
        if not gate_res.allowed:
            raise UnauthorizedTransmissionError(
                f"Transmission BLOCKED by authorization gate: {gate_res.reason} (Failed: {gate_res.failed_conditions})"
            )

        session = self.session_manager.get_session(session_id)

        # 3. Select correct directional key
        dir_upper = direction.upper()
        if dir_upper == "T1_TO_T2":
            directional_key = session.derived_keys.t1_to_t2_key
        elif dir_upper == "T2_TO_T1":
            directional_key = session.derived_keys.t2_to_t1_key
        else:
            raise ValueError(f"Invalid direction: '{direction}'. Must be T1_TO_T2 or T2_TO_T1.")

        # 4. Packetize payload
        chunks = self.packetizer.packetize(payload, transfer_id)
        self.metrics.mark_started()
        self.metrics.total_bytes_transferred += len(payload)

        if logger:
            logger.log_event(
                "TRANSFER_STARTED",
                session.context.initiator_id,
                session.context.responder_id,
                {"transfer_id": transfer_id, "chunk_count": len(chunks), "payload_bytes": len(payload)},
            )

        # 5. Encrypt packets
        packets = []
        for seq, chunk_bytes in chunks:
            packet = PacketCipher.encrypt(
                key=directional_key,
                plaintext=chunk_bytes,
                protocol_version=session.context.protocol_version,
                session_id=session_id,
                transfer_id=transfer_id,
                sequence_number=seq,
                direction=dir_upper,
            )
            packets.append(packet)
            self.metrics.packets_sent += 1

            if logger:
                logger.log_event(
                    "PACKET_ENCRYPTED",
                    session.context.initiator_id,
                    session.context.responder_id,
                    {"transfer_id": transfer_id, "sequence_number": seq, "direction": dir_upper},
                )

        return packets

    def send_ack_control_packet(
        self,
        session_id: str,
        transfer_id: str,
        ack_msg: AckMessage,
        direction: str,
    ) -> EncryptedPacket:
        """Create an authenticated encrypted control packet containing an AckMessage."""
        session = self.session_manager.get_session(session_id)
        dir_upper = direction.upper()

        if dir_upper == "T1_TO_T2":
            key = session.derived_keys.t1_to_t2_key
        elif dir_upper == "T2_TO_T1":
            key = session.derived_keys.t2_to_t1_key
        else:
            raise ValueError(f"Invalid direction: '{direction}'")

        ack_bytes = ack_msg.to_bytes()
        return PacketCipher.encrypt(
            key=key,
            plaintext=ack_bytes,
            protocol_version=session.context.protocol_version,
            session_id=session_id,
            transfer_id=transfer_id,
            sequence_number=0,  # Control sequence=0
            direction=dir_upper,
        )
