import { describe, expect, it } from "vitest";
import { RandomMotion } from "../src/simulation/motion/RandomMotion";

describe("RandomMotion", () => {
  it("is 100% deterministic with the same seed", () => {
    const motionA = new RandomMotion({
      initialPosition: { x: 0, y: 10, z: 0 },
      maxAcceleration: 20,
      maxVelocity: 50,
      damping: 0.05,
      seed: 42
    });

    const motionB = new RandomMotion({
      initialPosition: { x: 0, y: 10, z: 0 },
      maxAcceleration: 20,
      maxVelocity: 50,
      damping: 0.05,
      seed: 42
    });

    const dt = 0.0333;
    for (let i = 0; i < 100; i++) {
      const sa = motionA.update(i * dt, dt);
      const sb = motionB.update(i * dt, dt);
      expect(sa.position).toEqual(sb.position);
      expect(sa.velocity).toEqual(sb.velocity);
      expect(sa.acceleration).toEqual(sb.acceleration);
    }
  });

  it("produces different trajectories with different seeds", () => {
    const motion1 = new RandomMotion({
      initialPosition: { x: 0, y: 10, z: 0 },
      maxAcceleration: 20,
      maxVelocity: 50,
      damping: 0.05,
      seed: 111
    });

    const motion2 = new RandomMotion({
      initialPosition: { x: 0, y: 10, z: 0 },
      maxAcceleration: 20,
      maxVelocity: 50,
      damping: 0.05,
      seed: 999
    });

    const dt = 0.0333;
    for (let i = 0; i < 30; i++) {
      motion1.update(i * dt, dt);
      motion2.update(i * dt, dt);
    }

    const s1 = motion1.getState();
    const s2 = motion2.getState();
    expect(s1.position).not.toEqual(s2.position);
  });

  it("respects maximum velocity limits", () => {
    const maxVel = 40;
    const motion = new RandomMotion({
      initialPosition: { x: 0, y: 0, z: 0 },
      maxAcceleration: 100,
      maxVelocity: maxVel,
      damping: 0.01,
      seed: 42
    });

    const dt = 0.0333;
    for (let i = 0; i < 300; i++) {
      const state = motion.update(i * dt, dt);
      const speed = Math.hypot(state.velocity.x, state.velocity.y, state.velocity.z);
      expect(speed).toBeLessThanOrEqual(maxVel + 1e-4);
    }
  });
});
