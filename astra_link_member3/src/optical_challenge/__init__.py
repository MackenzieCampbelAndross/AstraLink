"""Optical challenge simulation and physical validation module."""

from .physical_validation import (
    PhysicalConsistencyValidator,
    PhysicalValidationResult,
)
from .probe_generator import OpticalChallenge, Probe, ProbeGenerator
from .probe_response import OpticalResponse, OpticalResponseSimulator

__all__ = [
    "Probe",
    "OpticalChallenge",
    "ProbeGenerator",
    "OpticalResponse",
    "OpticalResponseSimulator",
    "PhysicalValidationResult",
    "PhysicalConsistencyValidator",
]
