"""Attack 3: Packet Tampering Attack Simulation."""

from typing import Dict, Optional, Tuple

from ..transport.cipher import InvalidPacketError, PacketCipher
from ..transport.packet import EncryptedPacket
from ..trust import SecurityLogger


class PacketTamperingAttack:
    """Simulates active packet modification attacks on transmitted EncryptedPackets."""

    def __init__(self, logger: Optional[SecurityLogger] = None):
        self.logger = logger or SecurityLogger()
        self.attempts_count: int = 0
        self.integrity_failures: int = 0
        self.rejected_count: int = 0

    def tamper_packet(
        self,
        valid_packet: EncryptedPacket,
        field_to_corrupt: str = "ciphertext",
    ) -> EncryptedPacket:
        """Create a tampered copy of a valid packet by corrupting a specific field."""
        d = valid_packet.to_dict()

        if field_to_corrupt == "ciphertext":
            # Flip bits in ciphertext
            ct_bytes = bytearray(valid_packet.get_ciphertext_bytes())
            if ct_bytes:
                ct_bytes[0] ^= 0xFF
            d["ciphertext_hex"] = ct_bytes.hex()
        elif field_to_corrupt == "nonce":
            # Modify GCM nonce
            n_bytes = bytearray(valid_packet.get_nonce_bytes())
            if n_bytes:
                n_bytes[0] ^= 0xFF
            d["nonce_hex"] = n_bytes.hex()
        elif field_to_corrupt == "session_id":
            d["session_id"] = "SESS_CORRUPTED_99"
        elif field_to_corrupt == "transfer_id":
            d["transfer_id"] = "TX_CORRUPTED_99"
        elif field_to_corrupt == "sequence_number":
            d["sequence_number"] = valid_packet.sequence_number + 999
        elif field_to_corrupt == "direction":
            d["direction"] = "T2_TO_T1" if valid_packet.direction == "T1_TO_T2" else "T1_TO_T2"
        else:
            raise ValueError(f"Unknown field_to_corrupt: '{field_to_corrupt}'")

        return EncryptedPacket.from_dict(d)

    def test_decryption(
        self,
        session_key: bytes,
        packet: EncryptedPacket,
        field_corrupted: str = "unknown",
    ) -> Tuple[bool, str]:
        """Test AES-GCM decryption of a tampered packet."""
        self.attempts_count += 1
        self.logger.log_event(
            "PACKET_TAMPER_ATTEMPT",
            packet.session_id[:8],
            packet.transfer_id,
            {"field_corrupted": field_corrupted, "seq": packet.sequence_number},
        )

        try:
            PacketCipher.decrypt(key=session_key, packet=packet)
            return True, "TAMPERING_UNDETECTED_WARNING"
        except InvalidPacketError as e:
            self.integrity_failures += 1
            self.rejected_count += 1
            self.logger.log_event(
                "PACKET_INTEGRITY_FAILURE",
                packet.session_id[:8],
                packet.transfer_id,
                {"field_corrupted": field_corrupted, "reason": str(e)},
            )
            return False, f"PACKET_REJECTED: {e}"
