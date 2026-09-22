import { describe, expect, it } from "vitest";
import { OpticalBeacon } from "../src/beacon/OpticalBeacon";

describe("OpticalBeacon", () => {
  it("computes world position by adding local offset at zero orientation", () => {
    const beacon = new OpticalBeacon({
      enabled: true,
      brightness: 1.0,
      size: 5,
      localPosition: { x: 0, y: 2, z: 1 }
    });

    beacon.updateWorldPosition({ x: 100, y: 50, z: -200 }, { x: 0, y: 0, z: 0 });
    const worldPos = beacon.getWorldPosition();

    expect(worldPos.x).toBeCloseTo(100, 5);
    expect(worldPos.y).toBeCloseTo(52, 5);
    expect(worldPos.z).toBeCloseTo(-199, 5);
  });

  it("rotates local position when target orientation changes", () => {
    const beacon = new OpticalBeacon({
      enabled: true,
      brightness: 1.0,
      size: 5,
      localPosition: { x: 0, y: 0, z: 10 }
    });

    // 90 degrees yaw (PI/2 around Y axis)
    beacon.updateWorldPosition({ x: 0, y: 0, z: 0 }, { x: 0, y: Math.PI / 2, z: 0 });
    const worldPos = beacon.getWorldPosition();

    // Local z=10 rotated 90 deg yaw should point along world X
    expect(worldPos.x).toBeCloseTo(10, 4);
    expect(worldPos.y).toBeCloseTo(0, 4);
    expect(worldPos.z).toBeCloseTo(0, 4);
  });
});
