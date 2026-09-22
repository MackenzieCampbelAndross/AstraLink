import * as THREE from "three";
import { Vector3D, VisualizationConfig } from "../types";

export class DebugRenderer {
  private readonly maxPoints: number;
  private readonly positions: Float32Array;
  private readonly geometry: THREE.BufferGeometry;
  private readonly line: THREE.Line;
  private count: number = 0;
  private isVisible: boolean = true;

  constructor(scene: THREE.Scene, config?: VisualizationConfig) {
    this.maxPoints = config?.trajectoryLength ?? 600;
    this.isVisible = config?.showTrajectory ?? true;

    this.positions = new Float32Array(this.maxPoints * 3);
    this.geometry = new THREE.BufferGeometry();
    this.geometry.setAttribute("position", new THREE.BufferAttribute(this.positions, 3));
    this.geometry.setDrawRange(0, 0);

    const material = new THREE.LineBasicMaterial({
      color: 0x00ffcc,
      transparent: true,
      opacity: 0.75,
      linewidth: 2
    });

    this.line = new THREE.Line(this.geometry, material);
    this.line.frustumCulled = false;
    this.line.visible = this.isVisible;
    scene.add(this.line);
  }

  public addPoint(pos: Vector3D): void {
    if (this.count < this.maxPoints) {
      const idx = this.count * 3;
      this.positions[idx] = pos.x;
      this.positions[idx + 1] = pos.y;
      this.positions[idx + 2] = pos.z;
      this.count++;
    } else {
      // Shift array left by 1 vertex (3 floats) and append new point at end
      this.positions.copyWithin(0, 3);
      const lastIdx = (this.maxPoints - 1) * 3;
      this.positions[lastIdx] = pos.x;
      this.positions[lastIdx + 1] = pos.y;
      this.positions[lastIdx + 2] = pos.z;
    }

    this.geometry.attributes.position.needsUpdate = true;
    this.geometry.setDrawRange(0, this.count);
  }

  public clear(): void {
    this.count = 0;
    this.geometry.setDrawRange(0, 0);
    this.geometry.attributes.position.needsUpdate = true;
  }

  public setVisible(visible: boolean): void {
    this.isVisible = visible;
    this.line.visible = visible;
  }
}
