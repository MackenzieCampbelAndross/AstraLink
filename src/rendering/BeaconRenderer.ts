import * as THREE from "three";
import { BeaconState } from "../types";

export class BeaconRenderer {
  private readonly group: THREE.Group;
  private readonly coreMesh: THREE.Mesh;
  private readonly haloMesh: THREE.Mesh;
  private readonly pointLight: THREE.PointLight;
  private readonly material: THREE.MeshBasicMaterial;
  private readonly haloMaterial: THREE.MeshBasicMaterial;

  constructor(scene: THREE.Scene, initialState: BeaconState) {
    this.group = new THREE.Group();
    this.group.name = "OpticalBeacon_Visual";

    const size = initialState.size;

    // 1. Core emissive sphere
    const coreGeo = new THREE.SphereGeometry(size * 0.8, 24, 24);
    this.material = new THREE.MeshBasicMaterial({
      color: 0x00ffff
    });
    this.coreMesh = new THREE.Mesh(coreGeo, this.material);
    this.group.add(this.coreMesh);

    // 2. Halo glow sphere
    const haloGeo = new THREE.SphereGeometry(size * 2.2, 20, 20);
    this.haloMaterial = new THREE.MeshBasicMaterial({
      color: 0x00eeff,
      transparent: true,
      opacity: 0.35,
      blending: THREE.AdditiveBlending,
      side: THREE.BackSide
    });
    this.haloMesh = new THREE.Mesh(haloGeo, this.haloMaterial);
    this.group.add(this.haloMesh);

    // 3. Point light for illuminating surroundings
    this.pointLight = new THREE.PointLight(0x00ffff, initialState.brightness * 2.5, 300, 1.5);
    this.group.add(this.pointLight);

    this.group.position.set(
      initialState.worldPosition.x,
      initialState.worldPosition.y,
      initialState.worldPosition.z
    );

    scene.add(this.group);
  }

  public update(state: BeaconState): void {
    this.group.visible = state.enabled;
    if (!state.enabled) return;

    this.group.position.set(
      state.worldPosition.x,
      state.worldPosition.y,
      state.worldPosition.z
    );

    const b = state.brightness;
    this.pointLight.intensity = b * 2.5;
    this.haloMaterial.opacity = Math.min(0.8, 0.35 * b);
  }

  public setVisible(visible: boolean): void {
    this.group.visible = visible;
  }
}
