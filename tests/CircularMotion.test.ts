import { describe, expect, it } from "vitest";
import { CircularMotion } from "../src/simulation/motion/CircularMotion";

describe("CircularMotion", () => {
  it("maintains constant radius from center", () => {
    const center = { x: 50, y: 10, z: -20 };
    const radius = 100;
    const w = 1.0;
    const motion = new CircularMotion({ center, radius, angularVelocity: w, plane: "XZ" });

    for (let t = 0; t < 6.28; t += 0.2) {
      const state = motion.update(t, 0.2);
      const dist = Math.hypot(state.position.x - center.x, state.position.z - center.z);
      expect(dist).toBeCloseTo(radius, 4);
      expect(state.position.y).toBeCloseTo(center.y, 4);
    }
  });

  it("calculates exact centripetal acceleration a = -w^2 * (r - c)", () => {
    const center = { x: 0, y: 0, z: 0 };
    const radius = 50;
    const w = 2.0;
    const motion = new CircularMotion({ center, radius, angularVelocity: w, plane: "XZ" });

    const state = motion.update(1.23, 0.05);
    expect(state.acceleration.x).toBeCloseTo(-w * w * state.position.x, 4);
    expect(state.acceleration.z).toBeCloseTo(-w * w * state.position.z, 4);
  });

  it("rejects non-positive radius", () => {
    expect(() => new CircularMotion({ center: { x: 0, y: 0, z: 0 }, radius: 0, angularVelocity: 1 })).toThrow();
    expect(() => new CircularMotion({ center: { x: 0, y: 0, z: 0 }, radius: -10, angularVelocity: 1 })).toThrow();
  });
});
