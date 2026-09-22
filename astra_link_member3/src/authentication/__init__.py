"""Authentication module for Astra Link Member 3 (Phase 2 Mutual Authentication)."""

from .challenge import AuthenticationChallenge
from .challenge_response import AuthenticationController, AuthenticationResult
from .freshness import (
    AuthenticationError,
    ExpiredTimestampError,
    FreshnessError,
    FreshnessValidator,
    FutureTimestampError,
    InvalidSignatureError,
    InvalidTranscriptError,
    ReplayAttackError,
    ReplayKey,
    ReplayProtectionCache,
)
from .mutual_auth import (
    AuthState,
    AuthenticationSession,
    authenticate_mutually,
    create_challenge,
    create_response,
    verify_response,
)
from .response import AuthenticationResponse
from .transcript import compute_canonical_transcript

__all__ = [
    "AuthenticationChallenge",
    "AuthenticationResponse",
    "AuthenticationController",
    "AuthenticationResult",
    "compute_canonical_transcript",
    "FreshnessValidator",
    "ReplayKey",
    "ReplayProtectionCache",
    "AuthState",
    "AuthenticationSession",
    "AuthenticationError",
    "FreshnessError",
    "ExpiredTimestampError",
    "FutureTimestampError",
    "ReplayAttackError",
    "InvalidSignatureError",
    "InvalidTranscriptError",
    "create_challenge",
    "create_response",
    "verify_response",
    "authenticate_mutually",
]
