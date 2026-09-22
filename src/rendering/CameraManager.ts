import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { UAVModel } from "../entities/UAVModel";
import { FlightAttitude } from "../simulation/flight/FlightKinematics";
import { GimbalTelemetry } from "../simulation/gimbal/GimbalController";
import { Vector3D } from "../types";

export type CameraViewMode = "POV" | "UAV1_CHASE" | "UAV2_CHASE" | "TACTICAL_ORBIT";

export class CameraManager {
  public readonly camera: THREE.PerspectiveCamera;
  public readonly controls: OrbitControls;

  private mode: CameraViewMode = "POV";
  private baseFov: number = 42;
  private zoomLevel: number = 1.0; // 1x to 8x

  private readonly tempVec1 = new THREE.Vector3();
  private readonly tempVec2 = new THREE.Vector3();

  constructor(container: HTMLElement) {
    const aspect = container.clientWidth / (container.clientHeight || 1);
    this.camera = new THREE.PerspectiveCamera(this.baseFov, aspect, 0.5, 50000);

    // OrbitControls for TACTICAL_ORBIT mode
    this.controls = new OrbitControls(this.camera, container);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.05;
    this.controls.maxDistance = 6000;
    this.controls.minDistance = 10;
    this.controls.enabled = false;
  }

  public setMode(mode: CameraViewMode): void {
    this.mode = mode;
    this.controls.enabled = mode === "TACTICAL_ORBIT";

    if (mode === "TACTICAL_ORBIT") {
      this.camera.position.set(300, 350, 450);
      this.controls.target.set(0, 180, 0);
      this.controls.update();
    }
  }

  public getMode(): CameraViewMode {
    return this.mode;
  }

  public setZoom(zoom: number): void {
    this.zoomLevel = Math.max(1.0, Math.min(8.0, zoom));
    this.camera.fov = this.baseFov / this.zoomLevel;
    this.camera.updateProjectionMatrix();
  }

  public getZoom(): number {
    return this.zoomLevel;
  }

  public update(
    uav1Pos: Vector3D,
    uav1Attitude: FlightAttitude,
    uav1Model: UAVModel,
    uav2Pos: Vector3D,
    gimbalTelemetry: GimbalTelemetry
  ): void {
    if (this.mode === "TACTICAL_ORBIT") {
      this.controls.update();
      return;
    }

    if (this.mode === "POV") {
      // 1. Position camera at the UAV 1 Gimbal Turret aperture
      uav1Model.getWorldGimbalPosition(this.tempVec1);
      this.camera.position.copy(this.tempVec1);

      // 2. Optical boresight orientation:
      // Total Azimuth = UAV heading (yaw) + Gimbal Azimuth
      // Total Elevation = UAV pitch + Gimbal Elevation
      const totalYaw = uav1Attitude.yaw + gimbalTelemetry.azimuth;
      const totalPitch = uav1Attitude.pitch + gimbalTelemetry.elevation;

      // Calculate forward look vector from spherical coordinates
      const forwardX = Math.sin(totalYaw) * Math.cos(totalPitch);
      const forwardY = Math.sin(totalPitch);
      const forwardZ = -Math.cos(totalYaw) * Math.cos(totalPitch);

      this.tempVec2.set(
        this.tempVec1.x + forwardX * 100,
        this.tempVec1.y + forwardY * 100,
        this.tempVec1.z + forwardZ * 100
      );

      this.camera.lookAt(this.tempVec2);
      // Include banking/roll into the optical sensor view
      this.camera.rotateZ(uav1Attitude.roll * 0.4);
    } else if (this.mode === "UAV1_CHASE") {
      // Third-person camera behind UAV 1
      const yaw = uav1Attitude.yaw;
      const dist = 38;
      const height = 12;

      // Position behind UAV based on heading
      this.camera.position.set(
        uav1Pos.x - Math.sin(yaw) * -dist,
        uav1Pos.y + height,
        uav1Pos.z - Math.cos(yaw) * dist
      );

      this.camera.lookAt(uav1Pos.x, uav1Pos.y + 2, uav1Pos.z);
    } else if (this.mode === "UAV2_CHASE") {
      // Third-person camera behind UAV 2
      const dist = 38;
      const height = 12;

      this.camera.position.set(
        uav2Pos.x,
        uav2Pos.y + height,
        uav2Pos.z + dist
      );

      this.camera.lookAt(uav2Pos.x, uav2Pos.y, uav2Pos.z);
    }
  }

  public handleResize(width: number, height: number): void {
    if (width === 0 || height === 0) return;
    this.camera.aspect = width / height;
    this.camera.updateProjectionMatrix();
  }
}
