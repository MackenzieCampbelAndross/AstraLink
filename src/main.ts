import { CameraViewMode } from "./rendering/CameraManager";
import { FullTelemetrySnapshot, Simulator } from "./simulator";
import { DEFAULT_CONFIG } from "./config";
import { MotionType } from "./types";

window.addEventListener("DOMContentLoaded", () => {
  const container = document.getElementById("canvas-container") as HTMLElement;
  if (!container) throw new Error("Canvas container missing");

  // Telemetry DOM elements
  const badgeLock = document.getElementById("badge-lock")!;
  const badgeFps = document.getElementById("badge-fps")!;
  const compassDisplay = document.getElementById("compass-display")!;
  const targetBox = document.getElementById("target-box")!;
  const targetBoxLabel = document.getElementById("target-box-label")!;

  const valGimbalState = document.getElementById("val-gimbal-state")!;
  const valLockDuration = document.getElementById("val-lock-duration")!;
  const valTrackingErr = document.getElementById("val-tracking-err")!;
  const valTargetRange = document.getElementById("val-target-range")!;
  const valGimbalAngles = document.getElementById("val-gimbal-angles")!;
  const valOpticalLink = document.getElementById("val-optical-link")!;
  const valZoom = document.getElementById("val-zoom")!;
  const valUav1Stats = document.getElementById("val-uav1-stats")!;
  const valUav2Motion = document.getElementById("val-uav2-motion")!;
  const valModeTag = document.getElementById("val-mode-tag")!;

  // Button elements
  const btnPlay = document.getElementById("btn-play") as HTMLButtonElement;
  const btnStep = document.getElementById("btn-step") as HTMLButtonElement;
  const btnReset = document.getElementById("btn-reset") as HTMLButtonElement;
  const btnBreakLock = document.getElementById("btn-break-lock") as HTMLButtonElement;
  const btnForceSearch = document.getElementById("btn-force-search") as HTMLButtonElement;
  const btnForceLock = document.getElementById("btn-force-lock") as HTMLButtonElement;

  const camButtons = document.querySelectorAll<HTMLButtonElement>(".btn-cam");
  const zoomButtons = document.querySelectorAll<HTMLButtonElement>(".btn-zoom");
  const motionButtons = document.querySelectorAll<HTMLButtonElement>(".btn-motion");

  // Initialize Simulator with dual UAVs, realistic atmosphere, and Camera POV
  const simulator = new Simulator(container, DEFAULT_CONFIG, {
    onTelemetryUpdate: (snapshot: FullTelemetrySnapshot) => {
      updateHUD(snapshot);
    }
  });

  function updateHUD(s: FullTelemetrySnapshot): void {
    const g = s.gimbal;

    // 1. Badge & State
    badgeFps.textContent = `${s.fps} FPS`;
    valGimbalState.textContent = g.state;
    valLockDuration.textContent = `${g.lockDuration.toFixed(1)} s`;
    valTrackingErr.textContent = `${g.trackingErrorMrad.toFixed(1)} mrad`;
    valTargetRange.textContent = `${g.range.toFixed(1)} m`;

    const azDeg = (g.azimuth * 180 / Math.PI).toFixed(1);
    const elDeg = (g.elevation * 180 / Math.PI).toFixed(1);
    valGimbalAngles.textContent = `${azDeg}° / ${elDeg}°`;

    // UAV 1 Altitude & speed
    const alt = s.uav1Position.y.toFixed(0);
    valUav1Stats.textContent = `${alt}m ALT / 35 m/s`;

    // Zoom & View Mode
    valZoom.textContent = `${s.zoom.toFixed(1)}x`;
    valModeTag.textContent = s.cameraMode.replace("_", " ");

    // Heading Compass Tape
    let hdgDeg = Math.round((-s.uav1Attitude.yaw * 180 / Math.PI + 360) % 360);
    compassDisplay.textContent = `HDG ${hdgDeg.toString().padStart(3, "0")}° | EL ${elDeg}°`;

    // 2. Optical Link Status & Target Box Styling
    if (g.state === "LOCKED") {
      badgeLock.textContent = "BEACON LOCKED";
      badgeLock.className = "badge badge-locked";
      valGimbalState.className = "data-val accent-green";

      valOpticalLink.textContent = "OPTICAL LINK ACTIVE (10 Gbps)";
      valOpticalLink.className = "data-val accent-green";

      targetBox.className = "locked";
      targetBoxLabel.textContent = `LOCKED [${g.trackingErrorMrad.toFixed(1)} mrad]`;
      // Center target box precisely on optical reticle
      targetBox.style.transform = `translate(-50%, -50%) translate(${g.searchCoord.x * 20}px, ${g.searchCoord.y * 20}px) scale(1.0)`;
    } else if (g.state === "ACQUIRING") {
      badgeLock.textContent = "ACQUIRING BEACON";
      badgeLock.className = "badge badge-searching";
      valGimbalState.className = "data-val accent-cyan";

      valOpticalLink.textContent = "COARSE ALIGNING...";
      valOpticalLink.className = "data-val accent-cyan";

      targetBox.className = "";
      targetBoxLabel.textContent = "ACQUIRING";
      targetBox.style.transform = `translate(-50%, -50%) translate(${g.searchCoord.x * 120}px, ${g.searchCoord.y * 120}px) scale(1.2)`;
    } else {
      badgeLock.textContent = "SEARCHING";
      badgeLock.className = "badge badge-searching";
      valGimbalState.className = "data-val accent-amber";

      valOpticalLink.textContent = "SEARCHING UNCERTAINTY CONE";
      valOpticalLink.className = "data-val accent-amber";

      targetBox.className = "searching";
      targetBoxLabel.textContent = "SCANNING";
      targetBox.style.transform = `translate(-50%, -50%) translate(${g.searchCoord.x * 150}px, ${g.searchCoord.y * 150}px) scale(1.4)`;
    }
  }

  // Camera selector
  camButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      const mode = btn.dataset.cam as CameraViewMode;
      camButtons.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      simulator.setCameraMode(mode);
    });
  });

  // Zoom selector
  zoomButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      const z = parseFloat(btn.dataset.zoom || "1.0");
      zoomButtons.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      simulator.setZoom(z);
    });
  });

  // Target Motion selector
  motionButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      const motion = btn.dataset.motion as MotionType;
      motionButtons.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      valUav2Motion.textContent = motion.toUpperCase();
      simulator.switchMotion(motion);
    });
  });

  // Gimbal Actions
  btnBreakLock.addEventListener("click", () => {
    simulator.breakLock();
  });

  btnForceSearch.addEventListener("click", () => {
    simulator.forceSearch();
  });

  btnForceLock.addEventListener("click", () => {
    simulator.forceLock();
  });

  // Play / Pause
  btnPlay.addEventListener("click", () => {
    const running = simulator.togglePlay();
    btnPlay.textContent = running ? "Pause [Space]" : "Play [Space]";
  });

  // Step & Reset
  btnStep.addEventListener("click", () => {
    simulator.step();
    btnPlay.textContent = "Play [Space]";
  });

  btnReset.addEventListener("click", () => {
    simulator.reset();
  });

  // Keyboard Shortcuts
  window.addEventListener("keydown", (e) => {
    if (e.code === "Space") {
      e.preventDefault();
      btnPlay.click();
    } else if (e.code === "KeyR") {
      btnReset.click();
    } else if (e.code === "KeyS") {
      btnStep.click();
    } else if (e.code === "KeyB") {
      btnBreakLock.click();
    } else if (e.code === "KeyL") {
      btnForceLock.click();
    }
  });
});
