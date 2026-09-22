# ASTRA LINK — Simulation Engine

A high-performance, deterministic 3D simulation engine built in TypeScript and Three.js for the coarse alignment of mobile Free-Space Optical Communication (FSOC) terminals.

ASTRA LINK provides a clean, reproducible simulation environment featuring two terminals:
- **Terminal 1 (Reference Station)**: A stationary optical ground terminal with optical aperture and targeting alignment.
- **Terminal 2 (Remote Mobile Target)**: A mobile terminal navigating 3D space with attached **Optical Beacon**, multiple parametric/stochastic motion profiles, and high-frequency ground truth telemetry generation.

---

## Architecture & Data Flow

The simulation core is strictly decoupled from the Three.js visualization pipeline. The simulation engine can run in completely headless environments (such as Node.js, Web Workers, or CI test runners) without any DOM or GPU dependencies.

```text
               +-------------------------------------+
               ¦         Simulation Config           ¦
               +-------------------------------------+
                                  ¦
               +------------------?------------------+
               ¦    Simulation Clock (Fixed dt)      ¦
               ¦    Seeded Random Generator (RNG)    ¦
               +-------------------------------------+
                                  ¦
               +------------------?------------------+
               ¦            Motion Model             ¦
               ¦  (Straight, Circular, Fig8, Random) ¦
               +-------------------------------------+
                                  ¦
               +------------------?------------------+
               ¦         Target Kinematics           ¦
               ¦   (Position, Velocity, Accel, Yaw)  ¦
               +-------------------------------------+
                                  ¦
               +------------------?------------------+
               ¦          Optical Beacon             ¦
               ¦  (Local Offset transformed to World)¦
               +-------------------------------------+
                                  ¦
               +------------------?------------------+
               ¦       Ground Truth Telemetry        ¦
               ¦  (Independent of Rendered Pixels)   ¦
               +-------------------------------------+
                                  ¦
        +---------------------------------------------------+
        ¦                                                   ¦
+-------?--------------------------+      +-----------------?-----------------+
¦     Simulation API / State       ¦      ¦       Three.js Visualization      ¦
¦ (Consumed by downstream modules) ¦      ¦ (World, Terminals, Beacon, Trail) ¦
+----------------------------------+      +-----------------------------------+
```

### Deterministic Update Sequence

Every simulation step executes in a deterministic order:
1. **Advance Simulation Clock**: Fixed $\Delta t$ increment ($t = \text{frameId} \times \Delta t$).
2. **Update Target Motion**: Step analytical or integrated motion equations.
3. **Update Target Position & Velocity**: Bounded by world dimensions and reflection boundaries.
4. **Update Target Orientation**: Velocity-aligned heading vectors.
5. **Update Beacon World Position**: Target position rotated by target orientation + local offset.
6. **Generate Ground Truth**: Produces an immutable telemetry record for evaluation.
7. **Update Visualization**: Visual objects mirror simulation state without altering physics.

---

## Installation

