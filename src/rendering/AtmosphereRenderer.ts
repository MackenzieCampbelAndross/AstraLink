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
    uniforms["turbidity"].value = 2.0;
    uniforms["rayleigh"].value = 1.5;
    uniforms["mieCoefficient"].value = 0.004;
    uniforms["mieDirectionalG"].value = 0.82;

    // Sun angle (elevation ~18 degrees, azimuth -60 degrees for dramatic golden hour / tactical lighting)
    const phi = THREE.MathUtils.degToRad(90 - 18);
    const theta = THREE.MathUtils.degToRad(-60);
    this.sun.setFromSphericalCoords(1, phi, theta);
    uniforms["sunPosition"].value.copy(this.sun);

    // 2. Realistic Sun Directional Light
    this.dirLight = new THREE.DirectionalLight(0xfff4e0, 2.2);
    this.dirLight.position.copy(this.sun).multiplyScalar(2000);
    scene.add(this.dirLight);

    // Ambient sky fill light
    const hemiLight = new THREE.HemisphereLight(0x7090b0, 0x303540, 1.0);
    scene.add(hemiLight);

    // 3. Vast Landscape / Ground Terrain
    const groundGeo = new THREE.PlaneGeometry(30000, 30000, 64, 64);
    // Subtle elevation perturbation
    const pos = groundGeo.attributes.position as THREE.BufferAttribute;
    for (let i = 0; i < pos.count; i++) {
      const x = pos.getX(i);
      const y = pos.getY(i);
      const elevation = Math.sin(x * 0.0008) * Math.cos(y * 0.0008) * 80 + Math.sin(x * 0.002) * 20;
      pos.setZ(i, elevation);
    }
    groundGeo.computeVertexNormals();

    const groundMat = new THREE.MeshStandardMaterial({
      color: 0x1f2b37,
      roughness: 0.9,
      metalness: 0.1,
      wireframe: false
    });
    this.groundMesh = new THREE.Mesh(groundGeo, groundMat);
    this.groundMesh.rotation.x = -Math.PI / 2;
    this.groundMesh.position.y = -20;
    scene.add(this.groundMesh);

    // Coordinate grid on ground
    const grid = new THREE.GridHelper(20000, 200, 0x00f0ff, 0x163459);
    (grid.material as THREE.Material).transparent = true;
    (grid.material as THREE.Material).opacity = 0.25;
    grid.position.y = 0;
    scene.add(grid);

    // 4. Low Atmosphere Cloud Deck
    this.cloudGroup = new THREE.Group();
    const cloudGeo = new THREE.PlaneGeometry(1200, 800);
    const cloudMat = new THREE.MeshBasicMaterial({
      color: 0xeef4fa,
      transparent: true,
      opacity: 0.18,
      depthWrite: false
    });

    for (let i = 0; i < 16; i++) {
      const cloud = new THREE.Mesh(cloudGeo, cloudMat);
      cloud.rotation.x = -Math.PI / 2;
      cloud.position.set(
        (Math.random() - 0.5) * 8000,
        60 + (Math.random() - 0.5) * 40,
        (Math.random() - 0.5) * 8000
      );
      cloud.scale.set(1 + Math.random(), 1 + Math.random(), 1);
      this.cloudGroup.add(cloud);
    }
    scene.add(this.cloudGroup);
  }

  public update(dt: number): void {
    // Subtle cloud drift
    for (const cloud of this.cloudGroup.children) {
      cloud.position.x += 10 * dt;
      if (cloud.position.x > 4000) {
        cloud.position.x = -4000;
      }
    }
  }
}
