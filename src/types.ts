export interface Vector3D {
  x: number;
  y: number;
  z: number;
}

export interface Orientation3D {
  pitch: number;
  yaw: number;
  roll: number;
}

export interface MotionState {
  position: Vector3D;
  velocity: Vector3D;
  acceleration: Vector3D;
}

export interface SimulationTime {
  time: number;
  deltaTime: number;
  frameId: number;
}

export type BoundaryBehavior = "bounce" | "clamp" | "wrap";

export type MotionType = "straight" | "circular" | "figure8" | "random";

export interface StraightMotionConfig {
  initial_velocity: Vector3D;
}

export interface CircularMotionConfig {
  center?: Vector3D;
  radius: number;
  angular_velocity: number;
  plane?: "XZ" | "XY" | "YZ";
  initial_phase?: number;
}

export interface Figure8MotionConfig {
  amplitude_x: number;
  amplitude_z: number;
  angular_frequency: number;
  center?: Vector3D;
  initial_phase?: number;
}

export interface RandomMotionConfig {
  max_acceleration: number;
  max_velocity: number;
  damping: number;
}

export type MotionParameters =
  | { type: "straight"; params: StraightMotionConfig }
  | { type: "circular"; params: CircularMotionConfig }
  | { type: "figure8"; params: Figure8MotionConfig }
  | { type: "random"; params: RandomMotionConfig };

export interface TargetConfig {
  motion: MotionType;
  size?: Vector3D;
  initial_velocity?: Vector3D;
  circular?: CircularMotionConfig;
  figure8?: Figure8MotionConfig;
  random?: RandomMotionConfig;
}

export interface BeaconConfig {
  enabled: boolean;
  brightness: number;
  size: number;
  localPosition?: Vector3D;
}

export interface TerminalConfig {
  position: Vector3D;
}

export interface WorldConfig {
  width: number;
  height: number;
  depth: number;
  boundary_behavior?: BoundaryBehavior;
}

export interface VisualizationConfig {
  showTrajectory?: boolean;
  trajectoryLength?: number;
}

export interface SimulationConfig {
  seed: number;
  simulation: {
    duration_s?: number;
    dt: number;
  };
  world: WorldConfig;
  terminals: {
    terminal1: TerminalConfig;
    terminal2: TerminalConfig;
  };
  target: TargetConfig;
  beacon: BeaconConfig;
  visualization?: VisualizationConfig;
}

export interface TerminalState {
  id: string;
  position: Vector3D;
  orientation: Vector3D;
}

export interface TargetState {
  timestamp: number;
  frameId: number;
  position: Vector3D;
  velocity: Vector3D;
  acceleration: Vector3D;
  orientation: Vector3D;
}

export interface BeaconState {
  enabled: boolean;
  brightness: number;
  size: number;
  localPosition: Vector3D;
  worldPosition: Vector3D;
}

export interface GroundTruth {
  timestamp: number;
  frameId: number;
  targetPosition: Vector3D;
  targetVelocity: Vector3D;
  targetAcceleration: Vector3D;
  targetOrientation: Vector3D;
  beaconPosition: Vector3D;
}

export interface SimulationStateSnapshot {
  time: SimulationTime;
  terminal1: TerminalState;
  target: TargetState;
  beacon: BeaconState;
  groundTruth: GroundTruth;
  isFinished: boolean;
}

export interface SimulationAPI {
  reset(): void;
  step(): void;
  update(deltaTime?: number): void;
  getTime(): number;
  getFrameId(): number;
  getTargetState(): TargetState;
  getBeaconState(): BeaconState;
  getGroundTruth(): GroundTruth;
  getState(): SimulationStateSnapshot;
  getConfig(): Readonly<SimulationConfig>;
  isFinished(): boolean;
}
