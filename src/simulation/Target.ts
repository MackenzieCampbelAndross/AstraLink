import { MotionState, TargetConfig, TargetState, Vector3D } from "../types";
import { MotionModel } from "./motion/MotionModel";

export class Target {
  private motionModel: MotionModel;
  private readonly size: Vector3D;
  private position: Vector3D;
  private velocity: Vector3D;
  private acceleration: Vector3D;
  private orientation: Vector3D; // Euler angles in radians: pitch, yaw, roll

  constructor(config: TargetConfig, motionModel: MotionModel) {
    this.motionModel = motionModel;
    this.size = config.size ? { ...config.size } : { x: 2, y: 2, z: 2 };

    const initialState = this.motionModel.getState();
    this.position = { ...initialState.position };
    this.velocity = { ...initialState.velocity };
    this.acceleration = { ...initialState.acceleration };
    this.orientation = this.computeOrientation(this.velocity, { x: 0, y: 0, z: 0 });
  }

  public setMotionModel(motionModel: MotionModel): void {
    this.motionModel = motionModel;
    this.reset();
  }

  public getMotionModel(): MotionModel {
    return this.motionModel;
  }

  public reset(): void {
    this.motionModel.reset();
    const state = this.motionModel.getState();
    this.position = { ...state.position };
    this.velocity = { ...state.velocity };
    this.acceleration = { ...state.acceleration };
    this.orientation = this.computeOrientation(this.velocity, { x: 0, y: 0, z: 0 });
  }

  public update(time: number, dt: number, frameId: number): TargetState {
    const motionState: MotionState = this.motionModel.update(time, dt);
    this.position = { ...motionState.position };
    this.velocity = { ...motionState.velocity };
    this.acceleration = { ...motionState.acceleration };
    this.orientation = this.computeOrientation(this.velocity, this.orientation);

    return this.getState(time, frameId);
  }

  public getState(timestamp: number = 0, frameId: number = 0): TargetState {
    return {
      timestamp,
      frameId,
      position: { ...this.position },
      velocity: { ...this.velocity },
      acceleration: { ...this.acceleration },
      orientation: { ...this.orientation }
    };
  }

  public getSize(): Vector3D {
    return { ...this.size };
  }

  /**
   * Computes orientation pointing along the velocity vector.
   * If velocity magnitude is near zero (< 1e-4), preserves previous orientation.
   */
  private computeOrientation(vel: Vector3D, prevOrientation: Vector3D): Vector3D {
    const horizontalSpeed = Math.hypot(vel.x, vel.z);
    const totalSpeed = Math.hypot(vel.x, vel.y, vel.z);

    if (totalSpeed < 1e-4) {
      return { ...prevOrientation };
    }

    // Yaw: angle in horizontal X-Z plane (facing -Z as default forward in Three.js)
    const yaw = Math.atan2(vel.x, -vel.z);
    // Pitch: angle w.r.t horizontal plane
    const pitch = Math.atan2(vel.y, horizontalSpeed);
    const roll = 0;

    return { x: pitch, y: yaw, z: roll };
  }
}
