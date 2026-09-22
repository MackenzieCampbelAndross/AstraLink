import { describe, expect, it } from "vitest";
import { StraightMotion } from "../src/simulation/motion/StraightMotion";

describe("StraightMotion", () => {
  it("starts at initial position with given velocity", () => {
    const motion = new StraightMotion({ x: 10, y: 20, z: 30 }, { x: 5, y: 0, z: -2 });
    const state = motion.getState();
    expect(state.position).toEqual({ x: 10, y: 20, z: 30 });
    expect(state.velocity).toEqual({ x: 5, y: 0, z: -2 });
    expect(state.acceleration).toEqual({ x: 0, y: 0, z: 0 });
  });

  it("linearly moves over time", () => {
    const motion = new StraightMotion({ x: 0, y: 0, z: 0 }, { x: 10, y: 2, z: -5 });
    const dt = 0.1;

    for (let i = 1; i <= 10; i++) {
      const s = motion.update(i * dt, dt);
      expect(s.position.x).toBeCloseTo(i * dt * 10, 5);
      expect(s.position.y).toBeCloseTo(i * dt * 2, 5);
      expect(s.position.z).toBeCloseTo(i * dt * -5, 5);
    }
  });

  it("bounces at world boundary correctly", () => {
    const bounds = {
      min: { x: -100, y: -100, z: -100 },
      max: { x: 100, y: 100, z: 100 },
      behavior: "bounce" as const
    };
    const motion = new StraightMotion({ x: 90, y: 0, z: 0 }, { x: 20, y: 0, z: 0 }, bounds);
    // Move by dt = 1s: 90 + 20 = 110 -> bounces off 100 to 100 - 10 = 90, velocity inverted to -20
    const nextState = motion.update(1, 1);
    expect(nextState.position.x).toBeCloseTo(90, 5);
    expect(nextState.velocity.x).toBeCloseTo(-20, 5);
  });
});
