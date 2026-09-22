"""SecureReceiver executing packet validation, directional key selection, and AES-GCM decryption."""

from typing import Optional

from src.session import SessionManager
from src.trust import SecurityLogger
from .ack import AckMessage
from .cipher import InvalidPacketError, PacketCipher
from .metrics import TransportMetrics
from .packet import EncryptedPacket
from .selective_repeat import ReceiverWindow


class SecureReceiver:
    """Handles receiving, verifying, and decrypting incoming EncryptedPackets and ACK control messages."""

    def __init__(self, session_manager: SessionManager):
        if not isinstance(session_manager, SessionManager):
            raise TypeError("Expected SessionManager instance.")
        self.session_manager = session_manager
        self.receiver_window = ReceiverWindow()
        self.metrics = TransportMetrics()

    def receive_and_decrypt(
        self,
        packet: EncryptedPacket,
        expected_direction: str,
        logger: Optional[SecurityLogger] = None,
    ) -> bytes:
        """Verify, authenticate, and decrypt an EncryptedPacket."""
        if not isinstance(packet, EncryptedPacket):
            raise TypeError("Expected EncryptedPacket instance.")

        # 1. Enforce active session validity
        if not self.session_manager.is_session_valid(packet.session_id):
            if logger:
                logger.log_event("PACKET_REJECTED", "RECEIVER", "SENDER", {"reason": "SESSION_INACTIVE_OR_EXPIRED"})
            raise InvalidPacketError(f"Packet rejected: Session '{packet.session_id}' is inactive or expired.")

        session = self.session_manager.get_session(packet.session_id)

        # 2. Enforce cross-direction protection
        exp_dir_upper = expected_direction.upper()
        if packet.direction.upper() != exp_dir_upper:
            if logger:
                logger.log_event("PACKET_REJECTED", "RECEIVER", "SENDER", {"reason": "DIRECTION_MISMATCH"})
            raise InvalidPacketError(
                f"Cross-direction packet reuse rejected: packet claims direction '{packet.direction}', "
                f"expected '{expected_direction}'"
            )

        # 3. Select directional key
        if exp_dir_upper == "T1_TO_T2":
            directional_key = session.derived_keys.t1_to_t2_key
        elif exp_dir_upper == "T2_TO_T1":
            directional_key = session.derived_keys.t2_to_t1_key
        else:
            raise ValueError(f"Invalid expected_direction: '{expected_direction}'")

        # 4. Decrypt & Verify AES-GCM tag and AAD
        try:
            plaintext = PacketCipher.decrypt(directional_key, packet)
            self.metrics.packets_received += 1
            if logger:
                logger.log_event(
                    "PACKET_DECRYPTED",
                    session.context.responder_id,
                    session.context.initiator_id,
                    {"transfer_id": packet.transfer_id, "sequence_number": packet.sequence_number},
                )
            return plaintext
        except InvalidPacketError as e:
            if logger:
                logger.log_event(
                    "PACKET_INTEGRITY_FAILURE",
                    session.context.responder_id,
                    session.context.initiator_id,
                    {"transfer_id": packet.transfer_id, "sequence_number": packet.sequence_number},
                )
            raise

    def decrypt_ack_control_packet(
        self,
        ack_packet: EncryptedPacket,
        expected_direction: str,
    ) -> AckMessage:
        """Decrypt and verify an incoming authenticated AckMessage control packet."""
        plaintext = self.receive_and_decrypt(ack_packet, expected_direction=expected_direction)
        ack_msg = AckMessage.from_bytes(plaintext)

        # Verify transfer ID and session match
        if ack_msg.session_id != ack_packet.session_id:
            raise InvalidPacketError("Wrong session ACK rejected.")

        if ack_msg.transfer_id != ack_packet.transfer_id:
            raise InvalidPacketError("Wrong transfer ACK rejected.")

        return ack_msg
