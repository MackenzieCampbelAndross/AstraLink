"""Phase 8: Attack Simulation Module for Astra Link Member 3."""

from .cloned_beacon import FakeBeaconAttack
from .forged_ack import ForgedAckAttack
from .forged_resume import ForgedResumeAttack
from .invalid_credentials import InvalidCredentialAttack
from .jamming import OpticalJammingAttack
from .packet_tampering import PacketTamperingAttack
from .replay import ReplayAttack

__all__ = [
    "FakeBeaconAttack",
    "ReplayAttack",
    "PacketTamperingAttack",
    "ForgedAckAttack",
    "ForgedResumeAttack",
    "InvalidCredentialAttack",
    "OpticalJammingAttack",
]
