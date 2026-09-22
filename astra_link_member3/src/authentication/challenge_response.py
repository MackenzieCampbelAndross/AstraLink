"""Challenge response authentication controller for Astra Link."""

from dataclasses import dataclass
from typing import Optional

from src.identity import TerminalCredentials, TerminalRegistry

from .freshness import FreshnessValidator, ReplayProtectionCache
from .mutual_auth import authenticate_mutually


@dataclass
class AuthenticationResult:
    """Result of mutual authentication attempt."""

    authenticated: bool
    reason: str


class AuthenticationController:
    """Controller for executing mutual challenge-response authentication."""

    def __init__(
        self,
        registry: TerminalRegistry,
        freshness_validator: Optional[FreshnessValidator] = None,
        replay_cache: Optional[ReplayProtectionCache] = None,
    ):
        self.registry = registry
        self.freshness_validator = freshness_validator or FreshnessValidator()
        self.replay_cache = replay_cache or ReplayProtectionCache()

    def execute_mutual_authentication(
        self,
        t1_creds: TerminalCredentials,
        t2_creds: TerminalCredentials,
        tracking_epoch: int = 1,
    ) -> AuthenticationResult:
        """Execute 2-way mutual challenge-response authentication."""
        from src.identity import TerminalIdentity
        t1_identity = TerminalIdentity(t1_creds)
        t2_identity = TerminalIdentity(t2_creds)

        try:
            res = authenticate_mutually(
                initiator_identity=t1_identity,
                responder_identity=t2_identity,
                registry=self.registry,
                tracking_epoch=tracking_epoch,
                freshness_validator=self.freshness_validator,
                replay_cache=self.replay_cache,
            )
            if res.get("mutual_authentication_success", False):
                return AuthenticationResult(authenticated=True, reason="MUTUAL_AUTHENTICATION_SUCCESS")
            return AuthenticationResult(authenticated=False, reason="MUTUAL_AUTHENTICATION_FAILED")
        except Exception as e:
            return AuthenticationResult(authenticated=False, reason=str(e))
