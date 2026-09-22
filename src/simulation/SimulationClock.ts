import { SimulationTime } from "../types";

/**
 * Deterministic simulation clock with fixed timestep dt.
 * Time advancement is strictly tied to frame ID and fixed dt.
 */
export class SimulationClock {
  private time: number = 0;
  private frameId: number = 0;
  private readonly dt: number;

  constructor(dt: number = 1 / 30) {
    if (dt <= 0 || !Number.isFinite(dt)) {
      throw new Error(`SimulationClock: invalid dt ${dt}`);
    }
    this.dt = dt;
    this.reset();
  }

  public reset(): void {
    this.time = 0;
    this.frameId = 0;
  }

  /**
   * Advances the simulation by exactly one fixed timestep dt.
   */
  public step(): SimulationTime {
    this.frameId++;
    // Use multiplication to avoid cumulative floating point addition error
    this.time = this.frameId * this.dt;
    return this.getTimeState();
  }

  public getTime(): number {
    return this.time;
  }

  public getDeltaTime(): number {
    return this.dt;
  }

  public getFrameId(): number {
    return this.frameId;
  }

  public getTimeState(): SimulationTime {
    return {
      time: this.time,
      deltaTime: this.dt,
      frameId: this.frameId
    };
  }
}
