"""Synthetic trajectory generation for testing."""

from typing import Tuple, List, Optional
import numpy as np


class TrajectoryGenerator:
    """Generates synthetic trajectories for testing.
    
    All trajectories are deterministic unless seeded random is explicitly requested.
    """
    
    def __init__(
        self,
        trajectory_type: str = "stationary",
        duration: float = 60.0,
        dt: float = 0.1,
        seed: Optional[int] = None
    ):
        """Initialize trajectory generator.
        
        Args:
            trajectory_type: Type of trajectory (stationary, linear, circular, figure8, sinusoidal, random, spiral)
            duration: Simulation duration in seconds
            dt: Time step in seconds
            seed: Random seed for reproducibility (None for deterministic)
        """
        self.trajectory_type = trajectory_type
        self.duration = duration
        self.dt = dt
        self.seed = seed
        
        if seed is not None:
            np.random.seed(seed)
    
    def generate(self) -> List[Tuple[float, Tuple[float, float], Tuple[float, float]]]:
        """Generate trajectory.
        
        Returns:
            List of (timestamp, position (degrees), velocity (degrees/second)) tuples
        """
        if self.trajectory_type == "stationary":
            return self._generate_stationary()
        elif self.trajectory_type == "linear":
            return self._generate_linear()
        elif self.trajectory_type == "circular":
            return self._generate_circular()
        elif self.trajectory_type == "figure8":
            return self._generate_figure8()
        elif self.trajectory_type == "sinusoidal":
            return self._generate_sinusoidal()
        elif self.trajectory_type == "random":
            return self._generate_random()
        elif self.trajectory_type == "spiral":
            return self._generate_spiral()
        else:
            return self._generate_stationary()
    
    def _generate_stationary(self) -> List[Tuple[float, Tuple[float, float], Tuple[float, float]]]:
        """Generate stationary trajectory.
        
        Returns:
            List of (timestamp, position, velocity) tuples
        """
        trajectory = []
        t = 0.0
        position = (0.0, 0.0)  # Center
        velocity = (0.0, 0.0)
        
        while t < self.duration:
            trajectory.append((t, position, velocity))
            t += self.dt
        
        return trajectory
    
    def _generate_linear(self) -> List[Tuple[float, Tuple[float, float], Tuple[float, float]]]:
        """Generate linear trajectory (constant velocity).
        
        Returns:
            List of (timestamp, position, velocity) tuples
        """
        trajectory = []
        t = 0.0
        velocity = (0.5, 0.3)  # degrees/second
        start_position = (-2.0, -1.5)  # Start off-center
        
        while t < self.duration:
            x = start_position[0] + velocity[0] * t
            y = start_position[1] + velocity[1] * t
            trajectory.append((t, (x, y), velocity))
            t += self.dt
        
        return trajectory
    
    def _generate_circular(self) -> List[Tuple[float, Tuple[float, float], Tuple[float, float]]]:
        """Generate circular trajectory.
        
        Returns:
            List of (timestamp, position, velocity) tuples
        """
        trajectory = []
        t = 0.0
        radius = 1.5  # degrees
        omega = 2 * np.pi / 20.0  # One revolution every 20 seconds
        
        while t < self.duration:
            x = radius * np.cos(omega * t)
            y = radius * np.sin(omega * t)
            
            vx = -radius * omega * np.sin(omega * t)
            vy = radius * omega * np.cos(omega * t)
            
            trajectory.append((t, (x, y), (vx, vy)))
            t += self.dt
        
        return trajectory
    
    def _generate_figure8(self) -> List[Tuple[float, Tuple[float, float], Tuple[float, float]]]:
        """Generate figure-8 trajectory.
        
        Returns:
            List of (timestamp, position, velocity) tuples
        """
        trajectory = []
        t = 0.0
        scale = 1.5  # degrees
        omega = 2 * np.pi / 20.0  # Period of 20 seconds
        
        while t < self.duration:
            x = scale * np.sin(omega * t)
            y = scale * np.sin(2 * omega * t)
            
            vx = scale * omega * np.cos(omega * t)
            vy = scale * 2 * omega * np.cos(2 * omega * t)
            
            trajectory.append((t, (x, y), (vx, vy)))
            t += self.dt
        
        return trajectory
    
    def _generate_sinusoidal(self) -> List[Tuple[float, Tuple[float, float], Tuple[float, float]]]:
        """Generate sinusoidal trajectory.
        
        Returns:
            List of (timestamp, position, velocity) tuples
        """
        trajectory = []
        t = 0.0
        amplitude = 1.5  # degrees
        omega = 2 * np.pi / 10.0  # Period of 10 seconds
        
        while t < self.duration:
            x = amplitude * np.sin(omega * t)
            y = amplitude * np.cos(omega * t) * 0.5  # Smaller amplitude in Y
            
            vx = amplitude * omega * np.cos(omega * t)
            vy = -amplitude * 0.5 * omega * np.sin(omega * t)
            
            trajectory.append((t, (x, y), (vx, vy)))
            t += self.dt
        
        return trajectory
    
    def _generate_random(self) -> List[Tuple[float, Tuple[float, float], Tuple[float, float]]]:
        """Generate random walk trajectory (requires seed for reproducibility).
        
        Returns:
            List of (timestamp, position, velocity) tuples
        """
        if self.seed is None:
            raise ValueError("Random trajectory requires a seed for reproducibility")
        
        trajectory = []
        t = 0.0
        position = (0.0, 0.0)
        velocity = (0.0, 0.0)
        
        while t < self.duration:
            # Random velocity change
            dv_x = np.random.uniform(-0.1, 0.1)
            dv_y = np.random.uniform(-0.1, 0.1)
            
            velocity = (velocity[0] + dv_x, velocity[1] + dv_y)
            
            # Clamp velocity
            max_vel = 1.0
            velocity = (
                max(-max_vel, min(max_vel, velocity[0])),
                max(-max_vel, min(max_vel, velocity[1]))
            )
            
            # Update position
            position = (position[0] + velocity[0] * self.dt, position[1] + velocity[1] * self.dt)
            
            trajectory.append((t, position, velocity))
            t += self.dt
        
        return trajectory
    
    def _generate_spiral(self) -> List[Tuple[float, Tuple[float, float], Tuple[float, float]]]:
        """Generate spiral trajectory.
        
        Returns:
            List of (timestamp, position, velocity) tuples
        """
        trajectory = []
        t = 0.0
        radius_start = 0.5
        radius_end = 2.0
        omega = 2 * np.pi / 20.0  # One revolution every 20 seconds
        
        while t < self.duration:
            # Radius increases linearly
            radius = radius_start + (radius_end - radius_start) * (t / self.duration)
            
            x = radius * np.cos(omega * t)
            y = radius * np.sin(omega * t)
            
            # Velocity includes radial component
            dr_dt = (radius_end - radius_start) / self.duration
            vx = dr_dt * np.cos(omega * t) - radius * omega * np.sin(omega * t)
            vy = dr_dt * np.sin(omega * t) + radius * omega * np.cos(omega * t)
            
            trajectory.append((t, (x, y), (vx, vy)))
            t += self.dt
        
        return trajectory
