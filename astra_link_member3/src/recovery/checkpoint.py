"""Persistent transfer checkpointing with atomic file writes and anti-rollback validation."""

import json
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple


class CheckpointError(Exception):
    """Base exception for checkpoint operations."""
    pass


class CorruptedCheckpointError(CheckpointError):
    """Raised when a checkpoint file is corrupted, incomplete, or unparseable."""
    pass


class InvalidCheckpointError(CheckpointError):
    """Raised when checkpoint values violate transfer invariants (e.g. out of bounds)."""
    pass


class CheckpointRollbackError(CheckpointError):
    """Raised when a checkpoint attempts an invalid rollback below a verified position."""
    pass


@dataclass(frozen=True)
class Checkpoint:
    """Represents a verified transfer checkpoint state."""

    transfer_id: str
    total_packets: int
    last_confirmed: int
    next_expected: int
    session_id: str
    tracking_epoch: int
    payload_hash: str
    checkpoint_timestamp: float

    def to_dict(self) -> Dict[str, Any]:
        """Serialize checkpoint to a dictionary."""
        return {
            "transfer_id": self.transfer_id,
            "total_packets": self.total_packets,
            "last_confirmed": self.last_confirmed,
            "next_expected": self.next_expected,
            "session_id": self.session_id,
            "tracking_epoch": self.tracking_epoch,
            "payload_hash": self.payload_hash,
            "checkpoint_timestamp": self.checkpoint_timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Checkpoint":
        """Deserialize checkpoint from dictionary with validation."""
        required = [
            "transfer_id",
            "total_packets",
            "last_confirmed",
            "next_expected",
            "session_id",
            "tracking_epoch",
            "payload_hash",
            "checkpoint_timestamp",
        ]
        for field_name in required:
            if field_name not in data:
                raise CorruptedCheckpointError(f"Missing required checkpoint field: '{field_name}'")

        try:
            transfer_id = str(data["transfer_id"])
            total_packets = int(data["total_packets"])
            last_confirmed = int(data["last_confirmed"])
            next_expected = int(data["next_expected"])
            session_id = str(data["session_id"])
            tracking_epoch = int(data["tracking_epoch"])
            payload_hash = str(data["payload_hash"])
            checkpoint_timestamp = float(data["checkpoint_timestamp"])
        except (ValueError, TypeError) as err:
            raise CorruptedCheckpointError(f"Invalid field data type in checkpoint: {err}") from err

        return cls(
            transfer_id=transfer_id,
            total_packets=total_packets,
            last_confirmed=last_confirmed,
            next_expected=next_expected,
            session_id=session_id,
            tracking_epoch=tracking_epoch,
            payload_hash=payload_hash,
            checkpoint_timestamp=checkpoint_timestamp,
        )


class CheckpointManager:
    """Manages persistent transfer checkpoints using atomic file replacement and anti-rollback checks."""

    def __init__(self, checkpoint_dir: str = "outputs/checkpoints"):
        self.checkpoint_dir = os.path.abspath(checkpoint_dir)
        os.makedirs(self.checkpoint_dir, exist_ok=True)

    def _get_checkpoint_path(self, transfer_id: str) -> str:
        safe_id = "".join(c for c in transfer_id if c.isalnum() or c in ("-", "_"))
        return os.path.join(self.checkpoint_dir, f"checkpoint_{safe_id}.json")

    def _get_tmp_path(self, transfer_id: str) -> str:
        safe_id = "".join(c for c in transfer_id if c.isalnum() or c in ("-", "_"))
        return os.path.join(self.checkpoint_dir, f"checkpoint_{safe_id}.tmp")

    def save_checkpoint(self, checkpoint: Checkpoint) -> str:
        """Atomically write checkpoint to persistent storage.
        
        Uses write -> flush -> fsync -> replace strategy to prevent partial/corrupted writes.
        """
        if not isinstance(checkpoint, Checkpoint):
            raise InvalidCheckpointError("Expected Checkpoint instance")

        target_path = self._get_checkpoint_path(checkpoint.transfer_id)
        tmp_path = self._get_tmp_path(checkpoint.transfer_id)

        data_dict = checkpoint.to_dict()
        json_bytes = json.dumps(data_dict, indent=2).encode("utf-8")

        # Atomic write strategy
        with open(tmp_path, "wb") as f:
            f.write(json_bytes)
            f.flush()
            os.fsync(f.fileno())

        os.replace(tmp_path, target_path)
        return target_path

    def load_checkpoint(self, transfer_id: str) -> Optional[Checkpoint]:
        """Load and parse checkpoint for transfer_id.
        
        Raises:
            CorruptedCheckpointError: If file is corrupted JSON or missing fields.
        """
        target_path = self._get_checkpoint_path(transfer_id)
        if not os.path.isfile(target_path):
            return None

        try:
            with open(target_path, "r", encoding="utf-8") as f:
                content = f.read()

            if not content.strip():
                raise CorruptedCheckpointError(f"Checkpoint file '{target_path}' is empty")

            data = json.loads(content)
            return Checkpoint.from_dict(data)
        except (json.JSONDecodeError, OSError) as err:
            raise CorruptedCheckpointError(f"Corrupted checkpoint file '{target_path}': {err}") from err

    def validate_checkpoint(
        self,
        checkpoint: Checkpoint,
        expected_total_packets: Optional[int] = None,
        verified_last_confirmed: Optional[int] = None,
        expected_payload_hash: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """Validate checkpoint state against bounds, anti-rollback, and transfer metadata."""
        if not isinstance(checkpoint, Checkpoint):
            return False, "INVALID_CHECKPOINT_OBJECT"

        total_packets = expected_total_packets if expected_total_packets is not None else checkpoint.total_packets

        if checkpoint.total_packets <= 0:
            raise InvalidCheckpointError(f"total_packets must be > 0 (got {checkpoint.total_packets})")

        if expected_total_packets is not None and checkpoint.total_packets != expected_total_packets:
            raise InvalidCheckpointError(
                f"total_packets mismatch (checkpoint: {checkpoint.total_packets}, expected: {expected_total_packets})"
            )

        # Bounds check: 0 <= last_confirmed < total_packets (unless completed)
        if checkpoint.last_confirmed < 0:
            raise InvalidCheckpointError(f"last_confirmed < 0 ({checkpoint.last_confirmed})")

        if checkpoint.last_confirmed >= total_packets and not (
            checkpoint.last_confirmed == total_packets - 1 or checkpoint.last_confirmed == total_packets
        ):
            raise InvalidCheckpointError(
                f"last_confirmed ({checkpoint.last_confirmed}) out of range for total_packets ({total_packets})"
            )

        if checkpoint.next_expected != checkpoint.last_confirmed + 1:
            raise InvalidCheckpointError(
                f"next_expected ({checkpoint.next_expected}) must equal last_confirmed + 1 ({checkpoint.last_confirmed + 1})"
            )

        # Anti-rollback check: cannot move backward below locally verified checkpoint
        if verified_last_confirmed is not None:
            if checkpoint.last_confirmed < verified_last_confirmed:
                raise CheckpointRollbackError(
                    f"Checkpoint rollback detected! Proposed ({checkpoint.last_confirmed}) < "
                    f"verified ({verified_last_confirmed})"
                )

        if expected_payload_hash is not None and checkpoint.payload_hash != expected_payload_hash:
            raise InvalidCheckpointError(
                f"payload_hash mismatch (checkpoint: '{checkpoint.payload_hash[:8]}...', "
                f"expected: '{expected_payload_hash[:8]}...')"
            )

        return True, "CHECKPOINT_VALID"

    def delete_checkpoint(self, transfer_id: str) -> None:
        """Remove checkpoint file after completed transfer."""
        target_path = self._get_checkpoint_path(transfer_id)
        if os.path.isfile(target_path):
            try:
                os.remove(target_path)
            except OSError:
                pass
