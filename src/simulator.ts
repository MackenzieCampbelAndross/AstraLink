import { AtmosphereRenderer } from "./rendering/AtmosphereRenderer";
import { CameraManager, CameraViewMode } from "./rendering/CameraManager";
import { DebugRenderer } from "./rendering/DebugRenderer";
import { DualUAVRenderer } from "./rendering/DualUAVRenderer";
import { SceneManager } from "./rendering/SceneManager";
import { FlightAttitude, FlightKinematics, TransmitterFlightTrajectory } from "./simulation/flight/FlightKinematics";
import { GimbalController, GimbalTelemetry } from "./simulation/gimbal/GimbalController";
import { SimulationEngine } from "./simulation/SimulationEngine";
import { GroundTruth, MotionType, SimulationConfig, SimulationStateSnapshot, Vector3D } from "./types";

export interface ScreenTargetProjection {
  x: number;
  y: number;
  inFront: boolean;
  inFov: boolean;
  distance: number;
}

export interface FullTelemetrySnapshot {
  simState: SimulationStateSnapshot;
  uav1Position: Vector3D;
  uav1Attitude: FlightAttitude;
  uav2Attitude: FlightAttitude;
  gimbal: GimbalTelemetry;
  fps: number;
  cameraMode: CameraViewMode;
  zoom: number;
  targetScreen: ScreenTargetProjection;
}

export interface SimulatorCallbacks {
  onTelemetryUpdate?: (snapshot: FullTelemetrySnapshot) => void;
}

export class Simulator {
  private readonly engine: SimulationEngine;
  private readonly sceneManager: SceneManager;
  private readonly atmosphereRenderer: AtmosphereRenderer;
  private readonly dualUAVRenderer: DualUAVRenderer;
  private readonly cameraManager: CameraManager;
  private readonly debugRenderer: DebugRenderer;

  private readonly uav1Trajectory: TransmitterFlightTrajectory;
  private readonly uav1Kinematics: FlightKinematics;
  private readonly uav2Kinematics: FlightKinematics;
  private readonly gimbal: GimbalController;

  private isRunning: boolean = true;
  private speedMultiplier: number = 1.0;
  private accumulator: number = 0;
  private lastTimestamp: number = 0;
  private animationFrameId?: number;

  private frameCount: number = 0;
  private fps: number = 60;
  private fpsTimer: number = 0;

  private callbacks: SimulatorCallbacks = {};
  private currentGimbalTelemetry!: GimbalTelemetry;
  private uav1Pos: Vector3D = { x: 0, y: 180, z: 0 };
  private uav1Att: FlightAttitude = { pitch: 0, yaw: 0, roll: 0 };
  private uav2Att: FlightAttitude = { pitch: 0, yaw: 0, roll: 0 };

  constructor(container: HTMLElement, config: SimulationConfig, callbacks?: SimulatorCallbacks) {
    this.callbacks = callbacks ?? {};

    // 1. Decoupled Simulation Engine
    this.engine = new SimulationEngine(config);

    // 2. Flight Dynamics & Gimbal Controller
    this.uav1Trajectory = new TransmitterFlightTrajectory();
    this.uav1Kinematics = new FlightKinematics();
    this.uav2Kinematics = new FlightKinematics();
    this.gimbal = new GimbalController();

    // 3. Three.js Scene & Realistic Atmosphere
    this.sceneManager = new SceneManager(container);
    this.atmosphereRenderer = new AtmosphereRenderer(this.sceneManager.scene);
    this.dualUAVRenderer = new DualUAVRenderer(this.sceneManager.scene);
    this.cameraManager = new CameraManager(container);
    this.debugRenderer = new DebugRenderer(this.sceneManager.scene, config.visualization);

    // Set initial gimbal state
    const initialSim = this.engine.getState();
    const initialU1 = this.uav1Trajectory.update(0);
    this.uav1Pos = initialU1.position;
    this.currentGimbalTelemetry = this.gimbal.update(
      this.uav1Pos,
      0,
      0,
      initialSim.beacon.worldPosition,
      0.033
    );

    // Window resize observer
    const resizeObserver = new ResizeObserver(() => {
      const width = container.clientWidth;
      const height = container.clientHeight;
      this.cameraManager.handleResize(width, height);
    });
    resizeObserver.observe(container);

    // Start render loop
    this.lastTimestamp = performance.now();
    this.loop = this.loop.bind(this);
    this.animationFrameId = requestAnimationFrame(this.loop);
  }

  public setCallbacks(callbacks: SimulatorCallbacks): void {
    this.callbacks = callbacks;
  }

  public start(): void {
    this.isRunning = true;
  }

  public pause(): void {
    this.isRunning = false;
  }

  public togglePlay(): boolean {
    this.isRunning = !this.isRunning;
    return this.isRunning;
  }

  public reset(): void {
    this.engine.reset();
    this.uav1Trajectory.reset();
    this.uav1Kinematics.reset();
    this.uav2Kinematics.reset();
    this.gimbal.reset();
    this.accumulator = 0;
    this.debugRenderer.clear();

    this.stepSimulation(0.033, 0);
  }

