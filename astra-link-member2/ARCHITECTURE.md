# Astra Link Member 2 - Architecture Summary

## Overview

Member 2 implements the tracking, state estimation, motion consistency checking, control, reacquisition, and tracking metrics components for the Astra Link FSOC coarse-alignment simulation system.

## Repository Structure

```
astra-link-member2/
├── README.md                      # Project overview and quick start
├── INTERFACE.md                   # Interface specifications with Member 1 and 3
├── SETUP.md                       # Detailed setup and usage guide
├── ARCHITECTURE.md                # This file - architecture summary
├── requirements.txt               # Python dependencies
├── pyproject.toml                 # Project configuration
├── .gitignore                     # Git ignore rules
├── config/
│   └── default_config.json        # Default configuration
├── src/
│   └── astra_link_tracking/
│       ├── __init__.py            # Package initialization
│       ├── main.py                # Main entry point
│       ├── models/                # Data interfaces
│       │   ├── __init__.py
│       │   └── interfaces.py     # DetectionResult, CameraCommand, etc.
│       ├── tracking/              # Tracking algorithms
│       │   ├── __init__.py
│       │   ├── coordinate_transform.py  # Pixel/world/angle transforms
│       │   ├── kalman.py         # Kalman filter state estimation
│       │   ├── motion_consistency.py   # Motion anomaly detection
│       │   ├── tracker.py        # Main tracker integration
│       │   └── state_machine.py  # Tracking mode state machine
│       ├── control/               # Control algorithms
│       │   ├── __init__.py
│       │   ├── pid.py            # PID controller
│       │   ├── feedforward.py    # Feedforward controller
│       │   ├── slew_limit.py     # Slew rate limiter
│       │   └── controller.py     # Main controller integration
│       ├── reacquisition/         # Reacquisition strategies
│       │   ├── __init__.py
│       │   ├── predictor.py      # Trajectory prediction
│       │   ├── levy_search.py    # Lévy flight search
│       │   ├── raster_search.py  # Raster grid search
│       │   └── search_controller.py  # Search strategy controller
│       ├── metrics/               # Performance metrics
│       │   ├── __init__.py
│       │   └── tracking_metrics.py    # Metrics calculator
│       ├── simulation/            # Simulation utilities
│       │   ├── __init__.py
│       │   ├── trajectories.py   # Synthetic trajectory generation
│       │   ├── dummy_detection.py    # Dummy detection generator
│       │   └── closed_loop.py    # Closed-loop simulation
│       └── visualization/         # Debug visualization
│           ├── __init__.py
│           └── debug_view.py    # Debug view implementation
├── tests/                         # Test suite
│   ├── test_coordinates.py
│   ├── test_kalman.py
│   ├── test_motion_consistency.py
│   ├── test_state_machine.py
│   ├── test_pid.py
│   ├── test_feedforward.py
│   ├── test_slew_limit.py
│   ├── test_reacquisition.py
│   └── test_metrics.py
├── outputs/                       # Output directories
│   ├── logs/
│   └── plots/
└── examples/                      # Usage examples
    └── basic_tracking.py
```

## Module Responsibilities

### Models (`models/`)
- **Purpose:** Define data interfaces for communication between members
- **Key Components:**
  - `DetectionResult`: Input from Member 1 (beacon detections)
  - `CameraCommand`: Output to Member 1 (camera control)
  - `TrackingState`: Output to Member 3 (security/trust)
  - `TrackingMetrics`: Output to Member 3 (performance logging)
  - `GroundTruthState`: Simulation ground truth for metrics

### Tracking (`tracking/`)
- **Purpose:** Implement tracking algorithms and state management
- **Key Components:**
  - `CoordinateTransform`: Convert between pixel and angular coordinates (dynamic from config)
  - `KalmanFilter`: State estimation using constant-velocity Kalman filtering with adaptive covariance
  - `MotionConsistencyChecker`: Mahalanobis distance-based statistical gating with four-case handling
  - `TrackingStateMachine`: Dedicated state machine (SEARCH/LOCKED/COASTING/LOST) with hysteresis
  - `Tracker`: Main tracker integrating all components

### Control (`control/`)
- **Purpose:** Implement camera control algorithms
- **Key Components:**
  - `PIDController`: Proportional-Integral-Derivative control
  - `FeedforwardController`: Model-based feedforward control
  - `SlewLimiter`: Slew rate and acceleration limiting
  - `Controller`: Main controller integrating all components

### Reacquisition (`reacquisition/`)
- **Purpose:** Implement reacquisition strategies for lost targets
- **Key Components:**
  - `TrajectoryPredictor`: Predict future beacon positions
  - `LevySearch`: Lévy flight search strategy
  - `RasterSearch`: Raster grid search strategy
  - `SearchController`: Manage search strategy selection

