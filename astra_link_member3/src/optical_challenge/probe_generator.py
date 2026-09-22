"""Optical challenge probe sequence generator and data models."""

import secrets
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List

from src.tracking import TrackingState


@dataclass(frozen=True)
class Probe:
    """Represents a single optical probe pulse in a challenge sequence."""

    probe_id: int
    offset_x: float
    offset_y: float
    expected_angular_x: float
    expected_angular_y: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "probe_id": self.probe_id,
            "offset_x": self.offset_x,
            "offset_y": self.offset_y,
            "expected_angular_x": self.expected_angular_x,
            "expected_angular_y": self.expected_angular_y,
        }


@dataclass(frozen=True)
class OpticalChallenge:
    """Represents an optical challenge issued to a tracked terminal."""

    challenge_id: str
    session_id: str
    tracking_epoch: int
    creation_timestamp: float
    probes: List[Probe] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "challenge_id": self.challenge_id,
            "session_id": self.session_id,
            "tracking_epoch": self.tracking_epoch,
            "creation_timestamp": self.creation_timestamp,
            "probes": [p.to_dict() for p in self.probes],
        }

    def __repr__(self) -> str:
        return (
            f"OpticalChallenge(challenge_id={self.challenge_id[:8]}..., "
            f"session_id={self.session_id[:8]}..., epoch={self.tracking_epoch}, probes={len(self.probes)})"
        )


class ProbeGenerator:
    """Generates controlled optical challenge probe sequences derived from tracking state."""

    def __init__(self, probe_count: int = 4, probe_offset_angle: float = 0.02):
        self.probe_count = max(1, probe_count)
        self.probe_offset_angle = float(probe_offset_angle)

    def generate_challenge(
        self,
        session_id: str,
        tracking_epoch: int,
        tracking_state: TrackingState,
    ) -> OpticalChallenge:
        """Generate a fresh OpticalChallenge based on tracking angles and session context."""
        if not session_id or not isinstance(session_id, str):
            raise ValueError("session_id must be a non-empty string.")

        challenge_id = secrets.token_hex(16)
        creation_timestamp = round(time.time(), 3)

        base_ax = tracking_state.angular_x
        base_ay = tracking_state.angular_y
        off = self.probe_offset_angle

        # Define controlled offsets for probes (+X, -X, +Y, -Y)
        offsets = [
            (off, 0.0),
            (-off, 0.0),
            (0.0, off),
            (0.0, -off),
        ]

        probes = []
        for i in range(self.probe_count):
            dx, dy = offsets[i % len(offsets)]
            probe = Probe(
                probe_id=i + 1,
                offset_x=dx,
                offset_y=dy,
                expected_angular_x=base_ax + dx,
                expected_angular_y=base_ay + dy,
            )
            probes.append(probe)

        return OpticalChallenge(
            challenge_id=challenge_id,
            session_id=session_id,
            tracking_epoch=tracking_epoch,
            creation_timestamp=creation_timestamp,
            probes=probes,
        )
