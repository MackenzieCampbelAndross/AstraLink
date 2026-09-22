import { describe, expect, it } from "vitest";
import { DEFAULT_CONFIG } from "../src/config";
import { SimulationEngine } from "../src/simulation/SimulationEngine";

describe("SimulationEngine", () => {
  it("initializes and produces valid ground truth", () => {
    const engine = new SimulationEngine(DEFAULT_CONFIG);
    expect(engine.getTime()).toBe(0);
    expect(engine.getFrameId()).toBe(0);

    const gt = engine.getGroundTruth();
    expect(gt.timestamp).toBe(0);
    expect(gt.frameId).toBe(0);
    expect(gt.targetPosition).toBeDefined();
    expect(gt.beaconPosition).toBeDefined();
  });

  it("advances state deterministically across steps", () => {
    const engine = new SimulationEngine(DEFAULT_CONFIG);
    engine.step();
    expect(engine.getFrameId()).toBe(1);
    expect(engine.getTime()).toBeCloseTo(DEFAULT_CONFIG.simulation.dt, 5);

    const gt = engine.getGroundTruth();
    expect(gt.frameId).toBe(1);
  });

  it("resets state back to t=0", () => {
    const engine = new SimulationEngine(DEFAULT_CONFIG);
    for (let i = 0; i < 10; i++) engine.step();
    expect(engine.getFrameId()).toBe(10);

    engine.reset();
    expect(engine.getFrameId()).toBe(0);
    expect(engine.getTime()).toBe(0);
  });
});
