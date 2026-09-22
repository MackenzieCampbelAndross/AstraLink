"""Optical challenge response models and multi-scenario simulator."""

import random
import time
from dataclasses import dataclass
from typing import Any, Dict, List

from src.tracking import TrackingState
from .probe_generator import OpticalChallenge


@dataclass(frozen=True)
class OpticalResponse:
    """Represents the optical response returned for a specific probe."""

    challenge_id: str
    probe_id: int
    angular_response_x: float
    angular_response_y: float
    received_signal: float
    timestamp: float
    signal_quality: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "challenge_id": self.challenge_id,
            "probe_id": self.probe_id,
            "angular_response_x": self.angular_response_x,
            "angular_response_y": self.angular_response_y,
            "received_signal": self.received_signal,
            "timestamp": self.timestamp,
            "signal_quality": self.signal_quality,
        }


class OpticalResponseSimulator:
    """Simulates terminal optical responses under legitimate, fake, inconsistent, and degraded scenarios."""

    def __init__(self, response_noise_std: float = 0.005):
        self.response_noise_std = float(response_noise_std)

    def simulate_legitimate_response(
        self,
        challenge: OpticalChallenge,
        tracking_state: TrackingState,
        noise_std: float = 0.005,
    ) -> List[OpticalResponse]:
        """Simulate a legitimate response matching target tracking predictions within bounded noise."""
        responses = []
        now = round(time.time(), 3)
        for probe in challenge.probes:
            noise_x = random.gauss(0.0, noise_std)
            noise_y = random.gauss(0.0, noise_std)
            resp = OpticalResponse(
                challenge_id=challenge.challenge_id,
                probe_id=probe.probe_id,
                angular_response_x=probe.expected_angular_x + noise_x,
                angular_response_y=probe.expected_angular_y + noise_y,
                received_signal=0.92,
                timestamp=now,
                signal_quality=0.95,
            )
            responses.append(resp)
        return responses

    def simulate_fake_response(self, challenge: OpticalChallenge) -> List[OpticalResponse]:
        """Simulate a response from a fake beacon (unaligned angles, random values)."""
        responses = []
        now = round(time.time(), 3)
        for probe in challenge.probes:
            resp = OpticalResponse(
                challenge_id=challenge.challenge_id,
                probe_id=probe.probe_id,
                angular_response_x=9.99,  # Completely unaligned
                angular_response_y=-8.88,
                received_signal=0.10,
                timestamp=now,
                signal_quality=0.15,
            )
            responses.append(resp)
        return responses

    def simulate_inconsistent_response(
        self,
        challenge: OpticalChallenge,
        tracking_state: TrackingState,
    ) -> List[OpticalResponse]:
        """Simulate a response with physical motion inconsistency (large angular deviation)."""
        responses = []
        now = round(time.time(), 3)
        for probe in challenge.probes:
            # Large angular offset (1.20 rad) far outside uncertainty
            resp = OpticalResponse(
                challenge_id=challenge.challenge_id,
                probe_id=probe.probe_id,
                angular_response_x=probe.expected_angular_x + 1.20,
                angular_response_y=probe.expected_angular_y - 0.90,
                received_signal=0.80,
                timestamp=now,
                signal_quality=0.85,
            )
            responses.append(resp)
        return responses

    def simulate_degraded_response(
        self,
        challenge: OpticalChallenge,
        tracking_state: TrackingState,
    ) -> List[OpticalResponse]:
        """Simulate a response with degraded optical signal quality."""
        responses = []
        now = round(time.time(), 3)
        for probe in challenge.probes:
            resp = OpticalResponse(
                challenge_id=challenge.challenge_id,
                probe_id=probe.probe_id,
                angular_response_x=probe.expected_angular_x,
                angular_response_y=probe.expected_angular_y,
                received_signal=0.25,
                timestamp=now,
                signal_quality=0.30,  # Below 0.50 threshold
            )
            responses.append(resp)
        return responses
