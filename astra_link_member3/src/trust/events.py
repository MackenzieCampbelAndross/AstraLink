"""Structured security event logger for audit trail generation."""

import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class SecurityEvent:
    """Structured security log event."""

    timestamp: float
    event_type: str
    terminal_id: str
    remote_terminal_id: Optional[str]
    details: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "event_type": self.event_type,
            "terminal_id": self.terminal_id,
            "remote_terminal_id": self.remote_terminal_id,
            "details": self.details,
        }

    def __repr__(self) -> str:
        return f"[{self.event_type}] terminal={self.terminal_id} remote={self.remote_terminal_id} details={self.details}"


class SecurityLogger:
    """Stores and logs security events in memory."""

    def __init__(self):
        self._events: List[SecurityEvent] = []

    def log_event(
        self,
        event_type: str,
        terminal_id: str,
        remote_terminal_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> SecurityEvent:
        """Create and store a structured security event."""
        event = SecurityEvent(
            timestamp=round(time.time(), 3),
            event_type=event_type,
            terminal_id=terminal_id,
            remote_terminal_id=remote_terminal_id,
            details=details or {},
        )
        self._events.append(event)
        return event

    def get_events(self) -> List[SecurityEvent]:
        """Return shallow copy of recorded events."""
        return list(self._events)

    def clear(self) -> None:
        """Clear log events."""
        self._events.clear()
