/**
 * Deterministic Pseudo-Random Number Generator using Mulberry32.
 * All random behaviors inside AstraLink MUST use this generator.
 * Never call Math.random() in the simulation.
 */
export class SeededRandom {
  private state: number;
  private readonly initialSeed: number;

  constructor(seed: number) {
    this.initialSeed = Math.floor(seed);
    this.state = this.initialSeed >>> 0;
  }

  public getSeed(): number {
    return this.initialSeed;
  }

  public reset(): void {
    this.state = this.initialSeed >>> 0;
  }

  /**
   * Returns a deterministic pseudo-random float in the half-open interval [0, 1).
   */
  public next(): number {
    this.state = (this.state + 0x6d2b79f5) | 0;
    let t = Math.imul(this.state ^ (this.state >>> 15), 1 | this.state);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  }

  /**
   * Returns a deterministic float in [min, max).
   */
  public range(min: number, max: number): number {
    return min + (max - min) * this.next();
  }

  /**
   * Returns a deterministic integer in [min, max].
   */
  public rangeInt(min: number, max: number): number {
    const minInt = Math.ceil(min);
    const maxInt = Math.floor(max);
    return Math.floor(minInt + (maxInt - minInt + 1) * this.next());
  }

  /**
   * Box-Muller transform for deterministic Gaussian (normal) distribution.
   */
  public gaussian(mean = 0, stdDev = 1): number {
    let u1 = 0;
    let u2 = 0;
    while (u1 === 0) u1 = this.next();
    while (u2 === 0) u2 = this.next();
    const z0 = Math.sqrt(-2.0 * Math.log(u1)) * Math.cos(2.0 * Math.PI * u2);
    return mean + z0 * stdDev;
  }
}
