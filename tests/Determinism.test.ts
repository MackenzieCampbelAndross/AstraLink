import { describe, expect, it } from "vitest";
import { DEFAULT_CONFIG } from "../src/config";
import { SimulationEngine } from "../src/simulation/SimulationEngine";
import { GroundTruth } from "../src/types";

describe("Determinism (Prompt Requirement 32)", () => {
  it("produces identical trajectories over 300 frames on reset with seed 42", () => {
    const engine = new SimulationEngine({ ...DEFAULT_CONFIG, seed: 42 });

    // Run A: 300 frames
    const runA: GroundTruth[] = [];
    for (let i = 0; i < 300; i++) {
      engine.step();
      runA.push(JSON.parse(JSON.stringify(engine.getGroundTruth())));
    }

    // Reset
    engine.reset();

    // Run B: 300 frames
    const runB: GroundTruth[] = [];
    for (let i = 0; i < 300; i++) {
      engine.step();
      runB.push(JSON.parse(JSON.stringify(engine.getGroundTruth())));
    }

    expect(runA.length).toBe(300);
    expect(runB.length).toBe(300);

    for (let f = 0; f < 300; f++) {
      const gtA = runA[f];
      const gtB = runB[f];

      expect(gtA.frameId).toBe(gtB.frameId);
      expect(gtA.timestamp).toBe(gtB.timestamp);
      expect(gtA.targetPosition).toEqual(gtB.targetPosition);
      expect(gtA.targetVelocity).toEqual(gtB.targetVelocity);
      expect(gtA.targetAcceleration).toEqual(gtB.targetAcceleration);
      expect(gtA.beaconPosition).toEqual(gtB.beaconPosition);
    }
  });

  it("produces different trajectories when seed is changed in random motion", () => {
    const configSeed1 = { ...DEFAULT_CONFIG, seed: 42, target: { ...DEFAULT_CONFIG.target, motion: "random" as const } };
    const configSeed2 = { ...DEFAULT_CONFIG, seed: 9999, target: { ...DEFAULT_CONFIG.target, motion: "random" as const } };

    const engine1 = new SimulationEngine(configSeed1);
    const engine2 = new SimulationEngine(configSeed2);

    for (let i = 0; i < 50; i++) {
      engine1.step();
      engine2.step();
    }

    expect(engine1.getGroundTruth().targetPosition).not.toEqual(engine2.getGroundTruth().targetPosition);
  });
});
