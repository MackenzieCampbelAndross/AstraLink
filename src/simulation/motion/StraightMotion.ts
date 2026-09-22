import { MotionState, Vector3D } from "../../types";
import { MotionBounds, MotionModel } from "./MotionModel";

export class StraightMotion implements MotionModel {
  readonly type = "straight";

  private readonly initialPosition: Vector3D;
  private readonly initialVelocity: Vector3D;
  private readonly bounds?: MotionBounds;

  private currentPosition: Vector3D;
  private currentVelocity: Vector3D;
  private currentAcceleration: Vector3D;

  constructor(
    initialPosition: Vector3D,
    initialVelocity: Vector3D,
    bounds?: MotionBounds
  ) {
    this.initialPosition = { ...initialPosition };
    this.initialVelocity = { ...initialVelocity };
    this.bounds = bounds ? { ...bounds } : undefined;

    this.currentPosition = { ...this.initialPosition };
    this.currentVelocity = { ...this.initialVelocity };
    this.currentAcceleration = { x: 0, y: 0, z: 0 };
  }

  public reset(): void {
    this.currentPosition = { ...this.initialPosition };
    this.currentVelocity = { ...this.initialVelocity };
    this.currentAcceleration = { x: 0, y: 0, z: 0 };
  }

  public update(_time: number, dt: number): MotionState {
    if (!this.bounds) {
      // Pure analytical unbounded straight motion
      this.currentPosition.x += this.currentVelocity.x * dt;
      this.currentPosition.y += this.currentVelocity.y * dt;
      this.currentPosition.z += this.currentVelocity.z * dt;
      this.currentAcceleration = { x: 0, y: 0, z: 0 };
      return this.getState();
    }

    // Step with boundary conditions
    let nextX = this.currentPosition.x + this.currentVelocity.x * dt;
    let nextY = this.currentPosition.y + this.currentVelocity.y * dt;
    let nextZ = this.currentPosition.z + this.currentVelocity.z * dt;

    if (this.bounds.behavior === "bounce") {
      if (nextX > this.bounds.max.x) {
        nextX = this.bounds.max.x - (nextX - this.bounds.max.x);
        this.currentVelocity.x = -Math.abs(this.currentVelocity.x);
      } else if (nextX < this.bounds.min.x) {
        nextX = this.bounds.min.x + (this.bounds.min.x - nextX);
        this.currentVelocity.x = Math.abs(this.currentVelocity.x);
      }

      if (nextY > this.bounds.max.y) {
        nextY = this.bounds.max.y - (nextY - this.bounds.max.y);
        this.currentVelocity.y = -Math.abs(this.currentVelocity.y);
      } else if (nextY < this.bounds.min.y) {
        nextY = this.bounds.min.y + (this.bounds.min.y - nextY);
        this.currentVelocity.y = Math.abs(this.currentVelocity.y);
      }

      if (nextZ > this.bounds.max.z) {
        nextZ = this.bounds.max.z - (nextZ - this.bounds.max.z);
        this.currentVelocity.z = -Math.abs(this.currentVelocity.z);
      } else if (nextZ < this.bounds.min.z) {
        nextZ = this.bounds.min.z + (this.bounds.min.z - nextZ);
        this.currentVelocity.z = Math.abs(this.currentVelocity.z);
      }
    } else if (this.bounds.behavior === "clamp") {
      if (nextX > this.bounds.max.x || nextX < this.bounds.min.x) {
        nextX = Math.max(this.bounds.min.x, Math.min(this.bounds.max.x, nextX));
        this.currentVelocity.x = 0;
      }
      if (nextY > this.bounds.max.y || nextY < this.bounds.min.y) {
        nextY = Math.max(this.bounds.min.y, Math.min(this.bounds.max.y, nextY));
        this.currentVelocity.y = 0;
      }
      if (nextZ > this.bounds.max.z || nextZ < this.bounds.min.z) {
        nextZ = Math.max(this.bounds.min.z, Math.min(this.bounds.max.z, nextZ));
        this.currentVelocity.z = 0;
      }
    }

    this.currentPosition = { x: nextX, y: nextY, z: nextZ };
    this.currentAcceleration = { x: 0, y: 0, z: 0 };
    return this.getState();
  }

  public getState(): MotionState {
    return {
      position: { ...this.currentPosition },
      velocity: { ...this.currentVelocity },
      acceleration: { ...this.currentAcceleration }
    };
  }
}