Ensure [Node.js](https://nodejs.org/) (v18+) is installed.

```bash
npm install
```

---

## Development

To start the Vite development server with hot module reloading:

```bash
npm run dev
```

Open `http://localhost:5173/` in your browser.

---

## Testing

Run the Vitest test suite covering the simulation clock, seeded RNG, analytical motion models, beacon kinematics, and 300-frame bit-exact determinism:

```bash
npm test
```

To run tests in watch mode:

```bash
npm run test:watch
```

---

## Production Build

To verify TypeScript types and bundle the application:

```bash
npm run build
```

---

## Supported Motion Models

| Motion Model | Description | Kinematic Formulation |
| :--- | :--- | :--- |
| **Straight** | Uniform linear motion with world boundary bounce/clamp | $\mathbf{r}(t) = \mathbf{r}_0 + \mathbf{v} \cdot t$ |
| **Circular** | Smooth orbital movement in 3D planes (XZ, XY, YZ) | $x = C_x + R\cos(\omega t + \phi)$, $z = C_z + R\sin(\omega t + \phi)$, centripetal $\mathbf{a} = -\omega^2 (\mathbf{r} - \mathbf{C})$ |
| **Figure-8** | Continuous Lissajous / Lemniscate parametric curve | $x = C_x + A_x\sin(\omega t)$, $z = C_z + A_z\sin(2\omega t)$ |
| **Random** | Smooth stochastic random walk without teleportation | Integrated Gaussian acceleration with damping, velocity limits, and world boundary bouncing |

---

## Configuration

The simulation is fully configurable via JSON files located in `config/`:
- `config/default.json`
- `config/straight.json`
- `config/circular.json`
- `config/figure8.json`
- `config/random.json`

### Example Configuration:

```json
{
  "seed": 42,
  "simulation": {
    "duration_s": 30,
    "dt": 0.0333333333
  },
  "world": {
    "width": 2000,
    "height": 1000,
    "depth": 2000,
    "boundary_behavior": "bounce"
  },
  "terminals": {
    "terminal1": {
      "position": { "x": 0, "y": 0, "z": 0 }
    },
    "terminal2": {
      "position": { "x": 300, "y": 50, "z": -300 }
    }
  },
  "target": {
    "motion": "circular",
    "size": { "x": 2, "y": 2, "z": 2 },
    "circular": {
      "center": { "x": 0, "y": 50, "z": -300 },
      "radius": 300,
      "angular_velocity": 0.4,
      "plane": "XZ",
      "initial_phase": 0
    }
  },
  "beacon": {
    "enabled": true,
    "brightness": 1.0,
    "size": 4,
    "localPosition": { "x": 0, "y": 1.2, "z": 0 }
  },
  "visualization": {
    "showTrajectory": true,
    "trajectoryLength": 600
  }
}
```

Configuration is validated prior to simulation initialization. Clear errors are thrown for non-positive timesteps, negative radii, or missing coordinates.

---

## Seeded Determinism

The simulation guarantees bit-exact repeatability:
- All stochastic behaviors utilize `SeededRandom` (Mulberry32).
- Zero calls to `Math.random()` in the simulation engine.
- A simulation initialized with `seed = 42` produces the exact same trajectory, velocity, beacon position, and ground truth across repeated runs.
- Tested and verified in `tests/Determinism.test.ts`.

---

## Public Simulation API

The engine exposes a clean, typed interface (`SimulationAPI`):

```typescript
import { SimulationEngine } from "./src/simulation/SimulationEngine";
import { DEFAULT_CONFIG } from "./src/config";

const engine = new SimulationEngine(DEFAULT_CONFIG);

// Advance by one fixed timestep dt
engine.step();

// Access ground truth telemetry (never derived from pixels)
const gt = engine.getGroundTruth();
console.log(`Time: ${gt.timestamp}s, Target: (${gt.targetPosition.x}, ${gt.targetPosition.y}, ${gt.targetPosition.z})`);
console.log(`Beacon: (${gt.beaconPosition.x}, ${gt.beaconPosition.y}, ${gt.beaconPosition.z})`);

// Switch motion dynamically
engine.switchMotion("figure8");

// Reset back to t = 0
engine.reset();
```

---

## Scope & Module Boundaries

In adherence to the ASTRA LINK modular specification, this repository implements **ONLY THE SIMULATION PART**.

This module **DOES NOT** implement and intentionally excludes:
- Optical beacon vision detector / CNN / YOLO / Heatmaps
- Kalman filters or tracking estimators
- PID controllers or gimbal servo controllers
- Authentication protocols or key exchange
- Cryptographic ciphers
- Network communication protocols, ARQ, or ACK loops
- Link failure reacquisition logic
- Downstream AI models

Downstream modules consume the 3D scene via virtual camera capture or consume ground truth telemetry for tracking benchmark evaluation.
