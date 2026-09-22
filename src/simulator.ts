import { BeaconRenderer } from "./rendering/BeaconRenderer";
import { DebugRenderer } from "./rendering/DebugRenderer";
import { SceneManager } from "./rendering/SceneManager";
import { TerminalRenderer } from "./rendering/TerminalRenderer";
import { WorldRenderer } from "./rendering/WorldRenderer";
import { SimulationEngine } from "./simulation/SimulationEngine";
import { GroundTruth, MotionType, SimulationConfig, SimulationStateSnapshot } from "./types";

export interface SimulatorCallbacks {
  onStateUpdate?: (state: SimulationStateSnapshot, fps: number) => void;
}

export class Simulator {
  private readonly engine: SimulationEngine;
  private readonly sceneManager: SceneManager;
  private readonly worldRenderer: WorldRenderer;
  private readonly terminalRenderer: TerminalRenderer;
  private readonly beaconRenderer: BeaconRenderer;
  private readonly debugRenderer: DebugRenderer;

  private isRunning: boolean = true;
  private speedMultiplier: number = 1.0;
  private accumulator: number = 0;
  private lastTimestamp: number = 0;
  private animationFrameId?: number;

  private frameCount: number = 0;
  private fps: number = 60;
  private fpsTimer: number = 0;

  private callbacks: SimulatorCallbacks = {};

  constructor(container: HTMLElement, config: SimulationConfig, callbacks?: SimulatorCallbacks) {
    this.callbacks = callbacks ?? {};

    // 1. Initialize decoupled headless SimulationEngine
    this.engine = new SimulationEngine(config);

    // 2. Initialize Three.js visualization
    this.sceneManager = new SceneManager(container);
    this.worldRenderer = new WorldRenderer(this.sceneManager.scene, config.world);

    const initialState = this.engine.getState();
    this.terminalRenderer = new TerminalRenderer(
      this.sceneManager.scene,
      initialState.terminal1,
      initialState.target
    );
    this.beaconRenderer = new BeaconRenderer(
      this.sceneManager.scene,
      initialState.beacon
    );
    this.debugRenderer = new DebugRenderer(
      this.sceneManager.scene,
      config.visualization
    );

    // Add initial target position to trajectory
    this.debugRenderer.addPoint(initialState.target.position);

    // Start animation loop
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
    this.accumulator = 0;
    this.debugRenderer.clear();

    const state = this.engine.getState();
    this.terminalRenderer.update(state.terminal1, state.target);
    this.beaconRenderer.update(state.beacon);
    this.debugRenderer.addPoint(state.target.position);

    this.notifyUpdate(state);
  }

  public step(): void {
    this.isRunning = false;
    this.engine.step();

    const state = this.engine.getState();
    this.terminalRenderer.update(state.terminal1, state.target);
    this.beaconRenderer.update(state.beacon);
    this.debugRenderer.addPoint(state.target.position);

    this.notifyUpdate(state);
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

  public setTrajectoryVisible(visible: boolean): void {
    this.debugRenderer.setVisible(visible);
  }

  public resetCamera(): void {
    this.sceneManager.camera.position.set(400, 350, 600);
    this.sceneManager.controls.target.set(0, 50, -150);
    this.sceneManager.controls.update();
  }

  public getWorldRenderer(): WorldRenderer {
    return this.worldRenderer;
  }

  public getEngine(): SimulationEngine {
    return this.engine;
  }

  public getGroundTruth(): GroundTruth {
    return this.engine.getGroundTruth();
  }

  public getSpeed(): number {
    return this.speedMultiplier;
  }

  public getIsRunning(): boolean {
    return this.isRunning;
  }

  private loop(timestamp: number): void {
    this.animationFrameId = requestAnimationFrame(this.loop);

    const deltaRealMs = timestamp - this.lastTimestamp;
    this.lastTimestamp = timestamp;

    // Cap real delta to 100ms to avoid spiral of death when tab is inactive
    const deltaRealS = Math.min(0.1, deltaRealMs / 1000);

    // Calculate rendering FPS
    this.frameCount++;
    this.fpsTimer += deltaRealS;
    if (this.fpsTimer >= 0.5) {
      this.fps = Math.round(this.frameCount / this.fpsTimer);
      this.frameCount = 0;
      this.fpsTimer = 0;
    }

    if (this.isRunning && !this.engine.isFinished()) {
      const fixedDt = this.engine.getConfig().simulation.dt;
      this.accumulator += deltaRealS * this.speedMultiplier;

      let stepsTaken = 0;
      // Step engine in exact deterministic increments
      while (this.accumulator >= fixedDt && stepsTaken < 20) {
        this.engine.step();
        this.accumulator -= fixedDt;
        stepsTaken++;

        const currentState = this.engine.getState();
        this.debugRenderer.addPoint(currentState.target.position);
      }

      if (this.accumulator > fixedDt * 2) {
        this.accumulator = 0;
      }
    }

    // Update Three.js visual objects from current simulation state
    const state = this.engine.getState();
    this.terminalRenderer.update(state.terminal1, state.target);
    this.beaconRenderer.update(state.beacon);

    // Render developer debug viewport
    this.sceneManager.render();

    // Telemetry callback to UI
    this.notifyUpdate(state);
  }

  private notifyUpdate(state: SimulationStateSnapshot): void {
    if (this.callbacks.onStateUpdate) {
      this.callbacks.onStateUpdate(state, this.fps);
    }
  }

  public dispose(): void {
    if (this.animationFrameId !== undefined) {
      cancelAnimationFrame(this.animationFrameId);
    }
    this.sceneManager.dispose();
  }
}
