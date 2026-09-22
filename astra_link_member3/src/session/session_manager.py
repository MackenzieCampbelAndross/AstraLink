"""Session Manager managing session creation, authentication binding, validity, expiry, and termination."""

import secrets
import time
from typing import Dict, Optional, Tuple

from .hkdf_derivation import DerivedSessionKeys, derive_session_key_material
from .key_exchange import EphemeralKeyPair, KeyExchange
from .rekey import execute_rekey
from .session_context import SessionContext, SessionState


class SessionError(Exception):
    """Base exception for session operations."""
    pass


class SessionAuthorizationError(SessionError):
    """Raised when session creation is attempted without required authentication and trust authorization."""
    pass


class SessionNotFoundError(SessionError):
    """Raised when a requested session is not found."""
    pass


class SessionExpiredError(SessionError):
    """Raised when an operation is attempted on an expired session."""
    pass


class ActiveSession:
    """Represents an active secure session instance holding context and derived keys."""

    def __init__(
        self,
        context: SessionContext,
        derived_keys: DerivedSessionKeys,
        initiator_ephemeral: EphemeralKeyPair,
        responder_ephemeral: EphemeralKeyPair,
    ):
        self.context = context
        self.derived_keys = derived_keys
        self.state = SessionState.ESTABLISHED
        self.initiator_ephemeral = initiator_ephemeral
        self.responder_ephemeral = responder_ephemeral

    @property
    def session_id(self) -> str:
        return self.context.session_id

    @property
    def tracking_epoch(self) -> int:
        return self.context.tracking_epoch

    def __repr__(self) -> str:
        return (
            f"ActiveSession(session_id={self.session_id[:8]}..., "
            f"initiator={self.context.initiator_id!r}, responder={self.context.responder_id!r}, "
            f"state={self.state.value})"
        )


class SessionManager:
    """Manages the full lifecycle of secure sessions."""

    def __init__(
        self,
        session_lifetime_seconds: float = 300.0,
        rekey_interval_seconds: float = 120.0,
    ):
        self.session_lifetime_seconds = float(session_lifetime_seconds)
        self.rekey_interval_seconds = float(rekey_interval_seconds)
        self._active_sessions: Dict[str, ActiveSession] = {}

    def establish_session(
        self,
        initiator_id: str,
        responder_id: str,
        tracking_epoch: int,
        authentication_valid: bool,
        trust_authorized: bool,
        protocol_version: str = "1.0",
    ) -> ActiveSession:
        """Establish a new secure session for authenticated and trusted peers.
        
        Raises:
            SessionAuthorizationError: If authentication or trust authorization is invalid.
        """
        # HARD PRECONDITION: Mutual Authentication and Trust Authorization required!
        if not authentication_valid or not trust_authorized:
            raise SessionAuthorizationError(
                f"Session establishment BLOCKED for {initiator_id} <-> {responder_id}: "
                f"authentication_valid={authentication_valid}, trust_authorized={trust_authorized}"
            )

        session_id = secrets.token_hex(16)
        created_at = round(time.time(), 3)

        # Generate fresh ephemeral key pairs
        init_ephemeral = EphemeralKeyPair.generate(initiator_id)
        resp_ephemeral = EphemeralKeyPair.generate(responder_id)

        context = SessionContext(
            session_id=session_id,
            initiator_id=initiator_id,
            responder_id=responder_id,
            tracking_epoch=tracking_epoch,
            created_at=created_at,
            initiator_ephemeral_public_key=init_ephemeral.public_key,
            responder_ephemeral_public_key=resp_ephemeral.public_key,
            protocol_version=protocol_version,
        )

        # X25519 ECDH Shared Secret
        shared_secret = KeyExchange.derive_shared_secret(init_ephemeral, resp_ephemeral.public_key)

        # HKDF SHA-256 Session Key Derivation
        derived_keys = derive_session_key_material(shared_secret, context)

        active_session = ActiveSession(
            context=context,
            derived_keys=derived_keys,
            initiator_ephemeral=init_ephemeral,
            responder_ephemeral=resp_ephemeral,
        )

        self._active_sessions[session_id] = active_session
        return active_session

    def get_session(self, session_id: str) -> ActiveSession:
        """Retrieve an active session by session_id.
        
        Raises:
            SessionNotFoundError: If session does not exist.
        """
        if session_id not in self._active_sessions:
            raise SessionNotFoundError(f"Session '{session_id}' not found.")
        return self._active_sessions[session_id]

    def is_session_valid(
        self,
        session_id: str,
        current_time: Optional[float] = None,
    ) -> bool:
        """Check if a session exists, is in ESTABLISHED state, and has not expired."""
        if session_id not in self._active_sessions:
            return False

        session = self._active_sessions[session_id]
        if session.state != SessionState.ESTABLISHED:
            return False

        now = current_time if current_time is not None else time.time()
        age = now - session.context.created_at

        if age > self.session_lifetime_seconds:
            session.state = SessionState.EXPIRED
            return False

        return True

    def expire_session(self, session_id: str) -> None:
        """Force session state to EXPIRED."""
        session = self.get_session(session_id)
        session.state = SessionState.EXPIRED

    def terminate_session(self, session_id: str) -> None:
        """Explicitly terminate a session."""
        session = self.get_session(session_id)
        session.state = SessionState.TERMINATED

    def rekey_session(self, session_id: str) -> ActiveSession:
        """Rekey an active session by generating new ephemeral keys and session key material."""
        session = self.get_session(session_id)

        if session.state != SessionState.ESTABLISHED:
            raise SessionError(f"Cannot rekey session '{session_id}' in state {session.state.value}")

        # Generate fresh ephemeral key pairs
        new_init_ephemeral = EphemeralKeyPair.generate(session.context.initiator_id)
        new_resp_ephemeral = EphemeralKeyPair.generate(session.context.responder_id)

        new_context, new_keys = execute_rekey(
            session.context, new_init_ephemeral, new_resp_ephemeral
        )

        session.context = new_context
        session.derived_keys = new_keys
        session.initiator_ephemeral = new_init_ephemeral
        session.responder_ephemeral = new_resp_ephemeral

        return session