  public step(): void {
    this.isRunning = false;
    const fixedDt = this.engine.getConfig().simulation.dt;
    this.stepSimulation(fixedDt, this.engine.getTime() + fixedDt);
  }

  public switchMotion(motion: MotionType): void {
    this.engine.switchMotion(motion);
    this.reset();
  }

  public setSpeed(multiplier: number): void {
    if (multiplier > 0) {
      this.speedMultiplier = multiplier;
    }
  }

  public setCameraMode(mode: CameraViewMode): void {
    this.cameraManager.setMode(mode);
  }

  public getCameraMode(): CameraViewMode {
    return this.cameraManager.getMode();
  }

  public setZoom(zoom: number): void {
    this.cameraManager.setZoom(zoom);
  }

  public breakLock(): void {
    this.gimbal.breakLock();
  }

  public forceSearch(): void {
    this.gimbal.forceSearch();
  }

  public forceLock(): void {
    this.gimbal.forceLock(
      this.currentGimbalTelemetry.targetAzimuth,
      this.currentGimbalTelemetry.targetElevation
    );
  }

  public setTrajectoryVisible(visible: boolean): void {
    this.debugRenderer.setVisible(visible);
  }

  public getEngine(): SimulationEngine {
    return this.engine;
  }

  public getGroundTruth(): GroundTruth {
    return this.engine.getGroundTruth();
  }

  public getIsRunning(): boolean {
    return this.isRunning;
  }

  private stepSimulation(dt: number, time: number): void {
    // 1. Advance UAV 2 Kinematics via SimulationEngine
    this.engine.step();
    const simState = this.engine.getState();

    // 2. Advance UAV 1 Tactical Trajectory
    const u1Motion = this.uav1Trajectory.update(time);
    this.uav1Pos = u1Motion.position;

    // 3. Compute flight attitudes (banking, pitch, yaw)
    this.uav1Att = this.uav1Kinematics.computeAttitude(u1Motion.velocity, time, dt);
    this.uav2Att = this.uav2Kinematics.computeAttitude(simState.target.velocity, time, dt);

    // 4. Update Gimbal Controller (Search / Lock logic)
    this.currentGimbalTelemetry = this.gimbal.update(
      this.uav1Pos,
      this.uav1Att.yaw,
      this.uav1Att.pitch,
      simState.beacon.worldPosition,
      dt
    );

    // 5. Add trajectory breadcrumb
    this.debugRenderer.addPoint(simState.target.position);
  }

  private loop(timestamp: number): void {
    this.animationFrameId = requestAnimationFrame(this.loop);

    const deltaRealMs = timestamp - this.lastTimestamp;
    this.lastTimestamp = timestamp;
    const deltaRealS = Math.min(0.1, deltaRealMs / 1000);

    // Frame rate counting
    this.frameCount++;
    this.fpsTimer += deltaRealS;
    if (this.fpsTimer >= 0.5) {
      this.fps = Math.round(this.frameCount / this.fpsTimer);
      this.frameCount = 0;
      this.fpsTimer = 0;
    }

    // Step physics at fixed dt
    if (this.isRunning && !this.engine.isFinished()) {
      const fixedDt = this.engine.getConfig().simulation.dt;
      this.accumulator += deltaRealS * this.speedMultiplier;

      let steps = 0;
      while (this.accumulator >= fixedDt && steps < 15) {
        this.stepSimulation(fixedDt, this.engine.getTime() + fixedDt);
        this.accumulator -= fixedDt;
        steps++;
      }
      if (this.accumulator > fixedDt * 2) {
        this.accumulator = 0;
      }
    }

    const simState = this.engine.getState();

    const isPov = this.cameraManager.getMode() === "POV";

    // Update 3D visual models
    this.dualUAVRenderer.update(
      this.uav1Pos,
      this.uav1Att,
      simState.target.position,
      this.uav2Att,
      this.currentGimbalTelemetry,
      deltaRealS,
      isPov
    );

    this.atmosphereRenderer.update(deltaRealS);

    // Update active camera
    this.cameraManager.update(
      this.uav1Pos,
      this.uav1Att,
      simState.target.position,
      this.currentGimbalTelemetry
    );

    // Render from current active camera (POV by default)
    this.sceneManager.renderer.render(
      this.sceneManager.scene,
      this.cameraManager.camera
    );

    // Project target beacon onto screen coordinates
    const targetScreen = this.cameraManager.projectToScreen(
      simState.beacon.worldPosition,
      window.innerWidth,
      window.innerHeight
    );

    // Notify UI
    if (this.callbacks.onTelemetryUpdate) {
      this.callbacks.onTelemetryUpdate({
        simState,
        uav1Position: this.uav1Pos,
        uav1Attitude: this.uav1Att,
        uav2Attitude: this.uav2Att,
        gimbal: this.currentGimbalTelemetry,
        fps: this.fps,
        cameraMode: this.cameraManager.getMode(),
        zoom: this.cameraManager.getZoom(),
        targetScreen
      });
    }
  }

  public dispose(): void {
    if (this.animationFrameId !== undefined) {
      cancelAnimationFrame(this.animationFrameId);
    }
    this.sceneManager.dispose();
  }
}