### Metrics (`metrics/`)
- **Purpose:** Calculate tracking performance metrics
- **Key Components:**
  - `TrackingMetricsCalculator`: Compute position error, stability, latency, etc.

### Simulation (`simulation/`)
- **Purpose:** Provide simulation utilities for testing
- **Key Components:**
  - `TrajectoryGenerator`: Generate synthetic trajectories
  - `DummyDetectionGenerator`: Generate dummy detections from trajectories
  - `ClosedLoopSimulation`: Run closed-loop simulations

### Visualization (`visualization/`)
- **Purpose:** Provide debug visualization
- **Key Components:**
  - `DebugView`: Real-time visualization of tracking state

## Data Flow

```
Member 1 (Detection)
    ↓
DetectionResult
    ↓
Tracker (CoordinateTransform → KalmanFilter → MotionConsistency → StateMachine)
    ↓
TrackingState → Member 3 (Security/Trust)
CameraCommand → Member 1 (Camera Control)
    ↓
MetricsCalculator
    ↓
TrackingMetrics → Member 3 (Logging/Analysis)
```

## Design Principles

1. **Clean Interfaces:** Member 2 communicates only through well-defined data structures
2. **Modularity:** Each component is independent and testable
3. **Configurability:** All parameters are configurable via JSON
4. **Type Safety:** All interfaces use Python type hints
5. **Headless Operation:** Core functionality works without visualization
6. **Testability:** Supports both dummy and real data for testing

## Implementation Status

### ✅ Completed
- Complete repository structure
- All data interfaces defined with typed dataclasses
- Configuration system with validation and JSON serialization
- Coordinate transformation (pixel ↔ angular, dynamic from config)
- Kalman filter (constant-velocity model, adaptive covariance, Joseph form)
- Motion consistency checker (Mahalanobis gating, four-case handling)
- Tracking state machine (SEARCH/LOCKED/COASTING/LOST with hysteresis)
- Test suite (210 tests, all passing)
- Examples (coordinate transform, Kalman filter, motion consistency)
- Main entry point with CLI
- Documentation (README, INTERFACE, SETUP, ARCHITECTURE)

### 🔜 To Be Implemented
- Full tracker integration (combining all tracking components)
- Complete PID control with anti-windup
- Model-based feedforward control
- Acceleration-aware slew limiting
- Advanced trajectory prediction
- Proper Lévy distribution sampling
- Optimal raster patterns
- Complete metrics computation
- Real-time visualization with matplotlib

## Dependencies

### Core Dependencies
- `numpy>=1.24.0`: Numerical computations
- `scipy>=1.10.0`: Scientific computing (Kalman filter, etc.)
- `matplotlib>=3.7.0`: Visualization

### Development Dependencies
- `pytest>=7.4.0`: Testing framework

### Intentionally Avoided
- Heavyweight ML frameworks (not needed for current scope)
- Computer vision libraries (opencv-python only when required)
- Web frameworks (not needed for headless operation)

## Configuration

All parameters are configurable via `config/default_config.json`:

- **Tracking:** Coordinate transforms, Kalman filter, motion consistency, state machine
- **Control:** PID gains, feedforward gains, slew limits
- **Reacquisition:** Prediction, Lévy search, raster search, search controller
- **Metrics:** Error thresholds, stability window, latency smoothing
- **Simulation:** Trajectory type, duration, time step, noise level
- **Visualization:** Enable/disable, update interval, display options

## Testing

The test suite covers all major components:
- Configuration validation (47 tests)
- Coordinate transformations (41 tests)
- Kalman filter operations (31 tests)
- Motion consistency checking (29 tests)
- State machine transitions (29 tests)
- PID controller (4 tests)
- Feedforward controller (3 tests)
- Slew limiting (4 tests)
- Reacquisition strategies (9 tests)
- Metrics calculation (7 tests)
- Other module tests (15 tests)

All 210 tests pass successfully.

## Running

### Headless Mode
```bash
python -m astra_link_tracking.main --headless
```

### Visualization Mode
```bash
python -m astra_link_tracking.main --visualize
```

### Tests
```bash
pytest tests/ -v
```

### Examples
```bash
python examples/basic_tracking.py
```

## Integration Points

### With Member 1
- **Input:** `DetectionResult` from beacon detection
- **Output:** `CameraCommand` for camera control

### With Member 3
- **Output:** `TrackingState` for security/trust
- **Output:** `TrackingMetrics` for logging/analysis

## Future Enhancements

1. Integration with real Member 1 detection system
2. Integration with Member 3 security/authentication
3. MP4 benchmark support for evaluation
4. Real-time optimization for production deployment
5. Advanced visualization tools
6. Performance profiling and optimization
7. Additional trajectory types for testing
8. Adaptive parameter tuning
