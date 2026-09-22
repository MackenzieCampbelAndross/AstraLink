"""Attack 7: Invalid / Unregistered Credential Attack Simulation."""

from typing import Optional, Tuple

from ..authentication import AuthenticationController
from ..identity import TerminalCredentials, TerminalRegistry, generate_credentials
from ..trust import SecurityLogger


class InvalidCredentialAttack:
    """Simulates an authentication attempt by an unknown/unregistered terminal possessing valid cryptographic keys."""

    def __init__(
        self,
        registry: TerminalRegistry,
        logger: Optional[SecurityLogger] = None,
    ):
        self.registry = registry
        self.logger = logger or SecurityLogger()
        self.attempts_count: int = 0
        self.rejections_count: int = 0

    def execute_unregistered_terminal_attack(
        self,
        registered_target_id: str = "T1",
        unregistered_attacker_id: str = "T3_UNREGISTERED",
        t1_creds: Optional[TerminalCredentials] = None,
    ) -> Tuple[bool, str]:
        """Attempt authentication from an unregistered terminal."""
        self.attempts_count += 1

        self.logger.log_event(
            "INVALID_CREDENTIAL_ATTEMPT",
            registered_target_id,
            unregistered_attacker_id,
            {"reason": "UNREGISTERED_TERMINAL_KEY_PRESENT"},
        )

        target_creds = t1_creds or generate_credentials(registered_target_id)
        t3_unregistered_creds = generate_credentials(unregistered_attacker_id)

        # Use isolated registry to prevent mutating main registry
        temp_registry = TerminalRegistry()
        temp_registry.register_public_credentials(target_creds.public_credentials)

        auth_ctrl = AuthenticationController(registry=temp_registry)
        auth_res = auth_ctrl.execute_mutual_authentication(
            t1_creds=target_creds,
            t2_creds=t3_unregistered_creds,
            tracking_epoch=1,
        )

        if not auth_res.authenticated:
            self.rejections_count += 1
            self.logger.log_event(
                "AUTHENTICATION_REJECTED",
                registered_target_id,
                unregistered_attacker_id,
                {"reason": auth_res.reason, "transmission_allowed": False},
            )
            return False, f"AUTHENTICATION_REJECTED: {auth_res.reason}"

        return True, "AUTHENTICATION_ACCEPTED_UNEXPECTED"
