import { describe, expect, it } from "vitest";
import { SeededRandom } from "../src/simulation/SeededRandom";

describe("SeededRandom", () => {
  it("produces identical sequences for identical seeds", () => {
    const rngA = new SeededRandom(42);
    const rngB = new SeededRandom(42);

    for (let i = 0; i < 100; i++) {
      expect(rngA.next()).toBe(rngB.next());
    }
  });

  it("produces different sequences for different seeds", () => {
    const rng1 = new SeededRandom(42);
    const rng2 = new SeededRandom(999);

    let differentCount = 0;
    for (let i = 0; i < 50; i++) {
      if (rng1.next() !== rng2.next()) {
        differentCount++;
      }
    }
    expect(differentCount).toBeGreaterThan(45);
  });

  it("returns numbers within [min, max) for range()", () => {
    const rng = new SeededRandom(12345);
    for (let i = 0; i < 200; i++) {
      const val = rng.range(-10, 25);
      expect(val).toBeGreaterThanOrEqual(-10);
      expect(val).toBeLessThan(25);
    }
  });

  it("resets back to initial state", () => {
    const rng = new SeededRandom(777);
    const firstRun = Array.from({ length: 20 }, () => rng.next());

    rng.reset();
    const secondRun = Array.from({ length: 20 }, () => rng.next());

    expect(firstRun).toEqual(secondRun);
  });
});
