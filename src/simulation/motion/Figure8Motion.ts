import { MotionState, Vector3D } from "../../types";
import { MotionModel } from "./MotionModel";

export interface Figure8MotionParams {
  center: Vector3D;
  amplitudeX: number;
  amplitudeZ: number;
  angularFrequency: number;
  initialPhase?: number;
}

/**
 * Smooth Lissajous / Lemniscate figure-8 trajectory.
 * x(t) = Cx + Ax * sin(wt + phi)
 * y(t) = Cy
 * z(t) = Cz + Az * sin(2*wt + 2*phi)
 * Provides exact analytical derivatives for velocity and acceleration.
 */
export class Figure8Motion implements MotionModel {
  readonly type = "figure8";

  private readonly center: Vector3D;
  private readonly amplitudeX: number;
  private readonly amplitudeZ: number;
  private readonly angularFrequency: number;
  private readonly initialPhase: number;

  private state: MotionState;

  constructor(params: Figure8MotionParams) {
    if (params.amplitudeX <= 0) {
      throw new Error(`Invalid amplitude: figure-8 amplitudeX must be > 0, got ${params.amplitudeX}`);
    }
    if (params.amplitudeZ <= 0) {
      throw new Error(`Invalid amplitude: figure-8 amplitudeZ must be > 0, got ${params.amplitudeZ}`);
    }
    this.center = { ...params.center };
    this.amplitudeX = params.amplitudeX;
    this.amplitudeZ = params.amplitudeZ;
    this.angularFrequency = params.angularFrequency;
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
    const theta = this.initialPhase + this.angularFrequency * time;
    const sinT = Math.sin(theta);
    const cosT = Math.cos(theta);

    const theta2 = 2 * theta;
    const sin2T = Math.sin(theta2);
    const cos2T = Math.cos(theta2);

    const Ax = this.amplitudeX;
    const Az = this.amplitudeZ;
    const w = this.angularFrequency;
    const w2 = w * w;

    const pos: Vector3D = {
      x: this.center.x + Ax * sinT,
      y: this.center.y,
      z: this.center.z + Az * sin2T
    };

    const vel: Vector3D = {
      x: Ax * w * cosT,
      y: 0,
      z: 2 * Az * w * cos2T
    };

    const acc: Vector3D = {
      x: -Ax * w2 * sinT,
      y: 0,
      z: -4 * Az * w2 * sin2T
    };

    return { position: pos, velocity: vel, acceleration: acc };
  }
}
