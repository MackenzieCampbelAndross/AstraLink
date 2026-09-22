import { OpticalBeacon } from "../beacon/OpticalBeacon";
import { validateConfig } from "../config";
import {
  BeaconState,
  GroundTruth,
  MotionType,
  SimulationAPI,
  SimulationConfig,
  SimulationStateSnapshot,
  TargetState
} from "../types";
import { GroundTruthGenerator } from "./GroundTruth";
import { CircularMotion } from "./motion/CircularMotion";
import { Figure8Motion } from "./motion/Figure8Motion";
import { MotionBounds, MotionModel } from "./motion/MotionModel";
import { RandomMotion } from "./motion/RandomMotion";
import { StraightMotion } from "./motion/StraightMotion";
import { SimulationClock } from "./SimulationClock";
import { createSimulationSnapshot } from "./SimulationState";
import { Target } from "./Target";
import { Terminal } from "./Terminal";

export class SimulationEngine implements SimulationAPI {
  private config: SimulationConfig;
  private clock: SimulationClock;
  private terminal1: Terminal;
  private target: Target;
  private beacon: OpticalBeacon;
  private currentGroundTruth: GroundTruth;

  constructor(config: SimulationConfig) {
    this.config = validateConfig(config);
    this.clock = new SimulationClock(this.config.simulation.dt);
    this.terminal1 = new Terminal("terminal1", this.config.terminals.terminal1);

    const motionModel = this.buildMotionModel(this.config);
    this.target = new Target(this.config.target, motionModel);
    this.beacon = new OpticalBeacon(this.config.beacon);

    // Initial position sync for t = 0
    this.syncInitialState();
    this.currentGroundTruth = this.generateCurrentGroundTruth();
  }

  public reset(): void {
    this.clock.reset();
    this.target.reset();
    this.syncInitialState();
    this.currentGroundTruth = this.generateCurrentGroundTruth();
  }

  public step(): void {
    if (this.isFinished()) {
      return;
    }

    // 1. Advance simulation clock
    const simTime = this.clock.step();

    // 2-5. Update target motion, position, velocity, and orientation
    const targetState = this.target.update(
      simTime.time,
      simTime.deltaTime,
      simTime.frameId
    );

    // 6. Update beacon world position
    this.beacon.updateWorldPosition(targetState.position, targetState.orientation);

    // 7. Generate ground truth
    this.currentGroundTruth = this.generateCurrentGroundTruth();
  }

  public update(_deltaTime?: number): void {
    this.step();
  }

  public switchMotion(motionType: MotionType): void {
    this.config.target.motion = motionType;
    const newMotionModel = this.buildMotionModel(this.config);
    this.target.setMotionModel(newMotionModel);
    this.reset();
  }

  public getTime(): number {
    return this.clock.getTime();
  }

  public getFrameId(): number {
    return this.clock.getFrameId();
  }

  public getTargetState(): TargetState {
    return this.target.getState(this.clock.getTime(), this.clock.getFrameId());
  }

  public getBeaconState(): BeaconState {
    return this.beacon.getState();
  }

  public getGroundTruth(): GroundTruth {
    return this.currentGroundTruth;
  }

  public getState(): SimulationStateSnapshot {
    return createSimulationSnapshot(
      this.clock.getTimeState(),
      this.terminal1.getState(),
      this.getTargetState(),
      this.getBeaconState(),
      this.currentGroundTruth,
      this.isFinished()
    );
  }

  public getConfig(): Readonly<SimulationConfig> {
    return this.config;
  }

  public isFinished(): boolean {
    const duration = this.config.simulation.duration_s;
    if (duration === undefined || duration <= 0) {
      return false;
    }
    return this.clock.getTime() >= duration;
  }

  private syncInitialState(): void {
    const targetState = this.target.getState(0, 0);
    this.beacon.updateWorldPosition(targetState.position, targetState.orientation);
  }

  private generateCurrentGroundTruth(): GroundTruth {
    return GroundTruthGenerator.generate(
      this.clock.getTime(),
      this.clock.getFrameId(),
      this.target.getState(this.clock.getTime(), this.clock.getFrameId()),
      this.beacon.getState()
    );
  }

  private buildMotionModel(config: SimulationConfig): MotionModel {
    const bounds: MotionBounds = {
      min: {
        x: -config.world.width / 2,
        y: 0,
        z: -config.world.depth / 2
      },
      max: {
        x: config.world.width / 2,
        y: config.world.height,
        z: config.world.depth / 2
      },
      behavior: config.world.boundary_behavior ?? "bounce"
    };

    const motionType = config.target.motion;

    switch (motionType) {
      case "straight": {
        const vel = config.target.initial_velocity ?? { x: 20, y: 0, z: 0 };
        return new StraightMotion(config.terminals.terminal2.position, vel, bounds);
      }

      case "circular": {
        const circ = config.target.circular;
        const center = circ?.center ?? config.terminals.terminal2.position;
        const radius = circ?.radius ?? 300;
        const angularVelocity = circ?.angular_velocity ?? 0.5;
        const plane = circ?.plane ?? "XZ";
        const initialPhase = circ?.initial_phase ?? 0;
        return new CircularMotion({
          center,
          radius,
          angularVelocity,
          plane,
          initialPhase
        });
      }

      case "figure8": {
        const fig = config.target.figure8;
        const center = fig?.center ?? config.terminals.terminal2.position;
        const amplitudeX = fig?.amplitude_x ?? 300;
        const amplitudeZ = fig?.amplitude_z ?? 150;
        const angularFrequency = fig?.angular_frequency ?? 0.35;
        const initialPhase = fig?.initial_phase ?? 0;
        return new Figure8Motion({
          center,
          amplitudeX,
          amplitudeZ,
          angularFrequency,
          initialPhase
        });
      }

      case "random": {
        const rnd = config.target.random;
        return new RandomMotion({
          initialPosition: config.terminals.terminal2.position,
          maxAcceleration: rnd?.max_acceleration ?? 25,
          maxVelocity: rnd?.max_velocity ?? 60,
          damping: rnd?.damping ?? 0.02,
          seed: config.seed,
          bounds
        });
      }

      default:
        throw new Error(`Unknown motion model: ${motionType}`);
    }
  }
}
