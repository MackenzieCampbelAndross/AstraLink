import { MotionState, Vector3D } from "../../types";
import { SeededRandom } from "../SeededRandom";
import { MotionBounds, MotionModel } from "./MotionModel";

export interface RandomMotionParams {
  initialPosition: Vector3D;
  maxAcceleration: number;
  maxVelocity: number;
  damping: number;
  seed: number;
  bounds?: MotionBounds;
}

/**
 * Deterministic, smooth stochastic motion model.
 * Uses SeededRandom to generate smooth random acceleration perturbations
 * that are integrated into velocity and position with damping and boundary bouncing.
 * Avoids any teleportation or discontinuous jumps.
 */
export class RandomMotion implements MotionModel {
  readonly type = "random";

  private readonly initialPosition: Vector3D;
  private readonly maxAcceleration: number;
  private readonly maxVelocity: number;
  private readonly damping: number;
  private readonly bounds?: MotionBounds;
  private readonly rng: SeededRandom;

  private currentPosition: Vector3D;
  private currentVelocity: Vector3D;
  private currentAcceleration: Vector3D;

  constructor(params: RandomMotionParams) {
    if (params.maxAcceleration <= 0) {
      throw new Error(`Invalid acceleration: maxAcceleration must be > 0, got ${params.maxAcceleration}`);
    }
    if (params.maxVelocity <= 0) {
      throw new Error(`Invalid velocity: maxVelocity must be > 0, got ${params.maxVelocity}`);
    }

    this.initialPosition = { ...params.initialPosition };
    this.maxAcceleration = params.maxAcceleration;
    this.maxVelocity = params.maxVelocity;
    this.damping = Math.max(0, Math.min(0.5, params.damping));
    this.bounds = params.bounds ? { ...params.bounds } : undefined;
    this.rng = new SeededRandom(params.seed);

    this.currentPosition = { ...this.initialPosition };
    this.currentVelocity = { x: 0, y: 0, z: 0 };
    this.currentAcceleration = { x: 0, y: 0, z: 0 };
  }

  public reset(): void {
    this.rng.reset();
    this.currentPosition = { ...this.initialPosition };
    this.currentVelocity = { x: 0, y: 0, z: 0 };
    this.currentAcceleration = { x: 0, y: 0, z: 0 };
  }

  public update(_time: number, dt: number): MotionState {
    // Generate smooth target acceleration perturbation
    const targetAx = this.rng.gaussian(0, this.maxAcceleration * 0.5);
    const targetAy = this.rng.gaussian(0, this.maxAcceleration * 0.2); // subtle vertical movement
    const targetAz = this.rng.gaussian(0, this.maxAcceleration * 0.5);

    // Exponential smoothing for acceleration to ensure continuous derivatives
    const smoothFactor = Math.min(1.0, 10.0 * dt);
    this.currentAcceleration.x += (targetAx - this.currentAcceleration.x) * smoothFactor;
    this.currentAcceleration.y += (targetAy - this.currentAcceleration.y) * smoothFactor;
    this.currentAcceleration.z += (targetAz - this.currentAcceleration.z) * smoothFactor;

    // Clamp acceleration magnitude
    const accMag = Math.hypot(
      this.currentAcceleration.x,
      this.currentAcceleration.y,
      this.currentAcceleration.z
    );
    if (accMag > this.maxAcceleration && accMag > 1e-6) {
      const scale = this.maxAcceleration / accMag;
      this.currentAcceleration.x *= scale;
      this.currentAcceleration.y *= scale;
      this.currentAcceleration.z *= scale;
    }

    // Integrate acceleration to velocity
    this.currentVelocity.x += this.currentAcceleration.x * dt;
    this.currentVelocity.y += this.currentAcceleration.y * dt;
    this.currentVelocity.z += this.currentAcceleration.z * dt;

    // Apply damping
    const dampMultiplier = Math.max(0, 1.0 - this.damping * dt * 30);
    this.currentVelocity.x *= dampMultiplier;
    this.currentVelocity.y *= dampMultiplier;
    this.currentVelocity.z *= dampMultiplier;

    // Clamp velocity magnitude
    const velMag = Math.hypot(
      this.currentVelocity.x,
      this.currentVelocity.y,
      this.currentVelocity.z
    );
    if (velMag > this.maxVelocity && velMag > 1e-6) {
      const scale = this.maxVelocity / velMag;
      this.currentVelocity.x *= scale;
      this.currentVelocity.y *= scale;
      this.currentVelocity.z *= scale;
    }

    // Integrate velocity to position
    let nextX = this.currentPosition.x + this.currentVelocity.x * dt;
    let nextY = this.currentPosition.y + this.currentVelocity.y * dt;
    let nextZ = this.currentPosition.z + this.currentVelocity.z * dt;

    // Apply boundary constraints
    if (this.bounds) {
      if (nextX > this.bounds.max.x) {
        nextX = this.bounds.max.x - (nextX - this.bounds.max.x);
        this.currentVelocity.x = -Math.abs(this.currentVelocity.x);
        this.currentAcceleration.x = -Math.abs(this.currentAcceleration.x);
      } else if (nextX < this.bounds.min.x) {
        nextX = this.bounds.min.x + (this.bounds.min.x - nextX);
        this.currentVelocity.x = Math.abs(this.currentVelocity.x);
        this.currentAcceleration.x = Math.abs(this.currentAcceleration.x);
      }

      if (nextY > this.bounds.max.y) {
        nextY = this.bounds.max.y - (nextY - this.bounds.max.y);
        this.currentVelocity.y = -Math.abs(this.currentVelocity.y);
        this.currentAcceleration.y = -Math.abs(this.currentAcceleration.y);
      } else if (nextY < this.bounds.min.y) {
        nextY = this.bounds.min.y + (this.bounds.min.y - nextY);
        this.currentVelocity.y = Math.abs(this.currentVelocity.y);
        this.currentAcceleration.y = Math.abs(this.currentAcceleration.y);
      }

      if (nextZ > this.bounds.max.z) {
        nextZ = this.bounds.max.z - (nextZ - this.bounds.max.z);
        this.currentVelocity.z = -Math.abs(this.currentVelocity.z);
        this.currentAcceleration.z = -Math.abs(this.currentAcceleration.z);
      } else if (nextZ < this.bounds.min.z) {
        nextZ = this.bounds.min.z + (this.bounds.min.z - nextZ);
        this.currentVelocity.z = Math.abs(this.currentVelocity.z);
        this.currentAcceleration.z = Math.abs(this.currentAcceleration.z);
      }
    }

    this.currentPosition = { x: nextX, y: nextY, z: nextZ };
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
