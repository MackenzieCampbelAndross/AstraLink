import { Vector3D } from "../../types";

export type GimbalState = "SEARCHING" | "ACQUIRING" | "LOCKED" | "LOST";

export interface GimbalTelemetry {
  state: GimbalState;
  azimuth: number;          // Current gimbal azimuth in radians
  elevation: number;        // Current gimbal elevation in radians
  targetAzimuth: number;    // True azimuth to beacon in radians
  targetElevation: number;  // True elevation to beacon in radians
  trackingErrorMrad: number;// Pointing error in milliradians
  range: number;            // Distance to target in meters
  lockDuration: number;     // Seconds locked
  opticalLinkActive: boolean;
  searchTime: number;       // Current time spent searching in seconds
  searchDuration: number;   // Target discovery time (approx 5-10s)
  currentSector: string;    // Active search sector label
  signalStrength: number;   // 0.0 to 1.0 (noise floor vs carrier peak)
}

export class GimbalController {
  private state: GimbalState = "SEARCHING";
  private currentAzimuth = 0;   // radians relative to aircraft heading
  private currentElevation = 0; // radians relative to aircraft pitch

  private searchTime = 0;
  private searchDuration = 7.0; // 5 - 10 seconds to discover beacon
  private acquireTimer = 0;
  private lockDuration = 0;

  // Mechanical gimbal limits & rates
  private readonly maxSlewRate = (50 * Math.PI) / 180; // 50 deg/sec
  private readonly searchFov = (20 * Math.PI) / 180;   // 20 deg FOV for acquisition
  private readonly lockThreshold = (0.5 * Math.PI) / 180; // 0.5 deg (8.7 mrad) lock threshold

  constructor(customDuration?: number) {
    this.reset();
    if (customDuration !== undefined) {
      this.searchDuration = customDuration;
    }
  }

  public applyCameraCommand(panDeg: number, tiltDeg: number): void {
    // Convert pan/tilt degrees from Python CameraCommand to radians
    this.currentAzimuth = (panDeg * Math.PI) / 180.0;
    this.currentElevation = (tiltDeg * Math.PI) / 180.0;
  }

  public reset(): void {
    this.state = "SEARCHING";
    this.currentAzimuth = -0.3; // Start slightly offset to sweep naturally
    this.currentElevation = 0.05;
    this.searchTime = 0;
    this.acquireTimer = 0;
    this.lockDuration = 0;
    this.randomizeDiscoveryTime();
  }

  public setSearchDuration(seconds: number): void {
    this.searchDuration = Math.max(0.5, seconds);
  }

  public breakLock(): void {
    this.state = "SEARCHING";
    this.searchTime = 0;
    this.acquireTimer = 0;
    this.lockDuration = 0;
    this.randomizeDiscoveryTime();
    // Offset search away from last lock
    this.currentAzimuth -= 0.4;
  }

  public forceSearch(): void {
    this.breakLock();
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
    while (targetAz < -Math.PI) targetAz -= 2 * Math.PI;

    let targetEl = worldElevation - uavPitch;

    let activeSectorName = "RASTER SWEEP: SECTOR A";
    let signalStrength = 0.05 + Math.sin(this.searchTime * 15) * 0.03; // Low noise floor

    if (this.state === "SEARCHING") {
      this.searchTime += dt;
      this.lockDuration = 0;

      // Phase 1: Realistic continuous raster search across the sky (approx 5-10 seconds)
      if (this.searchTime < this.searchDuration) {
        // Natural raster scan: horizontal sweeps with progressive vertical step
        const t = this.searchTime;
        const scanAz = 0.55 * Math.sin(t * 0.85); // Sweeps left to right (-31° to +31°)
        const scanEl = 0.14 * Math.cos(t * 0.35) - 0.04; // Smooth elevation modulation (-10° to +6°)

        // Smoothly drive gimbal along the raster pattern
        const panRate = Math.min(1.0, 5.0 * dt);
        this.currentAzimuth += (scanAz - this.currentAzimuth) * panRate;
        this.currentElevation += (scanEl - this.currentElevation) * panRate;

        // Active sector text based on scan direction
        const sectorNum = Math.floor((t * 0.4) % 4) + 1;
        const dirText = scanAz > 0 ? "EASTBOUND" : "WESTBOUND";
        activeSectorName = `RASTER SCAN: SECTOR 0${sectorNum} [${dirText}]`;
      } else {
        // Phase 2: After 5-10s of systematic sweeping, the scan intersects the target bearing!
        activeSectorName = "TARGET INTERCEPT [BEACON SPOT]";

        const azDiff = targetAz - this.currentAzimuth;
        const elDiff = targetEl - this.currentElevation;

        // Slew toward target bearing
        const interceptSpeed = Math.min(1.0, 4.5 * dt);
        this.currentAzimuth += azDiff * interceptSpeed;
        this.currentElevation += elDiff * interceptSpeed;

        const error = Math.hypot(targetAz - this.currentAzimuth, targetEl - this.currentElevation);

        // When target beacon enters camera field of view, transition to ACQUIRING
        if (error < this.searchFov) {
          this.state = "ACQUIRING";
          this.acquireTimer = 0;
        }
      }
    } else if (this.state === "ACQUIRING") {
      activeSectorName = "BEACON DETECTED [COARSE ALIGN]";
      signalStrength = 0.65 + Math.sin(this.acquireTimer * 20) * 0.15;

      // Rapid closed-loop slew to center optical beacon into reticle
      const errAz = targetAz - this.currentAzimuth;
      const errEl = targetEl - this.currentElevation;
      const totalErr = Math.hypot(errAz, errEl);

      const maxStep = this.maxSlewRate * dt;
      if (totalErr > 1e-4) {
        const step = Math.min(totalErr, maxStep);
        this.currentAzimuth += (errAz / totalErr) * step;
        this.currentElevation += (errEl / totalErr) * step;
      }

      if (totalErr <= this.lockThreshold) {
        this.acquireTimer += dt;
        if (this.acquireTimer >= 0.2) {
          this.state = "LOCKED";
        }
      } else {
        this.acquireTimer = Math.max(0, this.acquireTimer - dt * 0.3);
      }
    } else if (this.state === "LOCKED") {
      activeSectorName = "OPTICAL CARRIER LOCKED";
      signalStrength = 0.96 + Math.sin(this.lockDuration * 5) * 0.03; // Peak signal
      this.lockDuration += dt;

      // Continuous fine optical lead tracking: gimbal holds target dead-center
      const trackSpeed = Math.min(1.0, 24.0 * dt);
      this.currentAzimuth += (targetAz - this.currentAzimuth) * trackSpeed;
      this.currentElevation += (targetEl - this.currentElevation) * trackSpeed;

      const totalErr = Math.hypot(targetAz - this.currentAzimuth, targetEl - this.currentElevation);
      if (totalErr > this.searchFov * 1.5) {
        this.breakLock();
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
      opticalLinkActive: this.state === "LOCKED",
      searchTime: this.searchTime,
      searchDuration: this.searchDuration,
      currentSector: activeSectorName,
      signalStrength
    };
  }

  public getState(): GimbalState {
    return this.state;
  }

  private randomizeDiscoveryTime(): void {
    this.searchDuration = 6.0 + Math.random() * 2.5;
  }
}
