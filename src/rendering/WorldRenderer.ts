import * as THREE from "three";
import { WorldConfig } from "../types";

export class WorldRenderer {
  private readonly group: THREE.Group;

  constructor(scene: THREE.Scene, config: WorldConfig) {
    this.group = new THREE.Group();
    this.group.name = "WorldEnvironment";

    // 1. Grid
    const gridSize = Math.max(config.width, config.depth);
    const gridDivisions = Math.round(gridSize / 50);
    const gridHelper = new THREE.GridHelper(gridSize, gridDivisions, 0x1f4068, 0x0f2137);
    gridHelper.position.y = 0;
    this.group.add(gridHelper);

    // 2. Coordinate Axes Helper (Length 100)
    const axesHelper = new THREE.AxesHelper(120);
    (axesHelper.material as THREE.Material).depthTest = false;
    axesHelper.renderOrder = 1;
    this.group.add(axesHelper);

    // 3. World Boundary Box (Wireframe)
    const boxGeo = new THREE.BoxGeometry(config.width, config.height, config.depth);
    const wireframeGeo = new THREE.WireframeGeometry(boxGeo);
    const wireframeMat = new THREE.LineBasicMaterial({
      color: 0x163459,
      transparent: true,
      opacity: 0.35
    });
    const boundingBoxLine = new THREE.LineSegments(wireframeGeo, wireframeMat);
    boundingBoxLine.position.set(0, config.height / 2, 0);
    this.group.add(boundingBoxLine);

    scene.add(this.group);
  }

  public setVisible(visible: boolean): void {
    this.group.visible = visible;
  }
}
