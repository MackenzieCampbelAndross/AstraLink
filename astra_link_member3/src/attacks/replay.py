"""Attack 2: Replay Attack Simulation."""

from typing import Dict, Optional, Tuple

from ..authentication import (
    AuthenticationChallenge,
    AuthenticationResponse,
    FreshnessValidator,
    InvalidTranscriptError,
    ReplayAttackError,
    ReplayProtectionCache,
    create_challenge,
    create_response,
    verify_response,
)
from ..identity import TerminalCredentials, TerminalIdentity, TerminalRegistry, generate_credentials
from ..trust import SecurityLogger


class ReplayAttack:
    """Simulates replay attacks using captured authentic challenge/response messages."""

    def __init__(
        self,
        registry: TerminalRegistry,
        logger: Optional[SecurityLogger] = None,
    ):
        self.registry = registry
        self.logger = logger or SecurityLogger()
        self.replay_cache = ReplayProtectionCache()
        self.freshness_validator = FreshnessValidator()

        self.attempts_count: int = 0
        self.rejections_count: int = 0
        self.accepted_count: int = 0

    def capture_legitimate_handshake(
        self,
        initiator_id: str = "T1",
        responder_id: str = "T2",
        tracking_epoch: int = 1,
    ) -> Tuple[AuthenticationChallenge, AuthenticationResponse, TerminalCredentials, TerminalCredentials]:
        """Generate and capture a legitimate authentication exchange."""
        t1_creds = generate_credentials(initiator_id)
        t2_creds = generate_credentials(responder_id)

        self.registry.register_public_credentials(t1_creds.public_credentials)
        self.registry.register_public_credentials(t2_creds.public_credentials)

        ch = create_challenge(initiator_id, responder_id, tracking_epoch=tracking_epoch)
        t2_identity = TerminalIdentity(t2_creds)
        res = create_response(ch, t2_identity)

        # Register legitimate exchange in cache
        verify_response(
            challenge=ch,
            response=res,
            registry=self.registry,
            freshness_validator=self.freshness_validator,
            replay_cache=self.replay_cache,
            expected_epoch=tracking_epoch,
        )
        return ch, res, t1_creds, t2_creds

    def execute_replay_attempt(
        self,
        challenge: AuthenticationChallenge,
        response: AuthenticationResponse,
        scenario: str = "EXACT_REPLAY",
        new_epoch: Optional[int] = None,
    ) -> Tuple[bool, str]:
        """Execute replay attack scenario.
        
        Scenarios:
            - EXACT_REPLAY: Same challenge and response replayed.
            - NEW_EPOCH_REPLAY: Replaying challenge/response under new tracking epoch.
            - MISMATCHED_SESSION: Replaying response under modified session ID.
        """
        self.attempts_count += 1
        self.logger.log_event(
            "REPLAY_ATTEMPT",
            challenge.initiator_id,
            challenge.responder_id,
            {"scenario": scenario, "session_id": challenge.session_id[:8]},
        )

        expected_epoch = new_epoch if new_epoch is not None else challenge.tracking_epoch

        try:
            verify_response(
                challenge=challenge,
                response=response,
                registry=self.registry,
                freshness_validator=self.freshness_validator,
                replay_cache=self.replay_cache,
                expected_epoch=expected_epoch,
            )
            self.accepted_count += 1
            return True, "REPLAY_ACCEPTED_UNEXPECTED"
        except (ReplayAttackError, InvalidTranscriptError, Exception) as e:
            self.rejections_count += 1
            self.logger.log_event(
                "REPLAY_REJECTED",
                challenge.initiator_id,
                challenge.responder_id,
                {"scenario": scenario, "reason": str(e)},
            )
            return False, f"REPLAY_REJECTED: {e}"
