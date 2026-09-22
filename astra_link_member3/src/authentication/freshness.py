"""Freshness validation and replay protection mechanisms."""

import time
from dataclasses import dataclass
from typing import Dict, Optional, Tuple, Union

from .challenge import AuthenticationChallenge


class AuthenticationError(Exception):
    """Base exception for authentication failures."""
    pass


class FreshnessError(AuthenticationError):
    """Raised when authentication context fails freshness check."""
    pass


class ExpiredTimestampError(FreshnessError):
    """Raised when authentication timestamp is older than the allowed window."""
    pass


class FutureTimestampError(FreshnessError):
    """Raised when authentication timestamp is in the future beyond tolerance."""
    pass


class ReplayAttackError(AuthenticationError):
    """Raised when a replayed nonce or authentication context is detected."""
    pass


class InvalidSignatureError(AuthenticationError):
    """Raised when Ed25519 signature verification fails."""
    pass


class InvalidTranscriptError(AuthenticationError):
    """Raised when authentication context or transcript fields fail validation."""
    pass


@dataclass(frozen=True)
class ReplayKey:
    """Immutable 5-field representation of a complete authentication context."""

    initiator_id: str
    responder_id: str
    tracking_epoch: int
    session_id: str
    nonce: str

    @classmethod
    def from_challenge(cls, challenge: AuthenticationChallenge) -> "ReplayKey":
        return cls(
            initiator_id=challenge.initiator_id,
            responder_id=challenge.responder_id,
            tracking_epoch=int(challenge.tracking_epoch),
            session_id=challenge.session_id,
            nonce=challenge.nonce,
        )


class FreshnessValidator:
    """Validates temporal freshness and protocol parameters for authentication context."""

    def __init__(self, window_seconds: float = 30.0, expected_protocol_version: str = "1.0"):
        self.window_seconds = float(window_seconds)
        self.expected_protocol_version = expected_protocol_version

    def validate_challenge(
        self,
        challenge: AuthenticationChallenge,
        current_time: Optional[float] = None,
    ) -> None:
        """Validate timestamp freshness and protocol version of a challenge context."""
        if not isinstance(challenge, AuthenticationChallenge):
            raise InvalidTranscriptError("Expected AuthenticationChallenge object.")

        if challenge.protocol_version != self.expected_protocol_version:
            raise InvalidTranscriptError(
                f"Protocol version mismatch: got '{challenge.protocol_version}', expected '{self.expected_protocol_version}'"
            )

        now = current_time if current_time is not None else time.time()
        age = now - challenge.timestamp

        if age > self.window_seconds:
            raise ExpiredTimestampError(
                f"Authentication timestamp expired (age={age:.2f}s, allowed={self.window_seconds}s)"
            )

        if -age > self.window_seconds:
            raise FutureTimestampError(
                f"Authentication timestamp in future (future_diff={-age:.2f}s, allowed={self.window_seconds}s)"
            )


class ReplayProtectionCache:
    """Stateful, bounded, and TTL-expiring cache to detect and reject replayed authentication contexts."""

    def __init__(self, ttl_seconds: float = 60.0, max_entries: int = 10000):
        self.ttl_seconds = float(ttl_seconds)
        self.max_entries = int(max_entries)
        self._entries: Dict[ReplayKey, float] = {}

    def _cleanup_expired(self, now: float) -> None:
        """Evict entries older than ttl_seconds."""
        if self.ttl_seconds <= 0:
            return
        expired_keys = [
            key for key, timestamp in self._entries.items()
            if now - timestamp > self.ttl_seconds
        ]
        for key in expired_keys:
            del self._entries[key]

    def is_replayed(
        self,
        item: Union[AuthenticationChallenge, ReplayKey, Tuple[str, str]],
        current_time: Optional[float] = None,
    ) -> bool:
        """Check if an authentication context key is registered and active."""
        now = current_time if current_time is not None else time.time()
        self._cleanup_expired(now)

        if isinstance(item, AuthenticationChallenge):
            key = ReplayKey.from_challenge(item)
        elif isinstance(item, ReplayKey):
            key = item
        elif isinstance(item, tuple) and len(item) == 2:
            initiator_id, nonce = item
            return any(k.initiator_id == initiator_id and k.nonce == nonce for k in self._entries.keys())
        else:
            raise InvalidTranscriptError("Expected AuthenticationChallenge, ReplayKey, or (initiator_id, nonce) tuple.")

        return key in self._entries

    def check_and_register(
        self,
        challenge: AuthenticationChallenge,
        current_time: Optional[float] = None,
    ) -> None:
        """Check challenge for replay; register if fresh.
        
        Raises:
            ReplayAttackError: If nonce or context key was previously registered and active.
        """
        if not isinstance(challenge, AuthenticationChallenge):
            raise InvalidTranscriptError("Expected AuthenticationChallenge object.")

        now = current_time if current_time is not None else time.time()
        self._cleanup_expired(now)

        key = ReplayKey.from_challenge(challenge)
        if key in self._entries:
            raise ReplayAttackError(
                f"Replay detected for authentication context: initiator='{challenge.initiator_id}', "
                f"responder='{challenge.responder_id}', epoch={challenge.tracking_epoch}, "
                f"session_id='{challenge.session_id[:8]}...', nonce='{challenge.nonce[:8]}...'"
            )

        # Enforce maximum cache entries (FIFO eviction)
        while len(self._entries) >= self.max_entries and self.max_entries > 0:
            oldest_key = next(iter(self._entries))
            del self._entries[oldest_key]

        self._entries[key] = now

    def clear(self) -> None:
        """Reset cache."""
        self._entries.clear()

    def __len__(self) -> int:
        return len(self._entries)
