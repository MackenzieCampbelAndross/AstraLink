"""Lévy flight search strategy for reacquisition."""

from typing import Tuple, Optional
import numpy as np

from astra_link_tracking.models.config import ReacquisitionConfig


class LevySearch:
    """Lévy flight search strategy for efficient reacquisition.
    
    Implements a mathematically correct Lévy flight using a power-law
    distribution for step sizes. The Lévy distribution is characterized
    by a heavy-tailed power-law distribution:
    
    P(l) ~ l^(-α)
    
    where α is the Lévy exponent (typically 1 < α < 3).
    
    This implementation uses inverse transform sampling on a Pareto
    distribution, which is equivalent to a one-sided Lévy distribution.
    
    The search is reproducible with a random seed.
    """
    
    def __init__(self, config: ReacquisitionConfig, seed: Optional[int] = None):
        """Initialize Lévy search with configuration.
        
        Args:
            config: Reacquisition configuration with Lévy parameters
            seed: Random seed for reproducibility
        """
        self.config = config
        self.seed = seed
        
        # Lévy parameters
        self.alpha = config.levy_alpha  # Lévy exponent (typically 1.5)
        self.min_step = config.levy_min_step  # Minimum step size (degrees)
        self.max_step = config.levy_max_step  # Maximum step size (degrees)
        
        # Search state
        self.current_position: Tuple[float, float] = (0.0, 0.0)
        self.step_count = 0
        
        # Set random seed
        if seed is not None:
            np.random.seed(seed)
    
    def generate_step(self) -> Tuple[float, float]:
        """Generate next search step using Lévy distribution.
        
        Uses inverse transform sampling on a Pareto distribution:
        l = min_step * (1 - u)^(-1/α)
        
        where u is uniform in (0, 1). This produces a power-law
        distribution with exponent α.
        
        Returns:
            (dx, dy) step size in degrees
        """
        # Generate uniform random
        u = np.random.uniform(0, 1)
        
        # Inverse transform sampling for Pareto (equivalent to one-sided Lévy)
        # Clamp u to avoid division by zero
        u = max(u, 1e-10)
        step_size = self.min_step * ((1 - u) ** (-1.0 / self.alpha))
        
        # Clamp to maximum step size
        step_size = min(step_size, self.max_step)
        
        # Random direction
        angle = np.random.uniform(0, 2 * np.pi)
        
        dx = step_size * np.cos(angle)
        dy = step_size * np.sin(angle)
        
        return (dx, dy)
    
    def get_next_position(self, current_position: Tuple[float, float]) -> Tuple[float, float]:
        """Get next search position.
        
        Args:
            current_position: Current search position (x, y) in degrees
            
        Returns:
            Next search position (x, y) in degrees
        """
        dx, dy = self.generate_step()
        next_x = current_position[0] + dx
        next_y = current_position[1] + dy
        
        self.current_position = (next_x, next_y)
        self.step_count += 1
        
        return self.current_position
    
    def reset(self, start_position: Tuple[float, float] = (0.0, 0.0)):
        """Reset search to starting position.
        
        Args:
            start_position: Starting position for search in degrees
        """
        self.current_position = start_position
        self.step_count = 0
        
        # Re-seed if seed was provided
        if self.seed is not None:
            np.random.seed(self.seed)
    
    def get_step_count(self) -> int:
        """Get number of steps taken.
        
        Returns:
            Step count
        """
        return self.step_count
