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
  searchCoord: { x: number; y: number }; // Normalized [-1, 1] coordinate on camera HUD
  opticalLinkActive: boolean;
  searchTime: number;       // Current time spent searching in seconds
  searchDuration: number;   // Target discovery time (approx 5-10s)
  currentSector: string;    // Active search sector label
}

export class GimbalController {
  private state: GimbalState = "SEARCHING";
  private currentAzimuth = 0;   // radians relative to aircraft heading
  private currentElevation = 0; // radians relative to aircraft pitch

  private searchTime = 0;
  private searchDuration = 7.0; // 5 - 10 seconds to discover beacon
  private acquireTimer = 0;
  private lockDuration = 0;

  private currentSectorIndex = 0;
  private waypointTimer = 0;

  // Mechanical specs
  private readonly maxSlewRate = (45 * Math.PI) / 180; // 45 deg/sec
  private readonly searchFov = (18 * Math.PI) / 180;   // 18 deg FOV for acquisition
  private readonly lockThreshold = (0.5 * Math.PI) / 180; // 0.5 deg (8.7 mrad) lock threshold

  // Systematic pseudo-random search sectors across the airspace (azimuth, elevation)
  private readonly searchSectors: Array<{ az: number; el: number; name: string }> = [
    { az: -0.65, el: 0.18, name: "ALPHA-01 [LEFT HIGH]" },
    { az: -0.20, el: -0.25, name: "BRAVO-02 [CENTER LOW]" },
    { az: 0.60, el: 0.15, name: "CHARLIE-03 [RIGHT HIGH]" },
    { az: 0.35, el: -0.18, name: "DELTA-04 [RIGHT LOW]" },
    { az: -0.50, el: -0.05, name: "ECHO-05 [LEFT HORIZON]" },
    { az: 0.10, el: 0.28, name: "FOXTROT-06 [ZENITH SWEEP]" },
    { az: -0.30, el: 0.22, name: "GOLF-07 [LEFT APEX]" },
    { az: 0.50, el: -0.10, name: "HOTEL-08 [RIGHT HORIZON]" }
  ];

  constructor(customDuration?: number) {
    this.reset();
    if (customDuration !== undefined) {
      this.searchDuration = customDuration;
    }
  }

  public reset(): void {
    this.state = "SEARCHING";
    this.currentAzimuth = 0;
    this.currentElevation = 0;
    this.searchTime = 0;
    this.acquireTimer = 0;
    this.lockDuration = 0;
    this.currentSectorIndex = 0;
    this.waypointTimer = 0;
    // Set a realistic randomized discovery time between 6.0 and 8.5 seconds
    this.randomizeDiscoveryTime();
  }

  public setSearchDuration(seconds: number): void {
    this.searchDuration = Math.max(1.0, seconds);
  }

  public breakLock(): void {
    this.state = "SEARCHING";
    this.searchTime = 0;
    this.acquireTimer = 0;
    this.lockDuration = 0;
    this.randomizeDiscoveryTime();
    // Start search away from current lock position
    this.currentSectorIndex = (this.currentSectorIndex + 2) % this.searchSectors.length;
    this.waypointTimer = 0;
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
    while (targetAz < -Math.PI) targetAz += 2 * Math.PI;

    let targetEl = worldElevation - uavPitch;

    let searchCoord = { x: 0, y: 0 };
    let activeSectorName = "SEARCHING AIRSPACE";

    if (this.state === "SEARCHING") {
      this.searchTime += dt;
      this.waypointTimer += dt;
      this.lockDuration = 0;

      // Phase 1: Wide pseudo-random ordered search across the sky
      if (this.searchTime < this.searchDuration) {
        // Move between search sectors every 1.2 to 1.6 seconds
        const sectorDuration = 1.35;
        if (this.waypointTimer >= sectorDuration) {
          this.waypointTimer = 0;
          this.currentSectorIndex = (this.currentSectorIndex + 1) % this.searchSectors.length;
        }

        const sector = this.searchSectors[this.currentSectorIndex];
        activeSectorName = sector.name;

        // Smoothly steer gimbal towards current search sector
        const azDiff = sector.az - this.currentAzimuth;
        const elDiff = sector.el - this.currentElevation;
        const panRate = Math.min(1.0, 3.5 * dt);
        this.currentAzimuth += azDiff * panRate;
        this.currentElevation += elDiff * panRate;

        // Realistic sensor micro-dither / sweep motion
        const ditherPhase = this.searchTime * 12.0;
        const ditherAz = Math.sin(ditherPhase) * 0.015;
        const ditherEl = Math.cos(ditherPhase * 0.7) * 0.012;

        this.currentAzimuth += ditherAz;
        this.currentElevation += ditherEl;

        // HUD search scan coordinate
        searchCoord = {
          x: Math.sin(this.searchTime * 4.0) * 0.75,
          y: Math.cos(this.searchTime * 3.2) * 0.65
        };
      } else {
        // Phase 2: After 5-10s of systematic sweeping, the search sweeps into the target sector!
        activeSectorName = "TARGET SECTOR [INTERCEPT]";
        const azDiff = targetAz - this.currentAzimuth;
        const elDiff = targetEl - this.currentElevation;

        // Sweep toward target bearing
        const interceptSpeed = Math.min(1.0, 4.5 * dt);
        this.currentAzimuth += azDiff * interceptSpeed;
        this.currentElevation += elDiff * interceptSpeed;

        const error = Math.hypot(targetAz - this.currentAzimuth, targetEl - this.currentElevation);

        // When target beacon enters camera field of view, transition to ACQUIRING
        if (error < this.searchFov) {
          this.state = "ACQUIRING";
          this.acquireTimer = 0;
        }

        searchCoord = {
          x: Math.min(1.0, Math.max(-1.0, azDiff / this.searchFov)),
          y: Math.min(1.0, Math.max(-1.0, elDiff / this.searchFov))
        };
      }
    } else if (this.state === "ACQUIRING") {
      activeSectorName = "BEACON DETECTED [COARSE ALIGN]";
      // Rapid slew to center optical beacon
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
        x: (errAz / this.searchFov) * 0.6,
        y: (errEl / this.searchFov) * 0.6
      };

      if (totalErr <= this.lockThreshold) {
        this.acquireTimer += dt;
        if (this.acquireTimer >= 0.2) {
          this.state = "LOCKED";
        }
      } else {
        this.acquireTimer = Math.max(0, this.acquireTimer - dt * 0.4);
      }
    } else if (this.state === "LOCKED") {
      activeSectorName = "CARRIER LOCKED [TRACKING]";
      this.lockDuration += dt;

      // Fine continuous optical lead tracking
      const trackSpeed = Math.min(1.0, 22.0 * dt);
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
      searchCoord,
      opticalLinkActive: this.state === "LOCKED",
      searchTime: this.searchTime,
      searchDuration: this.searchDuration,
      currentSector: activeSectorName
    };
  }

  public getState(): GimbalState {
    return this.state;
  }

  private randomizeDiscoveryTime(): void {
    // Approx 5 to 9 seconds to find the target beacon
    this.searchDuration = 6.0 + (Math.sin(this.searchTime * 17.3) * 0.5 + 0.5) * 3.0;
  }
}
