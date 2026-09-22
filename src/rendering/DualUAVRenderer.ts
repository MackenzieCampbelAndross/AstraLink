import * as THREE from "three";
import { UAVModel } from "../entities/UAVModel";
import { FlightAttitude } from "../simulation/flight/FlightKinematics";
import { GimbalTelemetry } from "../simulation/gimbal/GimbalController";
import { Vector3D } from "../types";

export class DualUAVRenderer {
  public readonly uav1: UAVModel;
  public readonly uav2: UAVModel;

  private readonly laserGeometry: THREE.BufferGeometry;
  private readonly laserLine: THREE.Line;
  private readonly laserCoreLine: THREE.Line;

  constructor(scene: THREE.Scene) {
    // 1. Transmitter UAV 1
    this.uav1 = new UAVModel({
      name: "UAV1_Transmitter",
      isTransmitter: true,
      baseColor: 0x1d293d,
      accentColor: 0x00f0ff
    });
    scene.add(this.uav1.group);

    // 2. Receiver UAV 2 (Target with Optical Beacon)
    this.uav2 = new UAVModel({
      name: "UAV2_Receiver_Target",
      isTransmitter: false,
      baseColor: 0x4a5568,
      accentColor: 0x00ff88
    });
    scene.add(this.uav2.group);

    // 3. Optical Laser Communication Beam (Active when LOCKED)
    this.laserGeometry = new THREE.BufferGeometry();
    const pos = new Float32Array(6);
    this.laserGeometry.setAttribute("position", new THREE.BufferAttribute(pos, 3));

    // Outer optical glow beam
    const laserMat = new THREE.LineBasicMaterial({
      color: 0x00ffcc,
      transparent: true,
      opacity: 0.85,
      blending: THREE.AdditiveBlending
    });
    this.laserLine = new THREE.Line(this.laserGeometry, laserMat);
    this.laserLine.visible = false;
    scene.add(this.laserLine);

    // Core high-intensity laser line
    const coreMat = new THREE.LineBasicMaterial({
      color: 0xffffff,
      transparent: true,
      opacity: 0.95,
      blending: THREE.AdditiveBlending
    });
    this.laserCoreLine = new THREE.Line(this.laserGeometry, coreMat);
    this.laserCoreLine.visible = false;
    scene.add(this.laserCoreLine);
  }

  public update(
    uav1Pos: Vector3D,
    uav1Att: FlightAttitude,
    uav2Pos: Vector3D,
    uav2Att: FlightAttitude,
    gimbalTelemetry: GimbalTelemetry,
    dt: number
  ): void {
    // Update UAV 1 position and physical attitude
    this.uav1.setPositionAndAttitude(uav1Pos, uav1Att.pitch, uav1Att.yaw, uav1Att.roll);
    this.uav1.setGimbalOrientation(gimbalTelemetry.azimuth, gimbalTelemetry.elevation);
    this.uav1.update(dt);

    // Update UAV 2 position and physical attitude
    this.uav2.setPositionAndAttitude(uav2Pos, uav2Att.pitch, uav2Att.yaw, uav2Att.roll);
    this.uav2.update(dt);

    // Update Optical Laser Beam
    if (gimbalTelemetry.opticalLinkActive) {
      this.laserLine.visible = true;
      this.laserCoreLine.visible = true;

      const posAttr = this.laserGeometry.attributes.position as THREE.BufferAttribute;
      const array = posAttr.array as Float32Array;

      // Start: UAV 1 Gimbal Turret aperture
      const startPos = new THREE.Vector3();
      this.uav1.getWorldGimbalPosition(startPos);
      array[0] = startPos.x;
      array[1] = startPos.y;
      array[2] = startPos.z;

      // End: UAV 2 Beacon Position
      array[3] = uav2Pos.x;
      array[4] = uav2Pos.y + 1.8;
      array[5] = uav2Pos.z;

      posAttr.needsUpdate = true;
    } else {
      this.laserLine.visible = false;
      this.laserCoreLine.visible = false;
    }
  }
}
