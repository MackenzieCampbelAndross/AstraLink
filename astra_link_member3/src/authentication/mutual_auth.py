"""Mutual authentication state machine and protocol handlers."""

from enum import Enum
from typing import Any, Dict, Optional

from cryptography.exceptions import InvalidSignature

from src.identity import TerminalIdentity, TerminalRegistry

from .challenge import AuthenticationChallenge
from .freshness import (
    FreshnessValidator,
    InvalidSignatureError,
    InvalidTranscriptError,
    ReplayProtectionCache,
)
from .response import AuthenticationResponse
from .transcript import compute_canonical_transcript


class AuthState(Enum):
    """Authentication states for terminal protocol handlers."""
    UNAUTHENTICATED = "UNAUTHENTICATED"
    AUTHENTICATING = "AUTHENTICATING"
    AUTHENTICATED = "AUTHENTICATED"
    FAILED = "FAILED"


class AuthenticationSession:
    """Tracks authentication state and identity verification for a terminal."""

    def __init__(self, terminal_id: str, initial_epoch: int = 1):
        self.terminal_id = terminal_id
        self.state = AuthState.UNAUTHENTICATED
        self.local_authenticated = False
        self.remote_authenticated = False
        self.authenticated_remote_id: Optional[str] = None
        self.session_id: Optional[str] = None
        self.tracking_epoch = initial_epoch

    @property
    def mutual_authentication_success(self) -> bool:
        """Returns True only when both local and remote terminals are authenticated."""
        return (
            self.state == AuthState.AUTHENTICATED
            and self.local_authenticated is True
            and self.remote_authenticated is True
        )

    def mark_authenticating(self, session_id: str) -> None:
        self.state = AuthState.AUTHENTICATING
        self.session_id = session_id

    def mark_remote_authenticated(self, remote_id: str) -> None:
        self.remote_authenticated = True
        self.authenticated_remote_id = remote_id
        if self.local_authenticated and self.remote_authenticated:
            self.state = AuthState.AUTHENTICATED

    def mark_local_authenticated(self) -> None:
        self.local_authenticated = True
        if self.local_authenticated and self.remote_authenticated:
            self.state = AuthState.AUTHENTICATED

    def mark_failed(self) -> None:
        self.state = AuthState.FAILED
        self.local_authenticated = False
        self.remote_authenticated = False

    def __repr__(self) -> str:
        return (
            f"AuthenticationSession(terminal_id={self.terminal_id!r}, "
            f"state={self.state.value}, mutual_success={self.mutual_authentication_success})"
        )


def create_challenge(
    initiator_id: str,
    responder_id: str,
    tracking_epoch: int = 1,
    protocol_version: str = "1.0",
) -> AuthenticationChallenge:
    """Create a fresh authentication challenge."""
    return AuthenticationChallenge.create_fresh(
        initiator_id=initiator_id,
        responder_id=responder_id,
        tracking_epoch=tracking_epoch,
        protocol_version=protocol_version,
    )


def create_response(
    challenge: AuthenticationChallenge,
    responder_identity: TerminalIdentity,
) -> AuthenticationResponse:
    """Create a signed authentication response for a challenge.
    
    Args:
        challenge: The received AuthenticationChallenge.
        responder_identity: The responder's TerminalIdentity (with Ed25519 private key).
        
    Returns:
        AuthenticationResponse with Ed25519 signature over the canonical transcript.
    """
    if not isinstance(challenge, AuthenticationChallenge):
        raise TypeError("Expected AuthenticationChallenge instance.")

    if not isinstance(responder_identity, TerminalIdentity):
        raise TypeError("Expected TerminalIdentity instance.")

    if responder_identity.terminal_id != challenge.responder_id:
        raise InvalidTranscriptError(
            f"Responder identity mismatch: identity is '{responder_identity.terminal_id}', "
            f"challenge requested '{challenge.responder_id}'"
        )

    if not responder_identity.has_private_key:
        raise ValueError(f"Responder terminal '{responder_identity.terminal_id}' lacks private key material.")

    # 1. Compute canonical transcript bytes
    transcript_bytes = compute_canonical_transcript(challenge, direction="RESPONSE")

    # 2. Sign canonical transcript with responder's Ed25519 identity private key
    private_key = responder_identity.get_identity_private_key()
    signature_bytes = private_key.sign(transcript_bytes)

    return AuthenticationResponse(
        session_id=challenge.session_id,
        responder_id=responder_identity.terminal_id,
        signature_hex=signature_bytes.hex(),
    )


