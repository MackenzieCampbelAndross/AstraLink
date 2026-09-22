import * as THREE from "three";
import { TargetState, TerminalState } from "../types";

export class TerminalRenderer {
  private readonly terminal1Mesh: THREE.Group;
  private readonly terminal2Mesh: THREE.Group;
  private readonly losLine: THREE.Line;
  private readonly losGeometry: THREE.BufferGeometry;

  constructor(scene: THREE.Scene, initialT1: TerminalState, initialT2: TargetState) {
    // 1. Terminal 1 (Reference Ground / Base Terminal)
    this.terminal1Mesh = this.buildTerminal1Mesh();
    this.terminal1Mesh.position.set(initialT1.position.x, initialT1.position.y, initialT1.position.z);
    scene.add(this.terminal1Mesh);

    // 2. Terminal 2 (Remote Moving Terminal)
    this.terminal2Mesh = this.buildTerminal2Mesh();
    this.terminal2Mesh.position.set(initialT2.position.x, initialT2.position.y, initialT2.position.z);
    scene.add(this.terminal2Mesh);

    // 3. Line of Sight (LOS) vector between T1 and T2
    this.losGeometry = new THREE.BufferGeometry();
    const positions = new Float32Array([
      initialT1.position.x, initialT1.position.y + 10, initialT1.position.z,
      initialT2.position.x, initialT2.position.y, initialT2.position.z
    ]);
    this.losGeometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    const losMat = new THREE.LineDashedMaterial({
      color: 0x00f0ff,
      dashSize: 8,
      gapSize: 6,
      transparent: true,
      opacity: 0.4
    });
    this.losLine = new THREE.Line(this.losGeometry, losMat);
    this.losLine.computeLineDistances();
    scene.add(this.losLine);
  }

  public update(t1: TerminalState, t2: TargetState): void {
    // Update Terminal 1
    this.terminal1Mesh.position.set(t1.position.x, t1.position.y, t1.position.z);

    // Make Terminal 1 optical aperture point towards Terminal 2
    this.terminal1Mesh.lookAt(t2.position.x, t2.position.y, t2.position.z);

    // Update Terminal 2
    this.terminal2Mesh.position.set(t2.position.x, t2.position.y, t2.position.z);
    this.terminal2Mesh.rotation.set(t2.orientation.x, t2.orientation.y, t2.orientation.z, "YXZ");

    // Update LOS Line
    const posAttr = this.losGeometry.attributes.position as THREE.BufferAttribute;
    const array = posAttr.array as Float32Array;
    array[0] = t1.position.x;
    array[1] = t1.position.y + 8;
    array[2] = t1.position.z;
    array[3] = t2.position.x;
    array[4] = t2.position.y;
    array[5] = t2.position.z;
    posAttr.needsUpdate = true;
    this.losLine.computeLineDistances();
  }

  public setLosVisible(visible: boolean): void {
    this.losLine.visible = visible;
  }

  private buildTerminal1Mesh(): THREE.Group {
    const group = new THREE.Group();
    group.name = "Terminal1_Reference";

    // Base pedestal
    const pedestalGeo = new THREE.CylinderGeometry(14, 18, 6, 24);
    const pedestalMat = new THREE.MeshStandardMaterial({
      color: 0x1c2b3d,
      roughness: 0.6,
      metalness: 0.4
    });
    const pedestal = new THREE.Mesh(pedestalGeo, pedestalMat);
    pedestal.position.y = 3;
    group.add(pedestal);

    // Main housing
    const bodyGeo = new THREE.BoxGeometry(16, 12, 16);
    const bodyMat = new THREE.MeshStandardMaterial({
      color: 0x243b55,
      roughness: 0.4,
      metalness: 0.6
    });
    const body = new THREE.Mesh(bodyGeo, bodyMat);
    body.position.y = 12;
    group.add(body);

    // Optical aperture barrel
    const apertureGeo = new THREE.CylinderGeometry(5, 6, 10, 20);
    const apertureMat = new THREE.MeshStandardMaterial({
      color: 0x0b121e,
      roughness: 0.2,
      metalness: 0.8
    });
    const aperture = new THREE.Mesh(apertureGeo, apertureMat);
    aperture.rotation.x = Math.PI / 2;
    aperture.position.set(0, 12, 10);
    group.add(aperture);

    // Cyan aperture lens
    const lensGeo = new THREE.CircleGeometry(4.5, 24);
    const lensMat = new THREE.MeshBasicMaterial({
      color: 0x00d2ff,
      side: THREE.DoubleSide
    });
    const lens = new THREE.Mesh(lensGeo, lensMat);
    lens.position.set(0, 12, 15.1);
    group.add(lens);

    return group;
  }

  private buildTerminal2Mesh(): THREE.Group {
    const group = new THREE.Group();
    group.name = "Terminal2_Remote";

    // Aerodynamic / satellite pod body
    const bodyGeo = new THREE.BoxGeometry(14, 10, 24);
    const bodyMat = new THREE.MeshStandardMaterial({
      color: 0xd6e4ff,
      roughness: 0.3,
      metalness: 0.7
    });
    const body = new THREE.Mesh(bodyGeo, bodyMat);
    group.add(body);

    // Optical aperture facing forward (-Z)
    const apertureGeo = new THREE.CylinderGeometry(4, 4.8, 6, 16);
    const apertureMat = new THREE.MeshStandardMaterial({
      color: 0x111b27,
      roughness: 0.3,
      metalness: 0.8
    });
    const aperture = new THREE.Mesh(apertureGeo, apertureMat);
    aperture.rotation.x = Math.PI / 2;
    aperture.position.set(0, 0, -14);
    group.add(aperture);

    // Orientation heading arrow (Forward along -Z)
    const arrowConeGeo = new THREE.ConeGeometry(3, 8, 12);
    const arrowMat = new THREE.MeshBasicMaterial({ color: 0xff3366 });
    const arrowCone = new THREE.Mesh(arrowConeGeo, arrowMat);
    arrowCone.rotation.x = -Math.PI / 2;
    arrowCone.position.set(0, 8, -12);
    group.add(arrowCone);

    return group;
  }
}
