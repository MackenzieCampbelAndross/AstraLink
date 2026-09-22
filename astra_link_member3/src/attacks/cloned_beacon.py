"""Attack 1: Cloned / Fake Beacon Attack Simulation."""

from typing import Dict, Optional, Tuple

from ..authentication import AuthenticationController, AuthenticationResult
from ..identity import TerminalCredentials, TerminalRegistry, generate_credentials
from ..tracking import TrackingState
from ..trust import SecurityLogger


class FakeBeaconAttack:
    """Simulates a fake optical beacon attack.
    
    The fake beacon imitates visual tracking characteristics (LOCKED status)
    but lacks legitimate Ed25519 identity private credentials.
    """

    def __init__(
        self,
        registry: TerminalRegistry,
        logger: Optional[SecurityLogger] = None,
    ):
        self.registry = registry
        self.logger = logger or SecurityLogger()
        self.attempts_count: int = 0
        self.rejections_count: int = 0
        self.prevented_unauthorized_transmissions: int = 0

    def execute_attack(
        self,
        target_terminal_id: str = "T1",
        attacker_terminal_id: str = "T2",
        tracking_state: Optional[TrackingState] = None,
        target_creds: Optional[TerminalCredentials] = None,
    ) -> Tuple[bool, str, Dict[str, str]]:
        """Execute cloned beacon attack.
        
        Returns:
            Tuple of (attack_succeeded: bool, reason: str, details: dict)
        """
        self.attempts_count += 1
        self.logger.log_event(
            "SPOOF_ATTEMPT",
            target_terminal_id,
            attacker_terminal_id,
            {"reason": "CLONED_BEACON_VISUAL_LOCK_ATTEMPT"},
        )

        # 1. Fake beacon provides valid tracking lock
        if tracking_state is None:
            tracking_state = TrackingState(
                timestamp=100.0,
                tracking_state="LOCKED",
                predicted_x=10.0,
                predicted_y=20.0,
                angular_x=0.01,
                angular_y=0.02,
                velocity_x=0.1,
                velocity_y=0.2,
                motion_consistency=0.95,
            )

        # 2. Attacker lacks legitimate private credential registered in registry
        legit_target_creds = target_creds or generate_credentials(target_terminal_id)
        attacker_unauthorized_creds = generate_credentials(attacker_terminal_id)

        temp_reg = TerminalRegistry()
        temp_reg.register_public_credentials(legit_target_creds.public_credentials)

        auth_ctrl = AuthenticationController(registry=temp_reg)
        auth_res = auth_ctrl.execute_mutual_authentication(
            t1_creds=legit_target_creds,
            t2_creds=attacker_unauthorized_creds,
            tracking_epoch=1,
        )

        if not auth_res.authenticated:
            self.rejections_count += 1
            self.prevented_unauthorized_transmissions += 1
            self.logger.log_event(
                "SPOOF_REJECTED",
                target_terminal_id,
                attacker_terminal_id,
                {"reason": auth_res.reason, "transmission_allowed": False},
            )
            return False, f"SPOOF_REJECTED: {auth_res.reason}", {"transmission_allowed": "False"}

        return True, "SPOOF_SUCCEEDED_WARNING", {"transmission_allowed": "True"}
