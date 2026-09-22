import { SimulationConfig } from "./types";

export const DEFAULT_CONFIG: SimulationConfig = {
  seed: 42,
  simulation: {
    duration_s: 30,
    dt: 0.0333333333
  },
  world: {
    width: 2000,
    height: 1000,
    depth: 2000,
    boundary_behavior: "bounce"
  },
  terminals: {
    terminal1: {
      position: { x: 0, y: 0, z: 0 }
    },
    terminal2: {
      position: { x: 300, y: 50, z: -300 }
    }
  },
  target: {
    motion: "circular",
    size: { x: 2, y: 2, z: 2 },
    initial_velocity: { x: 10, y: 0, z: 0 },
    circular: {
      center: { x: 0, y: 50, z: -300 },
      radius: 300,
      angular_velocity: 0.4,
      plane: "XZ",
      initial_phase: 0
    },
    figure8: {
      center: { x: 0, y: 50, z: -300 },
      amplitude_x: 250,
      amplitude_z: 150,
      angular_frequency: 0.3,
      initial_phase: 0
    },
    random: {
      max_acceleration: 20,
      max_velocity: 60,
      damping: 0.02
    }
  },
  beacon: {
    enabled: true,
    brightness: 1.0,
    size: 4,
    localPosition: { x: 0, y: 1.2, z: 0 }
  },
  visualization: {
    showTrajectory: true,
    trajectoryLength: 600
  }
};

export function validateConfig(cfg: unknown): SimulationConfig {
  if (!cfg || typeof cfg !== "object") {
    throw new Error("Invalid configuration: configuration must be a valid JSON object");
  }

  const raw = cfg as Record<string, unknown>;

  if (typeof raw.seed !== "number" || !Number.isFinite(raw.seed)) {
    throw new Error("Invalid configuration: seed must be a finite number");
  }

  const sim = raw.simulation as Record<string, unknown> | undefined;
  if (!sim || typeof sim !== "object") {
    throw new Error("Invalid configuration: 'simulation' section is required");
  }
  if (typeof sim.dt !== "number" || sim.dt <= 0 || !Number.isFinite(sim.dt)) {
    throw new Error(`Invalid timestep: dt must be greater than 0, got ${sim.dt}`);
  }
  if (sim.duration_s !== undefined && (typeof sim.duration_s !== "number" || sim.duration_s <= 0)) {
    throw new Error(`Invalid duration: duration_s must be positive, got ${sim.duration_s}`);
  }

  const world = raw.world as Record<string, unknown> | undefined;
  if (!world || typeof world !== "object") {
    throw new Error("Invalid configuration: 'world' section is required");
  }
  if (typeof world.width !== "number" || world.width <= 0) {
    throw new Error(`Invalid world dimensions: width must be positive, got ${world.width}`);
  }
  if (typeof world.height !== "number" || world.height <= 0) {
    throw new Error(`Invalid world dimensions: height must be positive, got ${world.height}`);
  }
  if (typeof world.depth !== "number" || world.depth <= 0) {
    throw new Error(`Invalid world dimensions: depth must be positive, got ${world.depth}`);
  }

  const terms = raw.terminals as Record<string, unknown> | undefined;
  if (!terms || typeof terms !== "object") {
    throw new Error("Invalid configuration: 'terminals' section is required");
  }
  const t1 = terms.terminal1 as Record<string, unknown> | undefined;
  const t2 = terms.terminal2 as Record<string, unknown> | undefined;
  if (!t1 || !t1.position || !isVector3D(t1.position)) {
    throw new Error("Invalid terminal position: terminal1 must specify a valid {x, y, z} position");
  }
  if (!t2 || !t2.position || !isVector3D(t2.position)) {
    throw new Error("Invalid terminal position: terminal2 must specify a valid {x, y, z} position");
  }

  const target = raw.target as Record<string, unknown> | undefined;
  if (!target || typeof target !== "object") {
    throw new Error("Invalid configuration: 'target' section is required");
  }
  const validMotions = ["straight", "circular", "figure8", "random"];
  if (typeof target.motion !== "string" || !validMotions.includes(target.motion)) {
    throw new Error(`Unknown motion model: expected one of [${validMotions.join(", ")}], got '${target.motion}'`);
  }

  if (target.motion === "circular") {
    const circ = target.circular as Record<string, unknown> | undefined;
    if (circ) {
      if (typeof circ.radius === "number" && circ.radius <= 0) {
        throw new Error(`Negative radius: circular motion radius must be > 0, got ${circ.radius}`);
      }
    }
  }

  if (target.motion === "figure8") {
    const fig = target.figure8 as Record<string, unknown> | undefined;
    if (fig) {
      if (typeof fig.amplitude_x === "number" && fig.amplitude_x <= 0) {
        throw new Error(`Invalid amplitude: figure-8 amplitude_x must be > 0, got ${fig.amplitude_x}`);
      }
      if (typeof fig.amplitude_z === "number" && fig.amplitude_z <= 0) {
        throw new Error(`Invalid amplitude: figure-8 amplitude_z must be > 0, got ${fig.amplitude_z}`);
      }
    }
  }

  if (target.motion === "random") {
    const rnd = target.random as Record<string, unknown> | undefined;
    if (rnd) {
      if (typeof rnd.max_acceleration === "number" && rnd.max_acceleration <= 0) {
        throw new Error(`Invalid acceleration: random motion max_acceleration must be > 0, got ${rnd.max_acceleration}`);
      }
      if (typeof rnd.max_velocity === "number" && rnd.max_velocity <= 0) {
        throw new Error(`Invalid velocity: random motion max_velocity must be > 0, got ${rnd.max_velocity}`);
      }
    }
  }

  const beacon = raw.beacon as Record<string, unknown> | undefined;
  if (!beacon || typeof beacon !== "object") {
    throw new Error("Invalid configuration: 'beacon' section is required");
  }
  if (typeof beacon.enabled !== "boolean") {
    throw new Error("Invalid configuration: beacon.enabled must be a boolean");
  }
  if (typeof beacon.brightness !== "number" || beacon.brightness < 0) {
    throw new Error("Invalid configuration: beacon.brightness must be a non-negative number");
  }
  if (typeof beacon.size !== "number" || beacon.size <= 0) {
    throw new Error("Invalid configuration: beacon.size must be greater than 0");
  }

  return raw as unknown as SimulationConfig;
}

function isVector3D(v: unknown): boolean {
  if (!v || typeof v !== "object") return false;
  const obj = v as Record<string, unknown>;
  return (
    typeof obj.x === "number" && Number.isFinite(obj.x) &&
    typeof obj.y === "number" && Number.isFinite(obj.y) &&
    typeof obj.z === "number" && Number.isFinite(obj.z)
  );
}

export function createConfigForMotion(
  motion: "straight" | "circular" | "figure8" | "random",
  baseConfig: SimulationConfig = DEFAULT_CONFIG
): SimulationConfig {
  const cfg = JSON.parse(JSON.stringify(baseConfig)) as SimulationConfig;
  cfg.target.motion = motion;
  return cfg;
}
