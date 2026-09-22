import { DEFAULT_CONFIG } from "./config";
import { Simulator } from "./simulator";
import { MotionType, SimulationStateSnapshot } from "./types";

window.addEventListener("DOMContentLoaded", () => {
  const container = document.getElementById("canvas-container") as HTMLElement;
  if (!container) {
    throw new Error("Canvas container not found");
  }

  // DOM elements for telemetry
  const valTime = document.getElementById("val-time")!;
  const valFrame = document.getElementById("val-frame")!;
  const valMotion = document.getElementById("val-motion")!;
  const valSeed = document.getElementById("val-seed")!;
  const valTargetPos = document.getElementById("val-target-pos")!;
  const valTargetVel = document.getElementById("val-target-vel")!;
  const valSpeed = document.getElementById("val-speed")!;
  const valTargetAcc = document.getElementById("val-target-acc")!;
  const valBeaconPos = document.getElementById("val-beacon-pos")!;
  const valBeaconState = document.getElementById("val-beacon-state")!;
  const valT1Pos = document.getElementById("val-t1-pos")!;
  const valDistance = document.getElementById("val-distance")!;
  const badgeStatus = document.getElementById("badge-status")!;
  const fpsBadge = document.getElementById("fps-badge")!;

  // DOM elements for buttons
  const btnPlay = document.getElementById("btn-play") as HTMLButtonElement;
  const btnStep = document.getElementById("btn-step") as HTMLButtonElement;
  const btnReset = document.getElementById("btn-reset") as HTMLButtonElement;
  const btnTrail = document.getElementById("btn-trail") as HTMLButtonElement;
  const btnCamReset = document.getElementById("btn-cam-reset") as HTMLButtonElement;
  const motionButtons = document.querySelectorAll<HTMLButtonElement>(".btn-motion");
  const speedButtons = document.querySelectorAll<HTMLButtonElement>(".btn-speed");

  let trailVisible = true;

  // Initialize simulator
  const simulator = new Simulator(container, DEFAULT_CONFIG, {
    onStateUpdate: (state: SimulationStateSnapshot, fps: number) => {
      updateHUD(state, fps);
    }
  });

  function updateHUD(state: SimulationStateSnapshot, fps: number): void {
    const gt = state.groundTruth;

    valTime.textContent = `${gt.timestamp.toFixed(3)} s`;
    valFrame.textContent = `${gt.frameId} (${(1 / state.time.deltaTime).toFixed(1)} Hz)`;
    valSeed.textContent = `Seed: ${DEFAULT_CONFIG.seed}`;

    // Target Pos
    const tp = gt.targetPosition;
    valTargetPos.textContent = `${tp.x.toFixed(1)}, ${tp.y.toFixed(1)}, ${tp.z.toFixed(1)}`;

    // Velocity
    const tv = gt.targetVelocity;
    valTargetVel.textContent = `${tv.x.toFixed(1)}, ${tv.y.toFixed(1)}, ${tv.z.toFixed(1)}`;
    const speed = Math.hypot(tv.x, tv.y, tv.z);
    valSpeed.textContent = `${speed.toFixed(2)} m/s`;

    // Acceleration
    const ta = gt.targetAcceleration;
    valTargetAcc.textContent = `${ta.x.toFixed(1)}, ${ta.y.toFixed(1)}, ${ta.z.toFixed(1)}`;

    // Beacon
    const bp = gt.beaconPosition;
    valBeaconPos.textContent = `${bp.x.toFixed(1)}, ${bp.y.toFixed(1)}, ${bp.z.toFixed(1)}`;
    valBeaconState.textContent = state.beacon.enabled
      ? `ACTIVE (${state.beacon.brightness.toFixed(1)})`
      : "DISABLED";

    // Terminal 1 & separation
    const t1 = state.terminal1.position;
    valT1Pos.textContent = `(${t1.x.toFixed(1)}, ${t1.y.toFixed(1)}, ${t1.z.toFixed(1)})`;
    const dist = Math.hypot(tp.x - t1.x, tp.y - t1.y, tp.z - t1.z);
    valDistance.textContent = `${dist.toFixed(1)} m`;

    // Status
    fpsBadge.textContent = `${fps} FPS`;
    if (state.isFinished) {
      badgeStatus.textContent = "FINISHED";
      badgeStatus.className = "badge";
      badgeStatus.style.borderColor = "var(--accent-amber)";
      badgeStatus.style.color = "var(--accent-amber)";
    } else if (simulator.getIsRunning()) {
      badgeStatus.textContent = "RUNNING";
      badgeStatus.className = "badge badge-status";
      badgeStatus.style.borderColor = "";
      badgeStatus.style.color = "";
    } else {
      badgeStatus.textContent = "PAUSED";
      badgeStatus.className = "badge";
      badgeStatus.style.borderColor = "var(--accent-pink)";
      badgeStatus.style.color = "var(--accent-pink)";
    }
  }

  // Play / Pause
  btnPlay.addEventListener("click", () => {
    const isRunning = simulator.togglePlay();
    btnPlay.textContent = isRunning ? "Pause [Space]" : "Play [Space]";
    btnPlay.className = isRunning ? "btn-primary" : "";
  });

  // Reset
  btnReset.addEventListener("click", () => {
    simulator.reset();
  });

  // Step
  btnStep.addEventListener("click", () => {
    simulator.step();
    btnPlay.textContent = "Play [Space]";
    btnPlay.className = "";
  });

  // Motion buttons
  motionButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      const motion = btn.dataset.motion as MotionType;
      motionButtons.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      valMotion.textContent = motion.toUpperCase();
      simulator.switchMotion(motion);
    });
  });

  // Speed buttons
  speedButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      const speed = parseFloat(btn.dataset.speed || "1.0");
      speedButtons.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      simulator.setSpeed(speed);
    });
  });

  // Trajectory toggle
  btnTrail.addEventListener("click", () => {
    trailVisible = !trailVisible;
    simulator.setTrajectoryVisible(trailVisible);
    btnTrail.classList.toggle("active", trailVisible);
  });

  // Reset Camera
  btnCamReset.addEventListener("click", () => {
    simulator.resetCamera();
  });

  // Keyboard shortcuts
  window.addEventListener("keydown", (e) => {
    if (e.code === "Space") {
      e.preventDefault();
      btnPlay.click();
    } else if (e.code === "KeyR") {
      btnReset.click();
    } else if (e.code === "KeyS") {
      btnStep.click();
    } else if (e.code === "Digit1") {
      motionButtons[0]?.click();
    } else if (e.code === "Digit2") {
      motionButtons[1]?.click();
    } else if (e.code === "Digit3") {
      motionButtons[2]?.click();
    } else if (e.code === "Digit4") {
      motionButtons[3]?.click();
    }
  });
});
