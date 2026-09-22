# Astra Link — Unified Integration Status & Baseline Plan

> **Phase**: Prompt 1 of 5 (Integration Baseline & Gap Analysis)  
> **Repository**: [AstraLink](https://github.com/MackenzieCampbelAndross/AstraLink)  
> **Working Branch**: `integration/team-integration`  
> **Verification**: 538 automated tests passing across subsystems (Member 2: 328, Member 3: 203, Integration: 7). Member 1 TypeScript build passing.

---

## 1. Actual System Architecture & End-to-End Runtime Data Flow

```text
+-----------------------------------------------------------------------+
| MEMBER 1: 3D Visualization & Physics Engine (TypeScript / Three.js)   |
| src/simulation/SimulationEngine.ts                                   |
|   ├── Target.ts & OpticalBeacon.ts -> World 3D Position & Velocity   |
|   └── SimulationAPI -> State Snapshot (GroundTruth, Target, Beacon)  |
+-----------------------------------------------------------------------+
                                  │
                                  ▼ (Observations: 3D / Angular Centroid)
+-----------------------------------------------------------------------+
| MEMBER 2: Optical Tracking Subsystem (Python)                         |
| astra-link-member2/src/astra_link_tracking/                           |
|   ├── simulation/virtual_camera.py -> VirtualCamera observe target   |
|   ├── tracking/kalman.py -> KalmanFilter position/velocity estimate  |
|   ├── tracking/motion_consistency.py -> MotionConsistencyChecker      |
|   ├── tracking/state_machine.py -> TrackingStateMachine (LOCKED, etc) |
|   └── control/controller.py -> CameraController PTZ commands         |
|   Output: Member 2 TrackingState telemetry                            |
+-----------------------------------------------------------------------+
                                  │
                                  ▼ (Telemetry: state, consistency, cov)
+-----------------------------------------------------------------------+
| INTEGRATION BOUNDARY ADAPTER (Python)                                 |
| astra_link_integration/adapter.py -> TrackingAdapter.adapt()          |
|   ├── M2 TrackingMode Enum -> M3 Uppercase String ("LOCKED", etc)     |
|   ├── M2 bool consistency + float confidence -> M3 float score [0, 1] |
|   └── M2 2x2 covariance -> M3 prediction_covariance List[float]       |
|   Output: Member 3 Security TrackingState                             |
+-----------------------------------------------------------------------+
                                  │
                                  ▼ (Security TrackingState)
+-----------------------------------------------------------------------+
| MEMBER 3: Security, Auth & Secure Transport Subsystem (Python)       |
| astra_link_member3/src/                                              |
|   ├── tracking/tracking_state.py -> TrackingValidityEvaluator        |
|   ├── trust/trust_engine.py -> Multi-Domain TrustEngine (5 Gates)    |
|   ├── trust/authorization.py -> TransmissionAuthorizationGate        |
|   ├── session/ -> Ephemeral X25519 + HKDF Session Keys               |
|   └── transport/ -> AES-256-GCM + ARQSender / Selective Repeat ARQ   |
+-----------------------------------------------------------------------+
```

---

## 2. Incomplete Member 2 Portions Audit

### Category A: Required for Basic End-to-End Operation
1. **`Tracker.update()` Standard Entry Point Wiring**:
   - `astra_link_tracking/tracking/tracker.py` currently contains a draft stub for `update()`. The tested tracking loop logic is inside `ClosedLoopSimulation`.
   - **Action**: Refactor `Tracker.update(detection)` to coordinate `CoordinateTransform`, `KalmanFilter`, `MotionConsistencyChecker`, `TrackingStateMachine`, and `CameraController` as a clean, unified object.

2. **Standard Frame Observation Interface**:
   - Expose a clean `Tracker.process_detection(detection)` interface accepting Member 1 beacon pixel/angle observations.

### Category B: Required for Realistic Tracking
1. **Automated Reacquisition Controller Triggering**:
   - `reacquisition/` contains Levy search, raster search, and trajectory predictors (`levy_search.py`, `raster_search.py`, `predictor.py`). These components are unit-tested but need explicit triggering when `TrackingStateMachine` transitions to `COASTING` or `LOST`.

2. **Dynamic Range / Noise Parameterization**:
   - Parameterize measurement noise variance in `VirtualCamera` based on range to target.

### Category C: Optional Improvements
1. **Real-time Matplotlib / Overlay Debug Streams**:
   - `visualization/debug_view.py` provides off-line plot rendering. Connecting HUD overlays on canvas will enhance demo feedback.

---

## 3. Current Blockers & Connection Gaps

1. **Member 1 -> Member 2 Telemetry Bridge**:
   - Member 1 runs in JavaScript/TypeScript browser environment (`vite`), whereas Member 2 and 3 run in Python.
   - **Bridge Requirement**: A lightweight bridge (HTTP/WebSocket server or shared API model) is needed so Member 1's live Three.js target telemetry can be consumed by the Python tracking and security pipeline.

2. **Full Pipeline Orchestration**:
   - `IntegratedTrackingSecurityPipeline` currently processes individual frames. It needs an asynchronous or continuous tick runner to sync Member 1 time steps with Member 2 tracking and Member 3 ARQ payload delivery.

---

## 4. 5-Prompt Master Integration Roadmap

- [x] **Prompt 1 (Current)**: Unified Integration Baseline, Architecture Trace, Member 2 Audit, Verification Status & `INTEGRATION_STATUS.md`.
- [ ] **Prompt 2**: Complete Member 2 `Tracker.update()` implementation and establish the Python Integrated System Orchestrator linking Member 2 Tracker -> Adapter -> Member 3 Security & ARQ Transport.
- [ ] **Prompt 3**: Implement lightweight TypeScript ↔ Python Communication Bridge (WebSocket / HTTP JSON gateway) streaming Member 1 target/beacon telemetry into the Python pipeline.
- [ ] **Prompt 4**: Connect Three.js Member 1 UI frontend with real-time status telemetry overlays displaying Member 2 tracking mode and Member 3 security/authorization state.
- [ ] **Prompt 5**: Final End-to-End Verification, Full Test Suite Execution, Presentation Demo Script, and Production Web Readiness Confirmation.
