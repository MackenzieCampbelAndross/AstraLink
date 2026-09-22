import { BeaconConfig, BeaconState, Vector3D } from "../types";

export class OpticalBeacon {
  private enabled: boolean;
  private brightness: number;
  private size: number;
  private readonly localPosition: Vector3D;
  private worldPosition: Vector3D;

  constructor(config: BeaconConfig) {
    this.enabled = config.enabled;
    this.brightness = config.brightness;
    this.size = config.size;
    this.localPosition = config.localPosition
      ? { ...config.localPosition }
      : { x: 0, y: 1.0, z: 0 };
    this.worldPosition = { ...this.localPosition };
  }

  public updateWorldPosition(targetPosition: Vector3D, targetOrientation: Vector3D): void {
    // Transform local offset by target orientation (Euler: pitch = x, yaw = y, roll = z)
    const rotatedOffset = this.rotateVector(this.localPosition, targetOrientation);
    this.worldPosition = {
      x: targetPosition.x + rotatedOffset.x,
      y: targetPosition.y + rotatedOffset.y,
      z: targetPosition.z + rotatedOffset.z
    };
  }

  public getState(): BeaconState {
    return {
      enabled: this.enabled,
      brightness: this.brightness,
      size: this.size,
      localPosition: { ...this.localPosition },
      worldPosition: { ...this.worldPosition }
    };
  }

  public setEnabled(enabled: boolean): void {
    this.enabled = enabled;
  }

  public setBrightness(brightness: number): void {
    this.brightness = Math.max(0, brightness);
  }

  public getWorldPosition(): Vector3D {
    return { ...this.worldPosition };
  }

  public getLocalPosition(): Vector3D {
    return { ...this.localPosition };
  }

  /**
   * Applies Euler rotation (pitch around X, yaw around Y, roll around Z)
   * to a local 3D vector.
   */
  private rotateVector(v: Vector3D, euler: Vector3D): Vector3D {
    const cosX = Math.cos(euler.x);
    const sinX = Math.sin(euler.x);
    const cosY = Math.cos(euler.y);
    const sinY = Math.sin(euler.y);
    const cosZ = Math.cos(euler.z);
    const sinZ = Math.sin(euler.z);

    // 1. Rotate around X (pitch)
    const y1 = v.y * cosX - v.z * sinX;
    const z1 = v.y * sinX + v.z * cosX;
    const x1 = v.x;

    // 2. Rotate around Y (yaw)
    const x2 = x1 * cosY + z1 * sinY;
    const y2 = y1;
    const z2 = -x1 * sinY + z1 * cosY;

    // 3. Rotate around Z (roll)
    const x3 = x2 * cosZ - y2 * sinZ;
    const y3 = x2 * sinZ + y2 * cosZ;
    const z3 = z2;

    return { x: x3, y: y3, z: z3 };
  }
}
