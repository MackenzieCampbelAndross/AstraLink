import * as THREE from "three";
import { Vector3D } from "../types";

export interface UAVModelOptions {
  name: string;
  isTransmitter: boolean;
  baseColor?: number;
  accentColor?: number;
}

export class UAVModel {
  public readonly group: THREE.Group;
  public readonly gimbalTurret: THREE.Group;
  public readonly gimbalAperture: THREE.Mesh;
  public readonly propeller: THREE.Group;
  public readonly beaconLight?: THREE.PointLight;
  public readonly beaconMesh?: THREE.Mesh;

  private navLightTimer = 0;
  private navLights: THREE.PointLight[] = [];

  constructor(options: UAVModelOptions) {
    this.group = new THREE.Group();
    this.group.name = options.name;

    const bodyMat = new THREE.MeshStandardMaterial({
      color: options.baseColor ?? (options.isTransmitter ? 0x24334a : 0x5a6577),
      roughness: 0.35,
      metalness: 0.5
    });

    const darkMat = new THREE.MeshStandardMaterial({
      color: 0x141b24,
      roughness: 0.5,
      metalness: 0.7
    });

    const accentMat = new THREE.MeshStandardMaterial({
      color: options.accentColor ?? (options.isTransmitter ? 0x00f0ff : 0xffaa00),
      roughness: 0.3,
      metalness: 0.4
    });

    // 1. Fuselage
    const fuselageGroup = new THREE.Group();

    // Main central body (tapered cylinder / hull)
    const hullGeo = new THREE.CylinderGeometry(1.6, 1.0, 16, 16);
    hullGeo.rotateX(Math.PI / 2);
    const hull = new THREE.Mesh(hullGeo, bodyMat);
    hull.scale.set(1.1, 0.9, 1.0);
    fuselageGroup.add(hull);

    // Nose dome (front radome at -Z)
    const noseGeo = new THREE.SphereGeometry(1.6, 16, 16);
    noseGeo.scale(1.1, 0.9, 1.8);
    const nose = new THREE.Mesh(noseGeo, bodyMat);
    nose.position.set(0, 0, -8);
    fuselageGroup.add(nose);

    // Avionics / satellite comms upper hump
    const humpGeo = new THREE.SphereGeometry(1.2, 16, 16);
    humpGeo.scale(0.9, 0.7, 3.5);
    const hump = new THREE.Mesh(humpGeo, darkMat);
    hump.position.set(0, 1.3, -2);
    fuselageGroup.add(hump);

    this.group.add(fuselageGroup);

    // 2. High-Aspect Ratio Wings
    const wingSpan = 32;
    const wingChord = 2.4;
    const wingGeo = new THREE.BoxGeometry(wingSpan, 0.25, wingChord);
    // Taper wing towards tips
    const wing = new THREE.Mesh(wingGeo, bodyMat);
    wing.position.set(0, 0.4, -0.5);
    this.group.add(wing);

    // Wingtips / winglets
    const wingletGeo = new THREE.BoxGeometry(0.2, 2.0, 1.8);
    const leftWinglet = new THREE.Mesh(wingletGeo, accentMat);
    leftWinglet.position.set(-wingSpan / 2, 1.2, -0.5);
    leftWinglet.rotation.z = -0.15;
    this.group.add(leftWinglet);

    const rightWinglet = new THREE.Mesh(wingletGeo, accentMat);
    rightWinglet.position.set(wingSpan / 2, 1.2, -0.5);
    rightWinglet.rotation.z = 0.15;
    this.group.add(rightWinglet);

    // 3. Inverted V-Tail Fins
    const tailFinGeo = new THREE.BoxGeometry(0.2, 5.0, 2.0);

    const leftTail = new THREE.Mesh(tailFinGeo, bodyMat);
    leftTail.position.set(-1.8, 1.8, 8);
    leftTail.rotation.z = -Math.PI / 4;
    leftTail.rotation.x = -0.3;
    this.group.add(leftTail);

    const rightTail = new THREE.Mesh(tailFinGeo, bodyMat);
    rightTail.position.set(1.8, 1.8, 8);
    rightTail.rotation.z = Math.PI / 4;
    rightTail.rotation.x = -0.3;
    this.group.add(rightTail);

    // 4. Rear Engine Cowling & Pusher Propeller
    const engineCowlingGeo = new THREE.CylinderGeometry(0.9, 1.1, 3.0, 16);
    engineCowlingGeo.rotateX(Math.PI / 2);
    const engineCowling = new THREE.Mesh(engineCowlingGeo, darkMat);
    engineCowling.position.set(0, 0.3, 8.5);
    this.group.add(engineCowling);

    this.propeller = new THREE.Group();
    this.propeller.position.set(0, 0.3, 10.2);

    const propSpinnerGeo = new THREE.ConeGeometry(0.5, 1.2, 12);
    propSpinnerGeo.rotateX(-Math.PI / 2);
    const spinner = new THREE.Mesh(propSpinnerGeo, accentMat);
    this.propeller.add(spinner);

    const propBladeGeo = new THREE.BoxGeometry(4.8, 0.35, 0.08);
    const propBlade1 = new THREE.Mesh(propBladeGeo, darkMat);
    this.propeller.add(propBlade1);

    const propBlade2 = new THREE.Mesh(propBladeGeo, darkMat);
    propBlade2.rotation.z = Math.PI / 2;
    this.propeller.add(propBlade2);

    this.group.add(this.propeller);

    // 5. Chin/Belly Optical Gimbal Turret
    this.gimbalTurret = new THREE.Group();
    // Mounted under the chin forward: (0, -1.2, -6.5)
    this.gimbalTurret.position.set(0, -1.2, -6.5);

    const turretBaseGeo = new THREE.CylinderGeometry(1.1, 1.1, 0.4, 16);
    const turretBase = new THREE.Mesh(turretBaseGeo, darkMat);
    this.gimbalTurret.add(turretBase);

    const sphereGeo = new THREE.SphereGeometry(1.2, 20, 20);
    const sphere = new THREE.Mesh(sphereGeo, bodyMat);
    sphere.position.y = -0.6;
    this.gimbalTurret.add(sphere);

    // Aperture window
    const apertureGeo = new THREE.CylinderGeometry(0.55, 0.65, 0.6, 16);
    apertureGeo.rotateX(Math.PI / 2);
    const apertureMat = new THREE.MeshBasicMaterial({
      color: options.isTransmitter ? 0x00f0ff : 0x00ff88
    });
    this.gimbalAperture = new THREE.Mesh(apertureGeo, apertureMat);
    this.gimbalAperture.position.set(0, -0.6, -1.1);
    this.gimbalTurret.add(this.gimbalAperture);

    this.group.add(this.gimbalTurret);

    // 6. Navigation Strobe Lights
    const redLight = new THREE.PointLight(0xff0033, 1.2, 40);
    redLight.position.set(-wingSpan / 2, 0.5, -0.5);
    this.group.add(redLight);
    this.navLights.push(redLight);

    const greenLight = new THREE.PointLight(0x00ff44, 1.2, 40);
    greenLight.position.set(wingSpan / 2, 0.5, -0.5);
    this.group.add(greenLight);
    this.navLights.push(greenLight);

    // 7. If Receiver UAV: Mount High-Intensity Optical Beacon
    if (!options.isTransmitter) {
      const beaconMount = new THREE.Group();
      beaconMount.position.set(0, 1.8, 2);

      const beaconSphereGeo = new THREE.SphereGeometry(1.5, 24, 24);
      const beaconMat = new THREE.MeshBasicMaterial({
        color: 0x00ffff
      });
      this.beaconMesh = new THREE.Mesh(beaconSphereGeo, beaconMat);
      beaconMount.add(this.beaconMesh);

      // Glow halo
      const haloGeo = new THREE.SphereGeometry(3.5, 16, 16);
      const haloMat = new THREE.MeshBasicMaterial({
        color: 0x00ffff,
        transparent: true,
        opacity: 0.45,
        blending: THREE.AdditiveBlending,
        side: THREE.BackSide
      });
      const halo = new THREE.Mesh(haloGeo, haloMat);
      beaconMount.add(halo);

      this.beaconLight = new THREE.PointLight(0x00ffff, 4, 300, 1.5);
      beaconMount.add(this.beaconLight);

      this.group.add(beaconMount);
    }
  }

  public update(dt: number): void {
    // Spin propeller
    this.propeller.rotation.z += 40 * dt;

    // Strobe navigation lights
    this.navLightTimer += dt;
    const strobe = Math.sin(this.navLightTimer * 8) > 0.3;
    for (const light of this.navLights) {
      light.intensity = strobe ? 2.5 : 0.2;
    }

    if (this.beaconLight) {
      // Subtle optical pulse on the beacon
      this.beaconLight.intensity = 3.5 + Math.sin(this.navLightTimer * 12) * 1.5;
    }
  }

  public setGimbalOrientation(yaw: number, pitch: number): void {
    this.gimbalTurret.rotation.y = yaw;
    this.gimbalAperture.rotation.x = pitch;
  }

  public getWorldGimbalPosition(target: THREE.Vector3): THREE.Vector3 {
    return this.gimbalTurret.getWorldPosition(target);
  }

  public setPositionAndAttitude(pos: Vector3D, pitch: number, yaw: number, roll: number): void {
    this.group.position.set(pos.x, pos.y, pos.z);
    this.group.rotation.set(pitch, yaw, roll, "YXZ");
  }
}
