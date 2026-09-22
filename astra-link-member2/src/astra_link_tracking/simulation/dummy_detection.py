"""Dummy detection generator for testing."""

from typing import Tuple, List, Optional
import numpy as np

from astra_link_tracking.models.interfaces import DetectionResult, GroundTruthState


class DummyDetectionGenerator:
    """Generates dummy detection results for testing."""
    
    def __init__(self, config: dict):
        """Initialize dummy detection generator with configuration.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.drop_probability = 0.0  # Probability of dropping a detection
        self.noise_std = 1.0  # Detection noise standard deviation
    
    def generate_detections(
        self,
        trajectory: List[Tuple[float, Tuple[float, float], Tuple[float, float]]]
    ) -> List[DetectionResult]:
        """Generate detection results from trajectory.
        
        Args:
            trajectory: List of (timestamp, position, velocity) tuples
            
        Returns:
            List of DetectionResult objects
        """
        # TODO: Implement detection generation with drops and noise
        # This is a stub that will be replaced with proper implementation
        
        detections = []
        for i, (timestamp, position, velocity) in enumerate(trajectory):
            # Randomly drop some detections
            if np.random.random() < self.drop_probability:
                continue
            
            # Add noise to position
            noisy_x = position[0] + np.random.normal(0, self.noise_std)
            noisy_y = position[1] + np.random.normal(0, self.noise_std)
            
            # Convert to pixel coordinates (simplified)
            centroid = (noisy_x * 1000 + 320, noisy_y * 1000 + 240)
            
            detection = DetectionResult(
                timestamp=timestamp,
                centroid=centroid,
                confidence=0.9 + np.random.uniform(-0.1, 0.1),
                frame_id=i
            )
            detections.append(detection)
        
        return detections
    
    def generate_ground_truth(
        self,
        trajectory: List[Tuple[float, Tuple[float, float], Tuple[float, float]]]
    ) -> List[GroundTruthState]:
        """Generate ground truth states from trajectory.
        
        Args:
            trajectory: List of (timestamp, position, velocity) tuples
            
        Returns:
            List of GroundTruthState objects
        """
        ground_truths = []
        for timestamp, position, velocity in trajectory:
            gt = GroundTruthState(
                timestamp=timestamp,
                position=position,
                velocity=velocity
            )
            ground_truths.append(gt)
        
        return ground_truths
