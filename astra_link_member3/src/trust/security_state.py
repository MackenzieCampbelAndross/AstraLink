"""Security states and session security tracker for Astra Link."""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class SecurityState(Enum):
    """Extended security state model for Astra Link terminals."""

    UNTRUSTED = "UNTRUSTED"
    AUTHENTICATING = "AUTHENTICATING"
    AUTHENTICATED = "AUTHENTICATED"
    SESSION_ESTABLISHED = "SESSION_ESTABLISHED"  # Reserved for Phase 4
    AUTHORIZED = "AUTHORIZED"
    DEGRADED = "DEGRADED"
    BLOCKED = "BLOCKED"


@dataclass
class SecuritySessionState:
    """Tracks state transitions for a terminal session."""

    terminal_id: str
    remote_terminal_id: Optional[str] = None
    state: SecurityState = SecurityState.UNTRUSTED
    session_id: Optional[str] = None
    tracking_epoch: int = 1
    authentication_valid: bool = False
    physical_validation_valid: bool = False
    tracking_locked: bool = False

    def transition_to(self, new_state: SecurityState) -> None:
        """Execute explicit security state transition."""
        self.state = new_state

    def __repr__(self) -> str:
        return (
            f"SecuritySessionState(terminal_id={self.terminal_id!r}, "
            f"remote_id={self.remote_terminal_id!r}, state={self.state.value})"
        )
