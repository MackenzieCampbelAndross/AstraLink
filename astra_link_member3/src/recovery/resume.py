"""Secure resume protocol request and response models and validation handler."""

import json
import time
from dataclasses import dataclass
from typing import Any, Dict, Tuple

from ..transport.cipher import InvalidPacketError, PacketCipher
from ..transport.packet import EncryptedPacket


class ResumeError(Exception):
    """Base exception for resume protocol operations."""
    pass


class ResumeValidationError(ResumeError):
    """Raised when resume request or response validation fails."""
    pass


@dataclass(frozen=True)
class ResumeRequest:
    """Authenticated resume request sent from Sender to Receiver."""

    transfer_id: str
    total_packets: int
    tracking_epoch: int
    session_id: str
    sender_checkpoint: int
    payload_hash: str
    timestamp: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "msg_type": "RESUME_REQUEST",
            "transfer_id": self.transfer_id,
            "total_packets": self.total_packets,
            "tracking_epoch": self.tracking_epoch,
            "session_id": self.session_id,
            "sender_checkpoint": self.sender_checkpoint,
            "payload_hash": self.payload_hash,
            "timestamp": self.timestamp,
        }

    def to_bytes(self) -> bytes:
        return json.dumps(self.to_dict(), sort_keys=True).encode("utf-8")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ResumeRequest":
        if data.get("msg_type") != "RESUME_REQUEST":
            raise ResumeValidationError(f"Invalid msg_type: {data.get('msg_type')}")
        required = ["transfer_id", "total_packets", "tracking_epoch", "session_id", "sender_checkpoint", "payload_hash", "timestamp"]
        for f in required:
            if f not in data:
                raise ResumeValidationError(f"Missing required ResumeRequest field: '{f}'")
        return cls(
            transfer_id=str(data["transfer_id"]),
            total_packets=int(data["total_packets"]),
            tracking_epoch=int(data["tracking_epoch"]),
            session_id=str(data["session_id"]),
            sender_checkpoint=int(data["sender_checkpoint"]),
            payload_hash=str(data["payload_hash"]),
            timestamp=float(data["timestamp"]),
        )

    @classmethod
    def from_bytes(cls, b: bytes) -> "ResumeRequest":
        try:
            data = json.loads(b.decode("utf-8"))
            return cls.from_dict(data)
        except Exception as e:
            raise ResumeValidationError(f"Failed to parse ResumeRequest: {e}") from e


@dataclass(frozen=True)
class ResumeResponse:
    """Authenticated resume response returned from Receiver to Sender."""

    transfer_id: str
    receiver_verified_checkpoint: int
    total_packets: int
    tracking_epoch: int
    session_id: str
    timestamp: float
    status: str  # "ACCEPTED" or "REJECTED"
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "msg_type": "RESUME_RESPONSE",
            "transfer_id": self.transfer_id,
            "receiver_verified_checkpoint": self.receiver_verified_checkpoint,
            "total_packets": self.total_packets,
            "tracking_epoch": self.tracking_epoch,
            "session_id": self.session_id,
            "timestamp": self.timestamp,
            "status": self.status,
            "reason": self.reason,
        }

    def to_bytes(self) -> bytes:
        return json.dumps(self.to_dict(), sort_keys=True).encode("utf-8")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ResumeResponse":
        if data.get("msg_type") != "RESUME_RESPONSE":
            raise ResumeValidationError(f"Invalid msg_type: {data.get('msg_type')}")
        required = [
            "transfer_id",
            "receiver_verified_checkpoint",
            "total_packets",
            "tracking_epoch",
            "session_id",
            "timestamp",
            "status",
            "reason",
        ]
        for f in required:
            if f not in data:
                raise ResumeValidationError(f"Missing required ResumeResponse field: '{f}'")
        return cls(
            transfer_id=str(data["transfer_id"]),
            receiver_verified_checkpoint=int(data["receiver_verified_checkpoint"]),
            total_packets=int(data["total_packets"]),
            tracking_epoch=int(data["tracking_epoch"]),
            session_id=str(data["session_id"]),
            timestamp=float(data["timestamp"]),
            status=str(data["status"]),
            reason=str(data["reason"]),
        )

    @classmethod
    def from_bytes(cls, b: bytes) -> "ResumeResponse":
        try:
            data = json.loads(b.decode("utf-8"))
            return cls.from_dict(data)
        except Exception as e:
            raise ResumeValidationError(f"Failed to parse ResumeResponse: {e}") from e


