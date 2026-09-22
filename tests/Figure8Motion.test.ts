import { describe, expect, it } from "vitest";
import { Figure8Motion } from "../src/simulation/motion/Figure8Motion";

describe("Figure8Motion", () => {
  it("remains bounded within amplitudes", () => {
    const center = { x: 100, y: 50, z: 200 };
    const ampX = 80;
    const ampZ = 40;
    const motion = new Figure8Motion({
      center,
      amplitudeX: ampX,
      amplitudeZ: ampZ,
      angularFrequency: 0.5
    });

    for (let t = 0; t <= 20; t += 0.2) {
      const state = motion.update(t, 0.2);
      expect(state.position.x).toBeGreaterThanOrEqual(center.x - ampX - 1e-4);
      expect(state.position.x).toBeLessThanOrEqual(center.x + ampX + 1e-4);
      expect(state.position.z).toBeGreaterThanOrEqual(center.z - ampZ - 1e-4);
      expect(state.position.z).toBeLessThanOrEqual(center.z + ampZ + 1e-4);
      expect(state.position.y).toBe(center.y);
    }
  });

  it("has smooth continuous derivatives", () => {
    const motion = new Figure8Motion({
      center: { x: 0, y: 0, z: 0 },
      amplitudeX: 100,
      amplitudeZ: 50,
      angularFrequency: 1.0
    });

    // At t = 0: x = 0, z = 0, vx = 100, vz = 100
    const s0 = motion.update(0, 0);
    expect(s0.position.x).toBeCloseTo(0, 5);
    expect(s0.position.z).toBeCloseTo(0, 5);
    expect(s0.velocity.x).toBeCloseTo(100, 5);
    expect(s0.velocity.z).toBeCloseTo(100, 5);
  });
});
