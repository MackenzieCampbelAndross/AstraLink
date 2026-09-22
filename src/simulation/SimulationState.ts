import {
  BeaconState,
  GroundTruth,
  SimulationStateSnapshot,
  SimulationTime,
  TargetState,
  TerminalState
} from "../types";

export function createSimulationSnapshot(
  time: SimulationTime,
  terminal1: TerminalState,
  target: TargetState,
  beacon: BeaconState,
  groundTruth: GroundTruth,
  isFinished: boolean
): SimulationStateSnapshot {
  return Object.freeze({
    time: Object.freeze({ ...time }),
    terminal1: Object.freeze({
      id: terminal1.id,
      position: Object.freeze({ ...terminal1.position }),
      orientation: Object.freeze({ ...terminal1.orientation })
    }),
    target: Object.freeze({
      timestamp: target.timestamp,
      frameId: target.frameId,
      position: Object.freeze({ ...target.position }),
      velocity: Object.freeze({ ...target.velocity }),
      acceleration: Object.freeze({ ...target.acceleration }),
      orientation: Object.freeze({ ...target.orientation })
    }),
    beacon: Object.freeze({
      enabled: beacon.enabled,
      brightness: beacon.brightness,
      size: beacon.size,
      localPosition: Object.freeze({ ...beacon.localPosition }),
      worldPosition: Object.freeze({ ...beacon.worldPosition })
    }),
    groundTruth,
    isFinished
  });
}
