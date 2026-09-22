# ASTRA LINK — Simulation Engine

A high-performance, deterministic 3D simulation engine built in **TypeScript** and **Three.js** for coarse alignment and beam tracking of mobile Free-Space Optical Communication (FSOC) terminals.

The application renders in **Camera POV Format** from the optical transceiver gimbal of a tactical patrol aircraft (**UAV 1**), executing an autonomous **5–10 second electro-optical raster search** across 3D airspace before detecting, slewing, and locking onto the optical beacon of a mobile receiver aircraft (**UAV 2**).

---

## Key Features

- **Transmitter Camera POV**: Primary viewport is situated directly within the optical transceiver turret of UAV 1 with an unobstructed $360^\circ$ field of regard and zero mesh clipping.
- **FLIR / Electro-Optical Targeting HUD**:
  - Center mil-dot optical boresight crosshairs & sensor acquisition gate
  - Real-time 3D-to-2D screen-projected tactical tracking box mathematically centered on the target drone
  - Heading compass ribbon ($000^\circ$–$360^\circ$)
  - Beacon carrier signal strength (RSSI) meter
  - Azimuth/elevation gimbal angles, target range, and pointing error (mrad)
  - Optical zoom ($1\times$, $2\times$, $4\times$, $8\times$)
- **Realistic Atmospheric Sky & Aerial Environment**:
  - Three.js physical `Sky` shader with Rayleigh and Mie scattering calibrated for daylight flight
  - Natural earth/olive terrain with subtle altitude grid lines and atmospheric haze
  - Layered drifting cloud deck providing authentic flight speed cues
- **Dual-UAV Aerodynamic Flight Kinematics**:
  - Procedural tactical fixed-wing UAV models (aerodynamic fuselage, high-aspect wings with ailerons, inverted V-tail, spinning pusher propeller, optical turret pod, strobe lights)
  - Coordinated banking physics ($\phi = -\arctan(\frac{v \cdot \dot{\psi}}{g})$) into turns
  - UAV 1 flies a continuous reconnaissance patrol circuit at $180\text{ m}$ altitude
  - UAV 2 flies configurable trajectories (Circle, Figure-8, Straight, Evasive Random)
- **Authentic 5–10s Raster Search & Lock**:
  - Gimbal performs smooth horizontal raster sweeps across the airspace
  - Spends ~5 to 8.5 seconds sweeping sectors before intercepting the target beacon
  - Upon acquisition, closed-loop servo controller slews camera to center the beacon into the crosshairs
  - Snaps into `BEACON LOCKED` once error $< 0.5^\circ$ ($8.7\text{ mrad}$)
  - High-bandwidth optical communication laser carrier beam activates

---

## Project Structure

```text
AstraLink/
├── .github/
│   └── workflows/
│       └── ci.yml             # GitHub Actions automated test & build CI
├── config/                    # JSON scenario configs
│   ├── default.json
│   ├── straight.json
│   ├── circular.json
│   ├── figure8.json
│   └── random.json
├── src/
│   ├── main.ts                # Application entrypoint & HUD event coordinator
│   ├── simulator.ts           # Simulator runner & 3D render loop
│   ├── types.ts               # Pure mathematical types & telemetry contracts
│   ├── config.ts              # Configuration validator & presets
│   ├── beacon/
│   │   └── OpticalBeacon.ts   # Optical beacon model & 3D transform
│   ├── entities/
│   │   └── UAVModel.ts        # Procedural 3D aerospace UAV model
│   ├── rendering/
│   │   ├── SceneManager.ts    # Three.js WebGL scene, lighting, and fog
│   │   ├── AtmosphereRenderer.ts # Physical Sky shader, terrain & clouds
│   │   ├── CameraManager.ts   # Camera perspectives & 3D-to-2D screen projection
│   │   ├── DualUAVRenderer.ts # Dual UAV rendering & optical laser beam
│   │   └── DebugRenderer.ts   # Trajectory trail visualizer
│   └── simulation/
│       ├── SimulationEngine.ts # Master headless simulation coordinator
│       ├── SimulationClock.ts  # Deterministic fixed-dt clock (1/30s)
│       ├── SeededRandom.ts     # Mulberry32 PRNG (zero Math.random in physics)
│       ├── GroundTruth.ts      # Immutable ground truth telemetry generator
│       ├── flight/
│       │   └── FlightKinematics.ts # Aerodynamic flight & coordinated banking
│       ├── gimbal/
│       │   └── GimbalController.ts # 5-10s raster search & optical lock servo
│       └── motion/
│           ├── MotionModel.ts
│           ├── StraightMotion.ts
│           ├── CircularMotion.ts
│           ├── Figure8Motion.ts
│           └── RandomMotion.ts
├── tests/                     # Vitest test suite (32 tests)
│   ├── Beacon.test.ts
│   ├── CircularMotion.test.ts
│   ├── Determinism.test.ts
│   ├── Figure8Motion.test.ts
│   ├── GimbalAndFlight.test.ts
│   ├── RandomMotion.test.ts
│   ├── SeededRandom.test.ts
│   ├── SimulationClock.test.ts
│   ├── SimulationEngine.test.ts
│   └── StraightMotion.test.ts
├── .editorconfig
├── .gitattributes
├── .gitignore
├── index.html
├── LICENSE
├── package.json
├── tsconfig.json
└── vite.config.ts
```

---

## Installation & Setup

Ensure **Node.js** (v18+) is installed.

```bash
npm install
```

---

## Development Server

Launch the Vite local dev server with hot module replacement:

```bash
npm run dev
```

Open `http://localhost:5173/` in your browser.

---

## Automated Testing

Execute all 32 unit and determinism test suites using Vitest:

```bash
npm test
```

To run tests in interactive watch mode:

```bash
npm run test:watch
```

---

## Production Build

Compile TypeScript and build the optimized production assets:

```bash
npm run build
```

---

## Interactive Controls & Shortcuts

| Action | Shortcut | Description |
| :--- | :--- | :--- |
| **Play / Pause** | `Space` | Toggles simulation progression |
| **Step** | `S` | Advances simulation by one fixed timestep $\Delta t$ |
| **Reset** | `R` | Resets simulation and flight clocks to $t = 0$ |
| **Break Lock** | `B` | Breaks active lock and initiates a new 5–10s search |
| **Instant Lock** | `L` | Operator override to instantly lock target beacon |
| **Camera POV** | Button | Transmitter optical gimbal camera view (Default) |
| **Chase Cams** | Buttons | Exterior third-person chase cameras behind UAV 1 or UAV 2 |
| **Tactical Free**| Button | Free orbit camera inspecting the airspace |
| **Optical Zoom** | Buttons | Modulates optical lens FOV ($1\times, 2\times, 4\times, 8\times$) |

---

## Scope & Architectural Boundary

In accordance with the ASTRA LINK specification, this module implements **ONLY THE SIMULATION FOUNDATION**:
- Virtual flight environment, UAV kinematics, and optical beacon
- Camera POV and electro-optical search and lock servo kinematics
- Ground truth telemetry and deterministic clock

This module **DOES NOT** implement and explicitly excludes:
- Neural network detectors (YOLO / Heatmap CNN)
- Kalman filter tracking estimators
- Cryptographic authentication and key exchange
- Downstream network communications, ARQ, and data streaming

---

## License

This project is licensed under the [MIT License](LICENSE).
