"""Tests for independent slew rate limiters."""

import pytest

from astra_link_tracking.control.slew_limit import SlewLimiter, SlewLimiterPair


class TestSlewLimiter:
    """Test suite for single-axis slew limiter."""
    
    @pytest.fixture
    def slew_limiter(self):
        """Create a slew limiter instance."""
        return SlewLimiter(max_rate_deg_per_sec=5.0)
    
    def test_initialization(self, slew_limiter):
        """Test slew limiter initialization."""
        assert slew_limiter.max_rate == 5.0
        assert slew_limiter.last_position == 0.0
        assert slew_limiter.initialized is False
    
    def test_first_update(self, slew_limiter):
        """Test first update initializes position."""
        desired = 10.0
        dt = 0.1
        
        limited, rate = slew_limiter.limit(desired, dt)
        
        # First update should initialize to desired position
        assert limited == desired
        assert rate == 0.0
        assert slew_limiter.initialized is True
    
    def test_rate_limiting(self, slew_limiter):
        """Test that rates are limited."""
        # Initialize
        slew_limiter.limit(0.0, 0.1)
        
        # Try to move very fast (100 degrees in 0.1s = 1000 deg/s)
        desired = 100.0
        dt = 0.1
        
        limited, rate = slew_limiter.limit(desired, dt)
        
        # Rate should be limited to max_rate
        assert abs(rate) <= slew_limiter.max_rate
        assert rate == slew_limiter.max_rate
    
    def test_within_limits(self, slew_limiter):
        """Test movement within limits."""
        # Initialize
        slew_limiter.limit(0.0, 0.1)
        
        # Move within limits (0.5 degrees in 0.1s = 5 deg/s)
        desired = 0.5
        dt = 0.1
        
        limited, rate = slew_limiter.limit(desired, dt)
        
        # Should not be limited
        assert limited == desired
        assert rate == 5.0
    
    def test_negative_direction(self, slew_limiter):
        """Test negative direction movement."""
        # Initialize
        slew_limiter.limit(10.0, 0.1)
        
        # Move negative
        desired = 0.0
        dt = 0.1
        
        limited, rate = slew_limiter.limit(desired, dt)
        
        # Rate should be negative
        assert rate < 0
        assert abs(rate) <= slew_limiter.max_rate
    
    def test_reset(self, slew_limiter):
        """Test slew limiter reset."""
        slew_limiter.limit(10.0, 0.1)
        slew_limiter.reset()
        
        assert slew_limiter.last_position == 0.0
        assert slew_limiter.initialized is False
    
    def test_reset_with_initial_position(self, slew_limiter):
        """Test reset with initial position."""
        slew_limiter.reset(initial_position=5.0)
        
        assert slew_limiter.last_position == 5.0
        assert slew_limiter.initialized is False
    
    def test_zero_dt_protection(self, slew_limiter):
        """Test that zero dt raises error."""
        slew_limiter.limit(0.0, 0.1)
        
        with pytest.raises(ValueError, match="dt must be positive"):
            slew_limiter.limit(10.0, 0.0)
    
    def test_negative_dt_protection(self, slew_limiter):
        """Test that negative dt raises error."""
        slew_limiter.limit(0.0, 0.1)
        
        with pytest.raises(ValueError, match="dt must be positive"):
            slew_limiter.limit(10.0, -0.1)


class TestSlewLimiterPair:
    """Test suite for independent slew limiter pair."""
    
    @pytest.fixture
    def slew_limiter_pair(self):
        """Create a slew limiter pair instance."""
        return SlewLimiterPair(max_pan_speed_deg_per_sec=5.0, max_tilt_speed_deg_per_sec=3.0)
    
    def test_initialization(self, slew_limiter_pair):
        """Test slew limiter pair initialization."""
        assert slew_limiter_pair.pan_limiter.max_rate == 5.0
        assert slew_limiter_pair.tilt_limiter.max_rate == 3.0
    
    def test_independent_limits(self, slew_limiter_pair):
        """Test that pan and tilt have independent limits."""
        # Initialize
        slew_limiter_pair.limit(0.0, 0.0, 0.1)
        
        # Try to move both axes very fast
        desired_pan = 100.0
        desired_tilt = 100.0
        dt = 0.1
        
        limited_pan, limited_tilt, (pan_rate, tilt_rate) = slew_limiter_pair.limit(
            desired_pan, desired_tilt, dt
        )
        
        # Each axis should be limited to its own max rate
        assert abs(pan_rate) == 5.0
        assert abs(tilt_rate) == 3.0
    
    def test_one_axis_saturated(self, slew_limiter_pair):
        """Test when only one axis is saturated."""
        # Initialize
        slew_limiter_pair.limit(0.0, 0.0, 0.1)
        
        # Pan fast, tilt slow (within tilt limit)
        desired_pan = 100.0
        desired_tilt = 0.3  # 0.3 / 0.1 = 3 deg/s, at tilt limit of 3.0
        dt = 0.1
        
        limited_pan, limited_tilt, (pan_rate, tilt_rate) = slew_limiter_pair.limit(
            desired_pan, desired_tilt, dt
        )
        
        # Pan should be limited
        assert abs(pan_rate) == 5.0
        # Tilt should be at its limit (not below)
        assert abs(abs(tilt_rate) - 3.0) < 1e-6
    
    def test_reset(self, slew_limiter_pair):
        """Test slew limiter pair reset."""
        slew_limiter_pair.limit(10.0, 5.0, 0.1)
        slew_limiter_pair.reset()
        
        assert slew_limiter_pair.pan_limiter.last_position == 0.0
        assert slew_limiter_pair.tilt_limiter.last_position == 0.0
    
    def test_reset_with_initial_positions(self, slew_limiter_pair):
        """Test reset with initial positions."""
        slew_limiter_pair.reset(initial_pan=5.0, initial_tilt=3.0)
        
        assert slew_limiter_pair.pan_limiter.last_position == 5.0
        assert slew_limiter_pair.tilt_limiter.last_position == 3.0
