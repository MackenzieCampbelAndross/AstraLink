"""Search controller for reacquisition strategies."""

from typing import Tuple, Optional
import numpy as np

from astra_link_tracking.reacquisition.predictor import TrajectoryPredictor
from astra_link_tracking.reacquisition.levy_search import LevySearch
from astra_link_tracking.reacquisition.raster_search import RasterSearch


class SearchController:
    """Controller for reacquisition search strategies."""
    
    def __init__(self, config: dict):
        """Initialize search controller with configuration.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
        
        # Initialize search strategies
        predictor_config = config.get("reacquisition", {}).get("predictor", {})
        self.predictor = TrajectoryPredictor(predictor_config)
        
        levy_config = config.get("reacquisition", {}).get("levy_search", {})
        self.levy_search = LevySearch(levy_config)
        
        raster_config = config.get("reacquisition", {}).get("raster_search", {})
        self.raster_search = RasterSearch(raster_config)
        
        # Search controller parameters
        controller_config = config.get("reacquisition", {}).get("search_controller", {})
        self.max_search_time = controller_config.get("max_search_time", 10.0)
        self.search_strategy = controller_config.get("search_strategy", "prediction")
        
        self.search_start_time = 0.0
        self.is_searching = False
    
    def start_search(
        self,
        position: Tuple[float, float],
        velocity: Tuple[float, float],
        covariance: np.ndarray,
        timestamp: float
    ) -> Tuple[float, float]:
        """Start search for lost beacon.
        
        Args:
            position: Last known position (x, y)
            velocity: Last known velocity (vx, vy)
            covariance: Position covariance matrix
            timestamp: Current timestamp
            
        Returns:
            (azimuth, elevation) first search command
        """
        # TODO: Implement full search controller logic
        # This is a stub that will be replaced with proper implementation
        
        self.search_start_time = timestamp
        self.is_searching = True
        
        if self.search_strategy == "prediction":
            # Use trajectory prediction
            region = self.predictor.get_search_region(position, velocity, covariance, 0.5)
            center = ((region[0][0] + region[1][0]) / 2, (region[0][1] + region[1][1]) / 2)
            self.raster_search.reset(center)
            return center
        elif self.search_strategy == "levy":
            # Use Lévy flight
            self.levy_search.reset(position)
            return position
        elif self.search_strategy == "raster":
            # Use raster search
            self.raster_search.reset(position)
            return position
        else:
            return position
    
    def get_next_search_point(self) -> Optional[Tuple[float, float]]:
        """Get next search point.
        
        Returns:
            Next search position (x, y), or None if search complete
        """
        # TODO: Implement search point selection logic
        # This is a stub that will be replaced with proper implementation
        
        if not self.is_searching:
            return None
        
        if self.search_strategy == "prediction" or self.search_strategy == "raster":
            return self.raster_search.get_next_position()
        elif self.search_strategy == "levy":
            return self.levy_search.get_next_position()
        else:
            return None
    
    def stop_search(self):
        """Stop current search."""
        self.is_searching = False
    
    def should_stop_search(self, timestamp: float) -> bool:
        """Check if search should be stopped based on time limit.
        
        Args:
            timestamp: Current timestamp
            
        Returns:
            True if search should stop
        """
        return timestamp - self.search_start_time > self.max_search_time
    
    def reset(self):
        """Reset search controller."""
        self.is_searching = False
        self.search_start_time = 0.0