def verify_response(
    challenge: AuthenticationChallenge,
    response: AuthenticationResponse,
    registry: TerminalRegistry,
    freshness_validator: Optional[FreshnessValidator] = None,
    replay_cache: Optional[ReplayProtectionCache] = None,
    expected_epoch: Optional[int] = None,
) -> bool:
    """Verify an authentication response against trusted terminal registry and freshness rules.
    
    Args:
        challenge: The original challenge sent by the initiator.
        response: The response returned by the responder.
        registry: TerminalRegistry containing trusted public keys.
        freshness_validator: Optional validator for timestamp freshness.
        replay_cache: Optional cache for replay attack detection.
        expected_epoch: Optional expected tracking epoch to enforce.
        
    Returns:
        True if response is fully verified and authentic.
        
    Raises:
        InvalidTranscriptError: If fields mismatch or transcript context is modified.
        InvalidSignatureError: If Ed25519 signature verification fails.
        TerminalNotFoundError: If responder terminal is unknown.
        FreshnessError / ReplayAttackError: If timestamp or nonce validation fails.
    """
    if not isinstance(challenge, AuthenticationChallenge):
        raise TypeError("Expected AuthenticationChallenge instance.")
    if not isinstance(response, AuthenticationResponse):
        raise TypeError("Expected AuthenticationResponse instance.")

    # 1. Verify field consistency
    if response.session_id != challenge.session_id:
        raise InvalidTranscriptError(
            f"Session ID mismatch: challenge has '{challenge.session_id}', response has '{response.session_id}'"
        )

    if response.responder_id != challenge.responder_id:
        raise InvalidTranscriptError(
            f"Responder ID mismatch: challenge target '{challenge.responder_id}', response claims '{response.responder_id}'"
        )

    if expected_epoch is not None and challenge.tracking_epoch != expected_epoch:
        raise InvalidTranscriptError(
            f"Tracking epoch mismatch: expected epoch {expected_epoch}, challenge has epoch {challenge.tracking_epoch}"
        )

    # 2. Validate timestamp freshness if validator provided
    if freshness_validator is not None:
        freshness_validator.validate_challenge(challenge)

    # 3. Check replay protection if cache provided
    if replay_cache is not None:
        replay_cache.check_and_register(challenge)

    # 4. Lookup responder's trusted public credentials
    pub_creds = registry.get_public_credentials(response.responder_id)
    public_key = pub_creds.identity_public_key

    # 5. Compute canonical transcript bytes
    transcript_bytes = compute_canonical_transcript(challenge, direction="RESPONSE")

    # 6. Verify Ed25519 signature over canonical transcript
    try:
        public_key.verify(response.get_signature_bytes(), transcript_bytes)
    except InvalidSignature as e:
        raise InvalidSignatureError(f"Ed25519 signature verification failed for terminal '{response.responder_id}'") from e

    return True


def authenticate_mutually(
    initiator_identity: TerminalIdentity,
    responder_identity: TerminalIdentity,
    registry: TerminalRegistry,
    tracking_epoch: int = 1,
    freshness_validator: Optional[FreshnessValidator] = None,
    replay_cache: Optional[ReplayProtectionCache] = None,
) -> Dict[str, Any]:
    """Perform a complete 2-way mutual authentication handshake between two terminals.
    
    Returns:
        Dictionary containing authentication results:
        {
            "local_authenticated": True,
            "remote_authenticated": True,
            "mutual_authentication_success": True,
            "initiator_session": AuthenticationSession,
            "responder_session": AuthenticationSession,
        }
    """
    init_sess = AuthenticationSession(initiator_identity.terminal_id, initial_epoch=tracking_epoch)
    resp_sess = AuthenticationSession(responder_identity.terminal_id, initial_epoch=tracking_epoch)

    validator = freshness_validator or FreshnessValidator()
    cache = replay_cache or ReplayProtectionCache()

    # --- Handshake Phase A: Initiator (T1) verifies Responder (T2) ---
    ch1 = create_challenge(initiator_identity.terminal_id, responder_identity.terminal_id, tracking_epoch=tracking_epoch)
    init_sess.mark_authenticating(ch1.session_id)
    
    res1 = create_response(ch1, responder_identity)
    verify_response(ch1, res1, registry, freshness_validator=validator, replay_cache=cache, expected_epoch=tracking_epoch)
    
    init_sess.mark_remote_authenticated(responder_identity.terminal_id)
    resp_sess.mark_local_authenticated()

    # --- Handshake Phase B: Responder (T2) verifies Initiator (T1) ---
    ch2 = create_challenge(responder_identity.terminal_id, initiator_identity.terminal_id, tracking_epoch=tracking_epoch)
    resp_sess.mark_authenticating(ch2.session_id)
    
    res2 = create_response(ch2, initiator_identity)
    verify_response(ch2, res2, registry, freshness_validator=validator, replay_cache=cache, expected_epoch=tracking_epoch)
    
    resp_sess.mark_remote_authenticated(initiator_identity.terminal_id)
    init_sess.mark_local_authenticated()

    return {
        "local_authenticated": init_sess.local_authenticated and resp_sess.local_authenticated,
        "remote_authenticated": init_sess.remote_authenticated and resp_sess.remote_authenticated,
        "mutual_authentication_success": init_sess.mutual_authentication_success and resp_sess.mutual_authentication_success,
        "initiator_session": init_sess,
        "responder_session": resp_sess,
    }