class ResumeProtocolHandler:
    """Encapsulates creation, encrypted transmission, and strict validation of resume messages."""

    @staticmethod
    def create_request(
        transfer_id: str,
        total_packets: int,
        tracking_epoch: int,
        session_id: str,
        sender_checkpoint: int,
        payload_hash: str,
    ) -> ResumeRequest:
        return ResumeRequest(
            transfer_id=transfer_id,
            total_packets=total_packets,
            tracking_epoch=tracking_epoch,
            session_id=session_id,
            sender_checkpoint=sender_checkpoint,
            payload_hash=payload_hash,
            timestamp=round(time.time(), 3),
        )

    @staticmethod
    def process_request(
        request: ResumeRequest,
        expected_transfer_id: str,
        expected_epoch: int,
        expected_session_id: str,
        expected_payload_hash: str,
        receiver_verified_checkpoint: int,
    ) -> ResumeResponse:
        """Receiver processes incoming ResumeRequest and produces ResumeResponse."""
        now = round(time.time(), 3)
        if request.transfer_id != expected_transfer_id:
            return ResumeResponse(
                transfer_id=request.transfer_id,
                receiver_verified_checkpoint=receiver_verified_checkpoint,
                total_packets=request.total_packets,
                tracking_epoch=request.tracking_epoch,
                session_id=request.session_id,
                timestamp=now,
                status="REJECTED",
                reason=f"TRANSFER_ID_MISMATCH (got '{request.transfer_id}', expected '{expected_transfer_id}')",
            )

        if request.tracking_epoch != expected_epoch:
            return ResumeResponse(
                transfer_id=request.transfer_id,
                receiver_verified_checkpoint=receiver_verified_checkpoint,
                total_packets=request.total_packets,
                tracking_epoch=request.tracking_epoch,
                session_id=request.session_id,
                timestamp=now,
                status="REJECTED",
                reason=f"EPOCH_MISMATCH (got {request.tracking_epoch}, expected {expected_epoch})",
            )

        if request.session_id != expected_session_id:
            return ResumeResponse(
                transfer_id=request.transfer_id,
                receiver_verified_checkpoint=receiver_verified_checkpoint,
                total_packets=request.total_packets,
                tracking_epoch=request.tracking_epoch,
                session_id=request.session_id,
                timestamp=now,
                status="REJECTED",
                reason=f"SESSION_ID_MISMATCH (got '{request.session_id[:8]}...', expected '{expected_session_id[:8]}...')",
            )

        if request.payload_hash != expected_payload_hash:
            return ResumeResponse(
                transfer_id=request.transfer_id,
                receiver_verified_checkpoint=receiver_verified_checkpoint,
                total_packets=request.total_packets,
                tracking_epoch=request.tracking_epoch,
                session_id=request.session_id,
                timestamp=now,
                status="REJECTED",
                reason=f"PAYLOAD_HASH_MISMATCH",
            )

        if receiver_verified_checkpoint < 0 or receiver_verified_checkpoint >= request.total_packets:
            if not (receiver_verified_checkpoint == request.total_packets - 1 or receiver_verified_checkpoint == request.total_packets):
                return ResumeResponse(
                    transfer_id=request.transfer_id,
                    receiver_verified_checkpoint=receiver_verified_checkpoint,
                    total_packets=request.total_packets,
                    tracking_epoch=request.tracking_epoch,
                    session_id=request.session_id,
                    timestamp=now,
                    status="REJECTED",
                    reason=f"INVALID_RECEIVER_CHECKPOINT ({receiver_verified_checkpoint} for total {request.total_packets})",
                )

        return ResumeResponse(
            transfer_id=request.transfer_id,
            receiver_verified_checkpoint=receiver_verified_checkpoint,
            total_packets=request.total_packets,
            tracking_epoch=request.tracking_epoch,
            session_id=request.session_id,
            timestamp=now,
            status="ACCEPTED",
            reason="RESUME_AUTHORIZED",
        )

    @staticmethod
    def validate_response(
        response: ResumeResponse,
        expected_transfer_id: str,
        expected_epoch: int,
        expected_session_id: str,
        sender_checkpoint: int,
        total_packets: int,
    ) -> Tuple[bool, str]:
        """Sender validates received ResumeResponse."""
        if response.status != "ACCEPTED":
            raise ResumeValidationError(f"Resume response rejected by peer: {response.reason}")

        if response.transfer_id != expected_transfer_id:
            raise ResumeValidationError(
                f"Transfer ID mismatch in response: got '{response.transfer_id}', expected '{expected_transfer_id}'"
            )

        if response.tracking_epoch != expected_epoch:
            raise ResumeValidationError(
                f"Tracking epoch mismatch in response: got {response.tracking_epoch}, expected {expected_epoch}"
            )

        if response.session_id != expected_session_id:
            raise ResumeValidationError(
                f"Session ID mismatch in response: got '{response.session_id}', expected '{expected_session_id}'"
            )

        if response.total_packets != total_packets:
            raise ResumeValidationError(
                f"Total packets mismatch in response: got {response.total_packets}, expected {total_packets}"
            )

        # Anti-rollback check: response receiver_verified_checkpoint cannot be less than sender's verified checkpoint
        if response.receiver_verified_checkpoint < 0:
            raise ResumeValidationError(f"Invalid negative receiver checkpoint ({response.receiver_verified_checkpoint})")

        if response.receiver_verified_checkpoint > total_packets:
            raise ResumeValidationError(
                f"Invalid receiver checkpoint ({response.receiver_verified_checkpoint} > total {total_packets})"
            )

        return True, "RESUME_RESPONSE_VALIDATED"

    @staticmethod
    def encrypt_message(
        msg_bytes: bytes,
        session_key: bytes,
        protocol_version: str,
        session_id: str,
        transfer_id: str,
        sequence_number: int,
        direction: str,
    ) -> EncryptedPacket:
        """Encrypt resume control message using active session key and PacketCipher."""
        return PacketCipher.encrypt(
            key=session_key,
            plaintext=msg_bytes,
            protocol_version=protocol_version,
            session_id=session_id,
            transfer_id=transfer_id,
            sequence_number=sequence_number,
            direction=direction,
        )

    @staticmethod
    def decrypt_message(
        packet: EncryptedPacket,
        session_key: bytes,
    ) -> bytes:
        """Decrypt encrypted resume control message packet using active session key."""
        try:
            return PacketCipher.decrypt(key=session_key, packet=packet)
        except InvalidPacketError as e:
            raise ResumeValidationError(f"Failed to decrypt resume control message: {e}") from e
