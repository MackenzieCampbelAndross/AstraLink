"""Tests for velocity feedforward controller."""

import pytest

from astra_link_tracking.control.feedforward import VelocityFeedforward


class TestVelocityFeedforward:
    """Test suite for velocity feedforward controller."""
    
    @pytest.fixture
    def feedforward(self):
        """Create a velocity feedforward controller instance."""
        return VelocityFeedforward(gain=0.5)
    
    def test_initialization(self, feedforward):
        """Test feedforward controller initialization."""
        assert feedforward.gain == 0.5
    
    def test_compute(self, feedforward):
        """Test feedforward computation."""
        velocity_x = 1.0
        velocity_y = 2.0
        
        ff_x, ff_y = feedforward.compute(velocity_x, velocity_y)
        
        assert isinstance(ff_x, float)
        assert isinstance(ff_y, float)
        # With positive velocity and gain, output should be positive
        assert ff_x == 0.5  # 1.0 * 0.5
        assert ff_y == 1.0  # 2.0 * 0.5
    
    def test_zero_velocity(self, feedforward):
        """Test with zero velocity."""
        ff_x, ff_y = feedforward.compute(0.0, 0.0)
        
        assert ff_x == 0.0
        assert ff_y == 0.0
    
    def test_negative_velocity(self, feedforward):
        """Test with negative velocity."""
        ff_x, ff_y = feedforward.compute(-1.0, -2.0)
        
        assert ff_x == -0.5
        assert ff_y == -1.0
    
    def test_mixed_velocity(self, feedforward):
        """Test with mixed positive/negative velocity."""
        ff_x, ff_y = feedforward.compute(1.0, -2.0)
        
        assert ff_x == 0.5
        assert ff_y == -1.0
    
    def test_set_gain(self, feedforward):
        """Test setting gain."""
        feedforward.set_gain(1.0)
        
        assert feedforward.gain == 1.0
        
        # Verify computation uses new gain
        ff_x, ff_y = feedforward.compute(1.0, 2.0)
        assert ff_x == 1.0
        assert ff_y == 2.0
    
    def test_get_gain(self, feedforward):
        """Test getting gain."""
        gain = feedforward.get_gain()
        
        assert gain == 0.5
        assert gain == feedforward.gain
    
    def test_zero_gain(self):
        """Test with zero gain."""
        feedforward = VelocityFeedforward(gain=0.0)
        
        ff_x, ff_y = feedforward.compute(1.0, 2.0)
        
        assert ff_x == 0.0
        assert ff_y == 0.0
    
    def test_high_gain(self):
        """Test with high gain."""
        feedforward = VelocityFeedforward(gain=2.0)
        
        ff_x, ff_y = feedforward.compute(1.0, 2.0)
        
        assert ff_x == 2.0
        assert ff_y == 4.0
