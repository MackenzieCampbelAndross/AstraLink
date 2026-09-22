import { BeaconState, GroundTruth, TargetState } from "../types";

export class GroundTruthGenerator {
  public static generate(
    timestamp: number,
    frameId: number,
    targetState: TargetState,
    beaconState: BeaconState
  ): GroundTruth {
    return Object.freeze({
      timestamp,
      frameId,
      targetPosition: Object.freeze({ ...targetState.position }),
      targetVelocity: Object.freeze({ ...targetState.velocity }),
      targetAcceleration: Object.freeze({ ...targetState.acceleration }),
      targetOrientation: Object.freeze({ ...targetState.orientation }),
      beaconPosition: Object.freeze({ ...beaconState.worldPosition })
    });
  }
}
