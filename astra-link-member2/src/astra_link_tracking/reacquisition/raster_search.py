"""Raster search strategy for reacquisition."""

from typing import Tuple, List
import numpy as np

from astra_link_tracking.models.config import ReacquisitionConfig


class RasterSearch:
    """Deterministic raster (grid) search strategy for systematic reacquisition.
    
    Implements a zigzag raster scan pattern that systematically covers
    the search region. This is a deterministic fallback when Lévy search
    fails to find the target.
    """
    
    def __init__(self, config: ReacquisitionConfig):
        """Initialize raster search with configuration.
        
        Args:
            config: Reacquisition configuration with raster parameters
        """
        self.config = config
        self.grid_spacing = config.raster_grid_spacing  # Grid spacing (degrees)
        self.search_radius = config.raster_search_radius  # Search radius (degrees)
        
        # Search state
        self.current_position: Tuple[float, float] = (0.0, 0.0)
        self.search_path: List[Tuple[float, float]] = []
        self.current_index = 0
    
    def generate_search_path(self, center: Tuple[float, float]) -> List[Tuple[float, float]]:
        """Generate deterministic raster search path centered at given position.
        
        The raster scan follows a zigzag pattern:
        - Move right across the row
        - Move down one row
        - Move left across the row
        - Repeat until entire region is covered
        
        Args:
            center: Center of search region (x, y) in degrees
            
        Returns:
            List of (x, y) positions to search in degrees
        """
        path = []
        cx, cy = center
        
        # Calculate grid bounds
        x_min = cx - self.search_radius
        x_max = cx + self.search_radius
        y_min = cy - self.search_radius
        y_max = cy + self.search_radius
        
        # Generate grid points
        y = y_min
        direction = 1  # 1 for right, -1 for left
        
        while y <= y_max:
            if direction == 1:
                # Scan left to right
                x = x_min
                while x <= x_max:
                    path.append((x, y))
                    x += self.grid_spacing
            else:
                # Scan right to left
                x = x_max
                while x >= x_min:
                    path.append((x, y))
                    x -= self.grid_spacing
            
            # Move to next row
            y += self.grid_spacing
            direction *= -1  # Reverse direction
        
        return path
    
    def get_next_position(self) -> Tuple[float, float]:
        """Get next search position from pre-generated path.
        
        Returns:
            Next search position (x, y) in degrees
        """
        if self.current_index < len(self.search_path):
            position = self.search_path[self.current_index]
            self.current_index += 1
            self.current_position = position
            return position
        else:
            # Return current position if path exhausted
            return self.current_position
    
    def reset(self, center: Tuple[float, float] = (0.0, 0.0)):
        """Reset search to new center.
        
        Args:
            center: Center of search region in degrees
        """
        self.search_path = self.generate_search_path(center)
        self.current_index = 0
        self.current_position = center
    
    def get_progress(self) -> float:
        """Get search progress.
        
        Returns:
            Progress as fraction of path completed (0.0 to 1.0)
        """
        if len(self.search_path) == 0:
            return 0.0
        return self.current_index / len(self.search_path)
    
    def is_complete(self) -> bool:
        """Check if search is complete.
        
        Returns:
            True if entire path has been searched
        """
        return self.current_index >= len(self.search_path)
