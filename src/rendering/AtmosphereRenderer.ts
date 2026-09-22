import * as THREE from "three";
import { Sky } from "three/examples/jsm/objects/Sky.js";

export class AtmosphereRenderer {
  private readonly sky: Sky;
  private readonly sun: THREE.Vector3;
  private readonly dirLight: THREE.DirectionalLight;
  private readonly groundMesh: THREE.Mesh;
  private readonly cloudGroup: THREE.Group;

  constructor(scene: THREE.Scene) {
    // 1. Three.js Sky Shader
    this.sky = new Sky();
    this.sky.scale.setScalar(450000);
    scene.add(this.sky);

    this.sun = new THREE.Vector3();

    const uniforms = this.sky.material.uniforms;
    uniforms["turbidity"].value = 3.2;
    uniforms["rayleigh"].value = 2.4;
    uniforms["mieCoefficient"].value = 0.005;
    uniforms["mieDirectionalG"].value = 0.75;

    // Sun angle (elevation ~32 degrees, azimuth -50 degrees for natural daylight aerial atmosphere)
    const phi = THREE.MathUtils.degToRad(90 - 32);
    const theta = THREE.MathUtils.degToRad(-50);
    this.sun.setFromSphericalCoords(1, phi, theta);
    uniforms["sunPosition"].value.copy(this.sun);

    // 2. Realistic Sun Directional Light
    this.dirLight = new THREE.DirectionalLight(0xfff7ea, 1.6);
    this.dirLight.position.copy(this.sun).multiplyScalar(2000);
    scene.add(this.dirLight);

    // Natural atmospheric ambient fill
    const hemiLight = new THREE.HemisphereLight(0x89b2db, 0x3d4a3e, 0.85);
    scene.add(hemiLight);

    // 3. Vast Landscape / Earth Aerial Terrain
    const groundGeo = new THREE.PlaneGeometry(40000, 40000, 80, 80);
    const pos = groundGeo.attributes.position as THREE.BufferAttribute;
    for (let i = 0; i < pos.count; i++) {
      const x = pos.getX(i);
      const y = pos.getY(i);
      const elevation = Math.sin(x * 0.0006) * Math.cos(y * 0.0006) * 90 + Math.sin(x * 0.0018) * 35;
      pos.setZ(i, elevation);
    }
    groundGeo.computeVertexNormals();

    const groundMat = new THREE.MeshStandardMaterial({
      color: 0x3d493a, // Natural olive/earth landscape
      roughness: 0.88,
      metalness: 0.05
    });
    this.groundMesh = new THREE.Mesh(groundGeo, groundMat);
    this.groundMesh.rotation.x = -Math.PI / 2;
    this.groundMesh.position.y = -15;
    scene.add(this.groundMesh);

    // Subtle tactical altitude grid
    const grid = new THREE.GridHelper(30000, 300, 0x00f0ff, 0x224035);
    (grid.material as THREE.Material).transparent = true;
    (grid.material as THREE.Material).opacity = 0.12;
    grid.position.y = 0;
    scene.add(grid);

    // 4. Low-altitude and mid-altitude clouds
    this.cloudGroup = new THREE.Group();
    const cloudGeo = new THREE.PlaneGeometry(1600, 900);
    const cloudMat = new THREE.MeshBasicMaterial({
      color: 0xf5f8fc,
      transparent: true,
      opacity: 0.14,
      depthWrite: false
    });

    for (let i = 0; i < 20; i++) {
      const cloud = new THREE.Mesh(cloudGeo, cloudMat);
      cloud.rotation.x = -Math.PI / 2;
      cloud.position.set(
        (Math.random() - 0.5) * 12000,
        70 + (Math.random() - 0.5) * 50,
        (Math.random() - 0.5) * 12000
      );
      cloud.scale.set(1 + Math.random(), 1 + Math.random(), 1);
      this.cloudGroup.add(cloud);
    }
    scene.add(this.cloudGroup);
  }

  public update(dt: number): void {
    // Subtle cloud drift
    for (const cloud of this.cloudGroup.children) {
      cloud.position.x += 12 * dt;
      if (cloud.position.x > 6000) {
        cloud.position.x = -6000;
      }
    }
  }
}
