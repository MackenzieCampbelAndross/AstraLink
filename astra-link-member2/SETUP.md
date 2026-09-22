# Astra Link Member 2 - Setup and Usage Guide

## Installation

### Prerequisites
- Python 3.11 or higher
- Virtual environment (recommended)

### Setup Steps

1. **Navigate to the Member 2 directory:**
   ```bash
   cd astra-link-member2
   ```

2. **Create a virtual environment:**
   ```bash
   python3 -m venv venv
   ```

3. **Activate the virtual environment:**
   ```bash
   # On macOS/Linux:
   source venv/bin/activate
   
   # On Windows:
   venv\Scripts\activate
   ```

4. **Install the package in development mode:**
   ```bash
   pip install -e .
   ```

5. **Install development dependencies (for testing):**
   ```bash
   pip install pytest
   ```

## Running the System

### Headless Mode (Default)
Run the tracking simulation without visualization:
```bash
python -m astra_link_tracking.main --headless
```

### With Visualization
Run with visualization enabled:
```bash
python -m astra_link_tracking.main --visualize
```

### Custom Duration
Specify simulation duration:
```bash
python -m astra_link_tracking.main --headless --duration 30.0
```

### Custom Configuration
Use a custom configuration file:
```bash
python -m astra_link_tracking.main --config config/custom_config.json
```

## Running Tests

Run the complete test suite:
```bash
pytest tests/ -v
```

Run specific test files:
```bash
pytest tests/test_kalman.py -v
```

Run with coverage:
```bash
pytest tests/ --cov=src/astra_link_tracking --cov-report=html
```

## Examples

### Basic Tracking Example
Run the basic tracking example:
```bash
python examples/basic_tracking.py
```

### Using the Tracker Directly
```python
from astra_link_tracking.models.interfaces import DetectionResult
from astra_link_tracking.tracking.tracker import Tracker
import json

# Load configuration
with open("config/default_config.json", "r") as f:
    config = json.load(f)

# Create tracker
tracker = Tracker(config)

# Process detection
detection = DetectionResult(
    timestamp=1.0,
    centroid=(320.0, 240.0),
    confidence=0.95,
    frame_id=42
)

tracking_state, camera_command = tracker.update(detection)
```

### Closed-Loop Simulation
```python
from astra_link_tracking.simulation.closed_loop import ClosedLoopSimulation

sim = ClosedLoopSimulation("config/default_config.json")
results = sim.run(duration=60.0)

# Access results
metrics = results["metrics"]
tracking_states = results["tracking_states"]
camera_commands = results["camera_commands"]
```

## Configuration

The system is configured via `config/default_config.json`. Key sections:

### Tracking Parameters
- `coordinate_transform`: Pixel-to-world conversion parameters
- `kalman`: Kalman filter noise parameters
- `motion_consistency`: Motion anomaly detection thresholds
- `state_machine`: State machine timeouts and thresholds

### Control Parameters
- `pid`: PID controller gains for azimuth and elevation
- `feedforward`: Feedforward control gains
- `slew_limit`: Slew rate and acceleration limits

### Reacquisition Parameters
- `predictor`: Trajectory prediction parameters
- `levy_search`: Lévy flight search parameters
- `raster_search`: Raster search parameters
- `search_controller`: Search strategy selection

### Metrics Parameters
- `position_error_threshold`: Threshold for position error
- `stability_window`: Window size for stability calculation
- `latency_smoothing`: Smoothing factor for latency measurement

### Simulation Parameters
- `trajectory_type`: Type of synthetic trajectory (figure8, circle, linear)
- `duration`: Simulation duration
- `dt`: Time step
- `noise_level`: Noise level for trajectory generation

## Architecture

### Module Structure
```
src/astra_link_tracking/
├── models/          # Data interfaces (DetectionResult, CameraCommand, etc.)
├── tracking/        # Tracking algorithms (Kalman, coordinate transforms, etc.)
├── control/         # Control algorithms (PID, feedforward, slew limiting)
├── reacquisition/   # Reacquisition strategies (prediction, Lévy, raster)
├── metrics/         # Performance metrics calculation
├── simulation/      # Simulation utilities (trajectories, dummy detection)
└── visualization/  # Debug visualization
```

### Interfaces
- **Input from Member 1:** `DetectionResult` (beacon detections)
- **Output to Member 1:** `CameraCommand` (camera control)
- **Output to Member 3:** `TrackingState` (security/trust), `TrackingMetrics` (performance)

## Current Implementation Status

### ✅ Completed (Architecture & Stubs)
- Complete directory structure
- All data interfaces defined
- All module stubs implemented
- Configuration system
- Test suite (55 tests, all passing)
- Basic examples
- Main entry point

### 🔜 To Be Implemented (Sophisticated Algorithms)
- **Coordinate Transform:** Proper camera models and coordinate systems
- **Kalman Filter:** Full state transition and measurement matrices
- **Motion Consistency:** Physics-based anomaly detection
- **State Machine:** Complete state transition logic
- **PID Control:** Full implementation with anti-windup
- **Feedforward:** Model-based feedforward control
- **Slew Limiting:** Acceleration-aware slew limiting
- **Trajectory Prediction:** Advanced prediction algorithms
- **Lévy Search:** Proper Lévy distribution sampling
- **Raster Search:** Optimal raster patterns
- **Metrics:** Full metric computation
- **Visualization:** Real-time plotting with matplotlib

## Troubleshooting

### Import Errors
If you encounter import errors, ensure:
1. The virtual environment is activated
2. The package is installed in development mode: `pip install -e .`
3. You're running from the correct directory

### Test Failures
If tests fail:
1. Ensure all dependencies are installed: `pip install -e .`
2. Check Python version: `python --version` (should be 3.11+)
3. Run tests in verbose mode: `pytest tests/ -v`

### Configuration Issues
If configuration loading fails:
1. Check that `config/default_config.json` exists
2. Validate JSON syntax: `python -m json.tool config/default_config.json`
3. Ensure all required keys are present

## Next Steps

1. Implement sophisticated tracking algorithms in each module
2. Add integration tests with Member 1 (when available)
3. Implement real-time visualization
4. Add MP4 benchmark support
5. Optimize performance for real-time operation
