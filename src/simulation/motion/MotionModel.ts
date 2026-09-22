import { MotionState, Vector3D } from "../../types";

export interface MotionBounds {
  min: Vector3D;
  max: Vector3D;
  behavior: "bounce" | "clamp" | "wrap";
}

export interface MotionModel {
  readonly type: string;
  reset(): void;
  update(time: number, dt: number): MotionState;
  getState(): MotionState;
}
