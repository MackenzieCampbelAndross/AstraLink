"""Recovery state machine and epoch management for Astra Link Phase 7."""

from enum import Enum
from typing import Any, Dict, Optional

from ..tracking.tracking_state import TrackingState


class RecoveryState(Enum):
    """Explicit recovery state machine states."""

    CONNECTED = "CONNECTED"
    INTERRUPTED = "INTERRUPTED"
    REACQUIRING = "REACQUIRING"
    AUTHENTICATING = "AUTHENTICATING"
    ESTABLISHING_SESSION = "ESTABLISHING_SESSION"
    RESUMING = "RESUMING"
    FAILED = "FAILED"
    COMPLETED = "COMPLETED"


class RecoveryStateMachine:
    """Manages explicit recovery transitions, security states, tracking epoch advancement, and transmission gating."""

    def __init__(
        self,
        transfer_id: str,
        initial_epoch: int = 1,
        initial_session_id: Optional[str] = None,
    ):
        self.transfer_id = transfer_id
        self.state: RecoveryState = RecoveryState.CONNECTED
        self.tracking_epoch: int = max(1, int(initial_epoch))
        self.current_session_id: Optional[str] = initial_session_id
        self.security_status: str = "TRUSTED_CONNECTED"
        self.transmission_allowed: bool = True
        self.failure_reason: Optional[str] = None

    def handle_link_loss(self, reason: str = "OPTICAL_BEACON_LOST") -> None:
        """Triggered when Member 2 reports tracking_state = LOST or optical link drops."""
        self.state = RecoveryState.INTERRUPTED
        self.transmission_allowed = False
        self.security_status = "INTERRUPTED"

        # Increment tracking epoch upon meaningful link loss
        old_epoch = self.tracking_epoch
        self.tracking_epoch += 1

    def handle_reacquisition(self, tracking_state: TrackingState) -> None:
        """Handle optical beacon reacquisition from Member 2.
        
        BEACON REACQUIRED != AUTOMATIC TRUST != AUTOMATIC RESUME
        Sets security_status to LOCKED_UNVERIFIED and keeps transmission_allowed = False.
        """
        if self.state not in (RecoveryState.INTERRUPTED, RecoveryState.REACQUIRING, RecoveryState.FAILED):
            raise ValueError(f"Cannot reacquire beacon while in state {self.state.value}")

        if not tracking_state.is_locked:
            self.security_status = "UNVERIFIED_UNLOCKED"
            self.transmission_allowed = False
            return

        self.state = RecoveryState.REACQUIRING
        self.security_status = "LOCKED_UNVERIFIED"
        self.transmission_allowed = False

    def transition_to_authenticating(self) -> None:
        """Move to fresh Phase 2 reauthentication."""
        if self.state not in (RecoveryState.REACQUIRING, RecoveryState.INTERRUPTED):
            raise ValueError(f"Cannot transition to AUTHENTICATING from {self.state.value}")

        self.state = RecoveryState.AUTHENTICATING
        self.transmission_allowed = False
        self.security_status = "AUTHENTICATING"

    def handle_authentication_success(self) -> None:
        """Mark fresh mutual authentication succeeded."""
        if self.state != RecoveryState.AUTHENTICATING:
            raise ValueError(f"Cannot process auth success in state {self.state.value}")

        self.security_status = "AUTHENTICATED"
        self.transmission_allowed = False

    def handle_session_establishment(self, new_session_id: str) -> None:
        """Bind new secure session context while preserving transfer state.
        
        OLD SESSION != NEW SESSION, but OLD TRANSFER == NEW TRANSFER
        """
        if self.state not in (RecoveryState.AUTHENTICATING, RecoveryState.REACQUIRING):
            raise ValueError(f"Cannot establish session in state {self.state.value}")

        self.state = RecoveryState.ESTABLISHING_SESSION
        self.current_session_id = new_session_id
        self.security_status = "SESSION_ESTABLISHED"
        self.transmission_allowed = False

    def transition_to_resuming(self) -> None:
        """Start authenticated resume protocol negotiation."""
        if self.state != RecoveryState.ESTABLISHING_SESSION:
            raise ValueError(f"Cannot transition to RESUMING from {self.state.value}")

        self.state = RecoveryState.RESUMING
        self.security_status = "RESUMING"
        self.transmission_allowed = False

    def handle_resume_validated(self) -> None:
        """Authenticated resume response validated -> enable transmission."""
        if self.state != RecoveryState.RESUMING:
            raise ValueError(f"Cannot validate resume in state {self.state.value}")

        self.state = RecoveryState.CONNECTED
        self.security_status = "CONNECTED_RESUMED"
        self.transmission_allowed = True

    def handle_failure(self, reason: str) -> None:
        """Set state to FAILED and disable transmission."""
        self.state = RecoveryState.FAILED
        self.security_status = "FAILED"
        self.transmission_allowed = False
        self.failure_reason = reason

    def mark_completed(self) -> None:
        """Mark transfer complete."""
        self.state = RecoveryState.COMPLETED
        self.security_status = "TRANSFER_COMPLETED"
        self.transmission_allowed = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "transfer_id": self.transfer_id,
            "state": self.state.value,
            "tracking_epoch": self.tracking_epoch,
            "current_session_id": self.current_session_id,
            "security_status": self.security_status,
            "transmission_allowed": self.transmission_allowed,
            "failure_reason": self.failure_reason,
        }

    def __repr__(self) -> str:
        return (
            f"RecoveryStateMachine(transfer={self.transfer_id!r}, state={self.state.value}, "
            f"epoch={self.tracking_epoch}, allowed={self.transmission_allowed})"
        )
