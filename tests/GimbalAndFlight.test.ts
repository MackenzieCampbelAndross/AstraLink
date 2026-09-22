import { describe, expect, it } from "vitest";
import { FlightKinematics, TransmitterFlightTrajectory } from "../src/simulation/flight/FlightKinematics";
import { GimbalController } from "../src/simulation/gimbal/GimbalController";

describe("FlightKinematics", () => {
  it("computes coordinated turn bank angle proportionally to yaw rate", () => {
    const kinematics = new FlightKinematics();
    const dt = 0.05;

    kinematics.computeAttitude({ x: 0, y: 0, z: -30 }, 0, dt);
    const attTurn = kinematics.computeAttitude({ x: 10, y: 0, z: -28 }, 0.05, dt);

    expect(attTurn.yaw).toBeGreaterThan(0);
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
  it("starts in SEARCHING state with ~5-10 second search duration", () => {
    const gimbal = new GimbalController();
    expect(gimbal.getState()).toBe("SEARCHING");

    const uavPos = { x: 0, y: 200, z: 0 };
    const beaconPos = { x: 200, y: 200, z: -400 };

    const t = gimbal.update(uavPos, 0, 0, beaconPos, 0.033);
    expect(t.state).toBe("SEARCHING");
    expect(t.searchDuration).toBeGreaterThanOrEqual(5.0);
    expect(t.searchDuration).toBeLessThanOrEqual(10.0);
  });

  it("sweeps across sectors during search phase without premature locking", () => {
    const gimbal = new GimbalController(6.0); // 6s search duration
    const uavPos = { x: 0, y: 200, z: 0 };
    const beaconPos = { x: 0, y: 200, z: -300 };

    // Update for 2 seconds (< 6s search duration)
    for (let i = 0; i < 40; i++) {
      gimbal.update(uavPos, 0, 0, beaconPos, 0.05);
    }

    // Must still be SEARCHING across airspace sectors
    expect(gimbal.getState()).toBe("SEARCHING");
  });

  it("transitions to ACQUIRING and LOCKED after search duration elapses and intercepts target", () => {
    const gimbal = new GimbalController(2.0); // Configure 2s discovery for fast unit test
    const uavPos = { x: 0, y: 200, z: 0 };
    const beaconPos = { x: 0, y: 200, z: -300 };

    // Advance 4 seconds (past searchDuration 2.0s)
    for (let i = 0; i < 80; i++) {
      gimbal.update(uavPos, 0, 0, beaconPos, 0.05);
    }

    const finalTel = gimbal.update(uavPos, 0, 0, beaconPos, 0.05);
    expect(["ACQUIRING", "LOCKED"]).toContain(finalTel.state);
  });

  it("breaks lock and initiates a new 5-10 second search cycle", () => {
    const gimbal = new GimbalController();
    gimbal.forceLock(0, 0);
    expect(gimbal.getState()).toBe("LOCKED");

    gimbal.breakLock();
    expect(gimbal.getState()).toBe("SEARCHING");
    const tel = gimbal.update({ x: 0, y: 200, z: 0 }, 0, 0, { x: 0, y: 200, z: -300 }, 0.033);
    expect(tel.searchTime).toBeCloseTo(0.033, 2);
    expect(tel.searchDuration).toBeGreaterThanOrEqual(5.0);
  });
});
