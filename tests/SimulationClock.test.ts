import { describe, expect, it } from "vitest";
import { SimulationClock } from "../src/simulation/SimulationClock";

describe("SimulationClock", () => {
  it("initializes at frame 0 and time 0", () => {
    const clock = new SimulationClock(0.0333333333);
    expect(clock.getTime()).toBe(0);
    expect(clock.getFrameId()).toBe(0);
    expect(clock.getDeltaTime()).toBeCloseTo(0.0333333333, 6);
  });

  it("increments frameId and advances time with each step", () => {
    const dt = 0.05;
    const clock = new SimulationClock(dt);

    const s1 = clock.step();
    expect(s1.frameId).toBe(1);
    expect(s1.time).toBeCloseTo(0.05, 5);

    const s2 = clock.step();
    expect(s2.frameId).toBe(2);
    expect(s2.time).toBeCloseTo(0.1, 5);

    const s3 = clock.step();
    expect(s3.frameId).toBe(3);
    expect(s3.time).toBeCloseTo(0.15, 5);
  });

  it("resets correctly", () => {
    const clock = new SimulationClock(0.1);
    clock.step();
    clock.step();
    expect(clock.getFrameId()).toBe(2);
    expect(clock.getTime()).toBeCloseTo(0.2, 5);

    clock.reset();
    expect(clock.getFrameId()).toBe(0);
    expect(clock.getTime()).toBe(0);
  });

  it("throws error for non-positive or non-finite dt", () => {
    expect(() => new SimulationClock(0)).toThrow();
    expect(() => new SimulationClock(-0.01)).toThrow();
    expect(() => new SimulationClock(NaN)).toThrow();
  });
});
