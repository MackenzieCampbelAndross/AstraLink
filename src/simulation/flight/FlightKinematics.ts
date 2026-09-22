import { MotionState, Vector3D } from "../../types";

export interface FlightAttitude {
  pitch: number; // radians
  yaw: number;   // radians
  roll: number;  // radians (banking)
}

export class FlightKinematics {
  private prevYaw = 0;
  private currentRoll = 0;

  /**
   * Calculates realistic aerodynamic flight attitude from velocity and turn-rate.
   * Banks proportionally to yaw rate for realistic flight dynamics.
   */
  public computeAttitude(velocity: Vector3D, _time: number, dt: number): FlightAttitude {
    const horizontalSpeed = Math.hypot(velocity.x, velocity.z);
    const totalSpeed = Math.hypot(velocity.x, velocity.y, velocity.z);

    if (totalSpeed < 0.1) {
      return { pitch: 0, yaw: this.prevYaw, roll: 0 };
    }

    // Yaw heading: facing -Z as forward convention
    const yaw = Math.atan2(velocity.x, -velocity.z);

    // Pitch attitude: climb or dive angle
    const pitch = Math.atan2(velocity.y, horizontalSpeed);

    // Calculate yaw rate (turning rate)
    let yawDelta = yaw - this.prevYaw;
    while (yawDelta > Math.PI) yawDelta -= 2 * Math.PI;
    while (yawDelta < -Math.PI) yawDelta += 2 * Math.PI;

    const safeDt = dt > 0 ? dt : 0.033;
    const yawRate = yawDelta / safeDt;

    // Coordinated turn equation: tan(bank) = (v * yawRate) / g
    const g = 9.81;
    const targetRoll = -Math.atan2(totalSpeed * yawRate, g);

    // Clamp roll to realistic limits (-45 deg to +45 deg)
    const maxRoll = (45 * Math.PI) / 180;
    const clampedTargetRoll = Math.max(-maxRoll, Math.min(maxRoll, targetRoll));

    // Smooth roll damping
    const rollAlpha = Math.min(1.0, 6.0 * safeDt);
    this.currentRoll += (clampedTargetRoll - this.currentRoll) * rollAlpha;

    this.prevYaw = yaw;

    return {
      pitch,
      yaw,
      roll: this.currentRoll
    };
  }

  public reset(): void {
    this.prevYaw = 0;
    this.currentRoll = 0;
  }
}

/**
 * Procedural tactical patrol flight trajectory for UAV 1 (Transmitter).
 * Flies an expansive smooth reconnaissance oval/circuit at 200m altitude.
 */
export class TransmitterFlightTrajectory {
  private center: Vector3D = { x: 0, y: 180, z: 100 };
  private radiusX = 350;
  private radiusZ = 220;
  private angularSpeed = 0.18; // ~35s per orbit

  public update(time: number): MotionState {
    const angle = this.angularSpeed * time;
    const cosA = Math.cos(angle);
    const sinA = Math.sin(angle);

    const x = this.center.x + this.radiusX * cosA;
    const y = this.center.y + Math.sin(angle * 2) * 15; // Gentle altitude wave
    const z = this.center.z + this.radiusZ * sinA;

    const vx = -this.radiusX * this.angularSpeed * sinA;
    const vy = 30 * this.angularSpeed * Math.cos(angle * 2);
    const vz = this.radiusZ * this.angularSpeed * cosA;

    const ax = -this.radiusX * this.angularSpeed * this.angularSpeed * cosA;
    const ay = -60 * this.angularSpeed * this.angularSpeed * Math.sin(angle * 2);
    const az = -this.radiusZ * this.angularSpeed * this.angularSpeed * sinA;

    return {
      position: { x, y, z },
      velocity: { x: vx, y: vy, z: vz },
      acceleration: { x: ax, y: ay, z: az }
    };
  }

  public reset(): void {
    // Statelessly computed from time
  }
}
