import { Vector3D } from "../../types";

export type GimbalState = "SEARCHING" | "ACQUIRING" | "LOCKED" | "LOST";

export interface GimbalTelemetry {
  state: GimbalState;
  azimuth: number;       // Current gimbal azimuth in radians
  elevation: number;     // Current gimbal elevation in radians
  targetAzimuth: number; // True azimuth to beacon in radians
  targetElevation: number; // True elevation to beacon in radians
  trackingErrorMrad: number; // Pointing error in milliradians
  range: number;         // Distance to target in meters
  lockDuration: number;  // Seconds locked
  searchCoord: { x: number; y: number }; // Normalized [-1, 1] coordinate on camera HUD
  opticalLinkActive: boolean;
}

export class GimbalController {
  private state: GimbalState = "SEARCHING";
  private currentAzimuth = 0;   // radians relative to aircraft heading
  private currentElevation = 0; // radians relative to aircraft pitch

  private searchTime = 0;
  private acquireTimer = 0;
  private lockDuration = 0;

  // Mechanical specs
  private readonly maxSlewRate = (50 * Math.PI) / 180; // 50 deg/sec
  private readonly searchFov = (24 * Math.PI) / 180;   // 24 deg FOV for acquisition
  private readonly lockThreshold = (0.5 * Math.PI) / 180; // 0.5 deg (8.7 mrad) lock threshold

  constructor() {
    this.reset();
  }

  public reset(): void {
    this.state = "SEARCHING";
    this.currentAzimuth = 0;
    this.currentElevation = 0;
    this.searchTime = 0;
    this.acquireTimer = 0;
    this.lockDuration = 0;
  }

  public breakLock(): void {
    this.state = "SEARCHING";
    this.acquireTimer = 0;
    this.lockDuration = 0;
  }

  public forceSearch(): void {
    this.breakLock();
    this.searchTime = 0;
  }

  public forceLock(targetAz: number, targetEl: number): void {
    this.currentAzimuth = targetAz;
    this.currentElevation = targetEl;
    this.state = "LOCKED";
    this.lockDuration = 0.5;
  }

  public update(
    uavPos: Vector3D,
    uavYaw: number,
    uavPitch: number,
    beaconPos: Vector3D,
    dt: number
  ): GimbalTelemetry {
    // 1. Compute relative vector from UAV to Beacon in world space
    const dx = beaconPos.x - uavPos.x;
    const dy = beaconPos.y - uavPos.y;
    const dz = beaconPos.z - uavPos.z;
    const range = Math.hypot(dx, dy, dz);

    // World bearing (yaw) and elevation
    const worldBearing = Math.atan2(dx, -dz);
    const groundDistance = Math.hypot(dx, dz);
    const worldElevation = Math.atan2(dy, groundDistance);

    // Transform target bearing into aircraft relative body frame
    let targetAz = worldBearing - uavYaw;
    while (targetAz > Math.PI) targetAz -= 2 * Math.PI;
    while (targetAz < -Math.PI) targetAz += 2 * Math.PI;

    let targetEl = worldElevation - uavPitch;

    // Search pattern generation (Archimedean spiral)
    let searchCoord = { x: 0, y: 0 };

    if (this.state === "SEARCHING") {
      this.searchTime += dt;
      this.lockDuration = 0;

      // Expand spiral radius over a 6-second period, then repeat
      const cycleTime = 6.0;
      const progress = (this.searchTime % cycleTime) / cycleTime;
      const spiralRadius = ((20 * Math.PI) / 180) * Math.sqrt(progress);
      const spiralAngle = this.searchTime * 6.0; // spin frequency

      const scanAzOffset = spiralRadius * Math.cos(spiralAngle);
      const scanElOffset = spiralRadius * Math.sin(spiralAngle) * 0.75;

      // Approximate scan point towards the sector
      this.currentAzimuth += (targetAz + scanAzOffset - this.currentAzimuth) * Math.min(1.0, 4.0 * dt);
      this.currentElevation += (targetEl + scanElOffset - this.currentElevation) * Math.min(1.0, 4.0 * dt);

      // Normalized coordinates on HUD
      searchCoord = {
        x: Math.cos(spiralAngle) * progress,
        y: Math.sin(spiralAngle) * progress
      };

      // Check if target is inside camera acquisition cone
      const error = Math.hypot(this.currentAzimuth - targetAz, this.currentElevation - targetEl);
      if (error < this.searchFov) {
        this.state = "ACQUIRING";
        this.acquireTimer = 0;
      }
    } else if (this.state === "ACQUIRING") {
      // Slew toward target at maximum slew rate
      const errAz = targetAz - this.currentAzimuth;
      const errEl = targetEl - this.currentElevation;
      const totalErr = Math.hypot(errAz, errEl);

      const maxStep = this.maxSlewRate * dt;
      if (totalErr > 1e-4) {
        const step = Math.min(totalErr, maxStep);
        this.currentAzimuth += (errAz / totalErr) * step;
        this.currentElevation += (errEl / totalErr) * step;
      }

      searchCoord = {
        x: (errAz / this.searchFov) * 0.8,
        y: (errEl / this.searchFov) * 0.8
      };

      if (totalErr <= this.lockThreshold) {
        this.acquireTimer += dt;
        if (this.acquireTimer >= 0.25) {
          this.state = "LOCKED";
        }
      } else {
        this.acquireTimer = Math.max(0, this.acquireTimer - dt * 0.5);
      }
    } else if (this.state === "LOCKED") {
      // Continuous fine tracking
      this.lockDuration += dt;
      const trackSpeed = Math.min(1.0, 20.0 * dt);
      this.currentAzimuth += (targetAz - this.currentAzimuth) * trackSpeed;
      this.currentElevation += (targetEl - this.currentElevation) * trackSpeed;

      const totalErr = Math.hypot(targetAz - this.currentAzimuth, targetEl - this.currentElevation);
      // If error blows past threshold (e.g. radical maneuver)
      if (totalErr > this.searchFov * 1.5) {
        this.state = "SEARCHING";
        this.searchTime = 0;
      }
    }

    const currentErrRad = Math.hypot(targetAz - this.currentAzimuth, targetEl - this.currentElevation);
    const trackingErrorMrad = currentErrRad * 1000;

    return {
      state: this.state,
      azimuth: this.currentAzimuth,
      elevation: this.currentElevation,
      targetAzimuth: targetAz,
      targetElevation: targetEl,
      trackingErrorMrad,
      range,
      lockDuration: this.lockDuration,
      searchCoord,
      opticalLinkActive: this.state === "LOCKED"
    };
  }

  public getState(): GimbalState {
    return this.state;
  }
}
