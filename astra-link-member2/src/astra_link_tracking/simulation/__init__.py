"""Simulation module: trajectories, virtual camera, dummy detection, closed-loop simulation."""

from astra_link_tracking.simulation.trajectories import TrajectoryGenerator
from astra_link_tracking.simulation.virtual_camera import VirtualCamera
from astra_link_tracking.simulation.dummy_detection import DummyDetectionGenerator
from astra_link_tracking.simulation.closed_loop import ClosedLoopSimulation

__all__ = [
    "TrajectoryGenerator",
    "VirtualCamera",
    "DummyDetectionGenerator",
    "ClosedLoopSimulation",
]
