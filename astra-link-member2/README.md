# Astra Link - Member 2: Tracking + State Estimation + Motion Consistency + Control + Reacquisition + Tracking Metrics

## Overview

This module implements the tracking, state estimation, motion consistency checking, control, reacquisition, and tracking metrics components for the Astra Link FSOC coarse-alignment simulation system.

## Scope

Member 2 is responsible for:
- **Tracking**: Coordinate transformations, Kalman filtering, tracker state management
- **State Estimation**: Kalman filter-based state estimation
- **Motion Consistency**: Detecting anomalies in beacon motion
- **Control**: PID control, feedforward control, slew limiting
- **Reacquisition**: Prediction-based search, Lévy flight search, raster search
- **Tracking Metrics**: Position error, stability, latency metrics

Member 2 does NOT own:
- Virtual environment generation (Member 1)
- Moving target/beacon generation (Member 1)
- Virtual camera image generation (Member 1)
- Disturbances/noise (Member 1)
- Beacon detection (Member 1)
- Security/authentication/trust/communication (Member 3)

## Installation

```bash
cd astra-link-member2
pip install -e .
```

## Configuration

Edit `config/default_config.json` to adjust tracking parameters.

## Running

### Headless Mode (Default)
```bash
python -m astra_link_tracking.main --headless
```

### Visualization Mode
```bash
python -m astra_link_tracking.main --visualize
```

### With Specific Configuration
```bash
python -m astra_link_tracking.main --config config/custom_config.json
```

## Testing

```bash
pytest tests/
```

## Examples

See the `examples/` directory for usage examples.

## Interface

See `INTERFACE.md` for detailed interface specifications with Member 1 and Member 3.
