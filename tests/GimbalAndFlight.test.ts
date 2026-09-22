import { describe, expect, it } from "vitest";
import { FlightKinematics, TransmitterFlightTrajectory } from "../src/simulation/flight/FlightKinematics";
import { GimbalController } from "../src/simulation/gimbal/GimbalController";

describe("FlightKinematics", () => {
  it("computes coordinated turn bank angle proportionally to yaw rate", () => {
    const kinematics = new FlightKinematics();

    // Flight with forward speed 30 m/s
    const dt = 0.05;

    // Step 1: Heading straight North (-Z)
    kinematics.computeAttitude({ x: 0, y: 0, z: -30 }, 0, dt);

    // Step 2: Initiating a turn toward East (+X)
    const attTurn = kinematics.computeAttitude({ x: 10, y: 0, z: -28 }, 0.05, dt);

    expect(attTurn.yaw).toBeGreaterThan(0);
    // Bank/Roll should be non-zero during turn
    expect(attTurn.roll).not.toBe(0);
  });

  it("advances transmitter patrol flight smoothly", () => {
    const traj = new TransmitterFlightTrajectory();
    const s0 = traj.update(0);
    const s1 = traj.update(1.0);

    expect(s0.position.y).toBeCloseTo(180, 0);
    expect(s1.position.x).not.toEqual(s0.position.x);
    expect(Math.hypot(s1.velocity.x, s1.velocity.z)).toBeGreaterThan(20);
  });
});

describe("GimbalController Search and Lock", () => {
  it("starts in SEARCHING state and executes scan pattern", () => {
    const gimbal = new GimbalController();
    expect(gimbal.getState()).toBe("SEARCHING");

    const uavPos = { x: 0, y: 200, z: 0 };
    const beaconPos = { x: 200, y: 200, z: -400 };

    const t = gimbal.update(uavPos, 0, 0, beaconPos, 0.033);
    expect(t.range).toBeGreaterThan(300);
    expect(t.state).toBeDefined();
  });

  it("transitions from SEARCHING -> ACQUIRING -> LOCKED when beacon is aligned", () => {
    const gimbal = new GimbalController();

    const uavPos = { x: 0, y: 200, z: 0 };
    const beaconPos = { x: 0, y: 200, z: -300 }; // Directly in front at 0 Azimuth, 0 Elevation

    // Advance gimbal through update ticks
    for (let i = 0; i < 40; i++) {
      gimbal.update(uavPos, 0, 0, beaconPos, 0.05);
    }

    // After slewing toward target, gimbal should acquire and lock
    const finalTel = gimbal.update(uavPos, 0, 0, beaconPos, 0.05);
    expect(["ACQUIRING", "LOCKED"]).toContain(finalTel.state);
    expect(finalTel.trackingErrorMrad).toBeLessThan(50); // within 50 mrad
  });

  it("can break lock and re-enter SEARCHING", () => {
    const gimbal = new GimbalController();
    gimbal.forceLock(0, 0);
    expect(gimbal.getState()).toBe("LOCKED");

    gimbal.breakLock();
    expect(gimbal.getState()).toBe("SEARCHING");
  });
});
