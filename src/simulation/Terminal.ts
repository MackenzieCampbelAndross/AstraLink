import { TerminalConfig, TerminalState, Vector3D } from "../types";

export class Terminal {
  readonly id: string;
  private readonly position: Vector3D;
  private orientation: Vector3D;

  constructor(id: string, config: TerminalConfig) {
    this.id = id;
    this.position = { ...config.position };
    this.orientation = { x: 0, y: 0, z: 0 };
  }

  public getPosition(): Vector3D {
    return { ...this.position };
  }

  public getOrientation(): Vector3D {
    return { ...this.orientation };
  }

  public setOrientation(orientation: Vector3D): void {
    this.orientation = { ...orientation };
  }

  public getState(): TerminalState {
    return {
      id: this.id,
      position: this.getPosition(),
      orientation: this.getOrientation()
    };
  }
}
