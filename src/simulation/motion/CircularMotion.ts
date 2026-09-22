import { MotionState, Vector3D } from "../../types";
import { MotionModel } from "./MotionModel";

export interface CircularMotionParams {
  center: Vector3D;
  radius: number;
  angularVelocity: number;
  plane?: "XZ" | "XY" | "YZ";
  initialPhase?: number;
}

export class CircularMotion implements MotionModel {
  readonly type = "circular";

  private readonly center: Vector3D;
  private readonly radius: number;
  private readonly angularVelocity: number;
  private readonly plane: "XZ" | "XY" | "YZ";
  private readonly initialPhase: number;

  private state: MotionState;

  constructor(params: CircularMotionParams) {
    if (params.radius <= 0) {
      throw new Error(`Negative radius: circular motion radius must be > 0, got ${params.radius}`);
    }
    this.center = { ...params.center };
    this.radius = params.radius;
    this.angularVelocity = params.angularVelocity;
    this.plane = params.plane ?? "XZ";
    this.initialPhase = params.initialPhase ?? 0;

    this.state = this.calculateState(0);
  }

  public reset(): void {
    this.state = this.calculateState(0);
  }

  public update(time: number, _dt: number): MotionState {
    this.state = this.calculateState(time);
    return this.getState();
  }

  public getState(): MotionState {
    return {
      position: { ...this.state.position },
      velocity: { ...this.state.velocity },
      acceleration: { ...this.state.acceleration }
    };
  }

  private calculateState(time: number): MotionState {
    const theta = this.initialPhase + this.angularVelocity * time;
    const cosT = Math.cos(theta);
    const sinT = Math.sin(theta);
    const R = this.radius;
    const w = this.angularVelocity;
    const w2 = w * w;

    let pos: Vector3D;
    let vel: Vector3D;
    let acc: Vector3D;

    if (this.plane === "XY") {
      pos = {
        x: this.center.x + R * cosT,
        y: this.center.y + R * sinT,
        z: this.center.z
      };
      vel = {
        x: -R * w * sinT,
        y: R * w * cosT,
        z: 0
      };
      acc = {
        x: -R * w2 * cosT,
        y: -R * w2 * sinT,
        z: 0
      };
    } else if (this.plane === "YZ") {
      pos = {
        x: this.center.x,
        y: this.center.y + R * cosT,
        z: this.center.z + R * sinT
      };
      vel = {
        x: 0,
        y: -R * w * sinT,
        z: R * w * cosT
      };
      acc = {
        x: 0,
        y: -R * w2 * cosT,
        z: -R * w2 * sinT
      };
    } else {
      // Default XZ plane (horizontal orbit)
      pos = {
        x: this.center.x + R * cosT,
        y: this.center.y,
        z: this.center.z + R * sinT
      };
      vel = {
        x: -R * w * sinT,
        y: 0,
        z: R * w * cosT
      };
      acc = {
        x: -R * w2 * cosT,
        y: 0,
        z: -R * w2 * sinT
      };
    }

    return { position: pos, velocity: vel, acceleration: acc };
  }
}
