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
  const signalBar = document.getElementById("signal-bar")!;
  const valSignalRssi = document.getElementById("val-signal-rssi")!;

  const valGimbalState = document.getElementById("val-gimbal-state")!;
  const valSearchSector = document.getElementById("val-search-sector")!;
  const valSearchTime = document.getElementById("val-search-time")!;
  const valLockDuration = document.getElementById("val-lock-duration")!;
  const valTrackingErr = document.getElementById("val-tracking-err")!;
  const valTargetRange = document.getElementById("val-target-range")!;
  const valGimbalAngles = document.getElementById("val-gimbal-angles")!;
  const valOpticalLink = document.getElementById("val-optical-link")!;
  const valZoom = document.getElementById("val-zoom")!;
  const valUav1Stats = document.getElementById("val-uav1-stats")!;
  const valUav2Motion = document.getElementById("val-uav2-motion")!;
  const valModeTag = document.getElementById("val-mode-tag")!;

  // Member 2 & Member 3 Security Panel Elements
  const valBackendStatus = document.getElementById("val-backend-status")!;
  const valSecTrackingState = document.getElementById("val-sec-tracking-state")!;
  const valSecBeaconVisible = document.getElementById("val-sec-beacon-visible")!;
  const valSecConfidence = document.getElementById("val-sec-confidence")!;
  const valSecMotionConsistency = document.getElementById("val-sec-motion-consistency")!;
  const valSecTrustState = document.getElementById("val-sec-trust-state")!;
  const valSecAuth = document.getElementById("val-sec-auth")!;
  const valSecAuthorization = document.getElementById("val-sec-authorization")!;
  const valSecTxAllowed = document.getElementById("val-sec-tx-allowed")!;
  const valSecReason = document.getElementById("val-sec-reason")!;

  // Secure Communication & Recovery Telemetry Elements
  const valCommRecoveryState = document.getElementById("val-comm-recovery-state");
  const valCommSessionId = document.getElementById("val-comm-session-id");
  const valCommArqProgress = document.getElementById("val-comm-arq-progress");
  const valCommArqMetrics = document.getElementById("val-comm-arq-metrics");
  const valCommDecryptedPayload = document.getElementById("val-comm-decrypted-payload");

  // Communication Action Buttons
  const btnStartAuth = document.getElementById("btn-start-auth") as HTMLButtonElement | null;
  const btnStartTransfer = document.getElementById("btn-start-transfer") as HTMLButtonElement | null;
  const btnInjectFaults = document.getElementById("btn-inject-faults") as HTMLButtonElement | null;
  const btnSimulateLinkLoss = document.getElementById("btn-simulate-link-loss") as HTMLButtonElement | null;
  const btnResumeTransfer = document.getElementById("btn-resume-transfer") as HTMLButtonElement | null;

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

  let faultStateIndex = 0; // 0: Off, 1: Packet Loss 25%, 2: Tamper On

  // Initialize Simulator
  const simulator = new Simulator(container, DEFAULT_CONFIG, {
    onTelemetryUpdate: (snapshot: FullTelemetrySnapshot) => {
      updateHUD(snapshot);
    }
  });

  function updateHUD(s: FullTelemetrySnapshot): void {
    const g = s.gimbal;
    const ts = s.targetScreen;

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
    valZoom.textContent = `${s.zoom.toFixed(1)}x (${(42.0 / s.zoom).toFixed(1)}°)`;
    valModeTag.textContent = s.cameraMode.replace("_", " ");

    // Heading Compass Tape
    let hdgDeg = Math.round((-s.uav1Attitude.yaw * 180 / Math.PI + 360) % 360);
    compassDisplay.textContent = `HDG ${hdgDeg.toString().padStart(3, "0")}° | EL ${elDeg}°`;

    // Signal Strength Meter
    const signalPercent = Math.round(g.signalStrength * 100);
    valSignalRssi.textContent = `${signalPercent}%`;
    signalBar.style.width = `${signalPercent}%`;

    // 2. Optical Link Status & Target Box Tracking
    if (g.state === "LOCKED") {
      badgeLock.textContent = "BEACON LOCKED";
      badgeLock.className = "badge badge-locked";
      valGimbalState.className = "data-val accent-green";

      valSearchSector.textContent = "CARRIER LOCKED [TRACKING]";
      valSearchSector.className = "data-val accent-green";
      valSearchTime.textContent = `LOCKED (${g.lockDuration.toFixed(1)}s)`;

      valOpticalLink.textContent = "OPTICAL LASER LINK ACTIVE";
      valOpticalLink.className = "data-val accent-green";

      signalBar.className = "signal-bar-fill locked";

      if (ts.inFront) {
        targetBox.className = "";
        targetBox.classList.add("locked");
        targetBox.style.left = `${ts.x}px`;
        targetBox.style.top = `${ts.y}px`;
        targetBoxLabel.textContent = `LOCKED [${g.trackingErrorMrad.toFixed(1)} mrad]`;
      } else {
        targetBox.className = "hidden";
      }
    } else if (g.state === "ACQUIRING") {
      badgeLock.textContent = "ACQUIRING BEACON";
      badgeLock.className = "badge badge-searching";
      valGimbalState.className = "data-val accent-cyan";

      valSearchSector.textContent = "INTERCEPT [COARSE ALIGN]";
      valSearchSector.className = "data-val accent-cyan";
      valSearchTime.textContent = "DETECTED";

      valOpticalLink.textContent = "COARSE ALIGNING...";
      valOpticalLink.className = "data-val accent-cyan";

      signalBar.className = "signal-bar-fill";

      if (ts.inFront) {
        targetBox.className = "";
        targetBox.classList.add("acquiring");
        targetBox.style.left = `${ts.x}px`;
        targetBox.style.top = `${ts.y}px`;
        targetBoxLabel.textContent = "ACQUIRING BEACON";
      } else {
        targetBox.className = "hidden";
      }
    } else {
      badgeLock.textContent = "SEARCHING AIRSPACE";
      badgeLock.className = "badge badge-searching";
      valGimbalState.className = "data-val accent-amber";

      valSearchSector.textContent = g.currentSector;
      valSearchSector.className = "data-val accent-amber";
      valSearchTime.textContent = `${g.searchTime.toFixed(1)}s / ${g.searchDuration.toFixed(1)}s`;

      valOpticalLink.textContent = "SEARCHING UNCERTAINTY CONE";
      valOpticalLink.className = "data-val accent-amber";

      signalBar.className = "signal-bar-fill";
      targetBox.className = "hidden";
    }

    // 3. Update Member 2 & Member 3 Security Panel HUD
    if (s.bridgeConnected && s.bridgeTelemetry) {
      const bt = s.bridgeTelemetry;
      valBackendStatus.textContent = "ONLINE (WS 8765)";
      valBackendStatus.className = "data-val accent-green";

      valSecTrackingState.textContent = bt.tracking_state.mode.toUpperCase();
      valSecTrackingState.className = bt.tracking_state.mode.toUpperCase() === "LOCKED" ? "data-val accent-green" : "data-val accent-amber";

      valSecBeaconVisible.textContent = ts.inFov ? "VISIBLE (FOV)" : "OUT OF FOV";
      valSecConfidence.textContent = `${(bt.tracking_state.confidence * 100).toFixed(0)}%`;
      valSecMotionConsistency.textContent = bt.tracking_state.motion_consistency ? "PASSED (0.95)" : "FAIL (0.00)";
      valSecMotionConsistency.className = bt.tracking_state.motion_consistency ? "data-val accent-green" : "data-val accent-red";

      valSecTrustState.textContent = bt.security_state.state;
      valSecTrustState.className = bt.security_state.state === "AUTHORIZED" || bt.security_state.state === "SECURE" ? "data-val accent-green" : "data-val accent-amber";

      valSecAuth.textContent = bt.security_state.authentication_valid ? "AUTHENTICATED (Ed25519)" : "UNAUTHENTICATED";
      valSecAuth.className = bt.security_state.authentication_valid ? "data-val accent-green" : "data-val accent-red";

      valSecAuthorization.textContent = bt.security_state.trust_authorized ? "AUTHORIZED" : "UNTRUSTED";
      valSecAuthorization.className = bt.security_state.trust_authorized ? "data-val accent-green" : "data-val accent-red";

      valSecTxAllowed.textContent = bt.security_state.transmission_allowed ? "YES (PERMITTED)" : "NO (BLOCKED)";
      valSecTxAllowed.className = bt.security_state.transmission_allowed ? "data-val accent-green" : "data-val accent-red";

      valSecReason.textContent = bt.security_state.reason;

      // 4. Update Secure Transport & Link Recovery Telemetry HUD
      if (bt.communication_telemetry && valCommRecoveryState && valCommSessionId && valCommArqProgress && valCommArqMetrics && valCommDecryptedPayload) {
        const comm = bt.communication_telemetry;

        valCommRecoveryState.textContent = comm.recovery_state;
        valCommRecoveryState.className = comm.recovery_state === "CONNECTED" || comm.recovery_state === "COMPLETED" ? "data-val accent-green" : "data-val accent-amber";

        const shortSession = comm.session_id ? comm.session_id.substring(0, 8) + "..." : "NONE";
        valCommSessionId.textContent = `${shortSession} (EPOCH ${comm.tracking_epoch})`;

        const pct = (comm.transfer_completion * 100).toFixed(0);
        valCommArqProgress.textContent = `${comm.acknowledged_packets} / ${comm.total_packets} PKTS (${pct}%)`;

        valCommArqMetrics.textContent = `Retx:${comm.retransmissions} | Loss:${comm.packet_loss} | Rej:${comm.tamper_rejections}`;
        valCommDecryptedPayload.textContent = comm.decrypted_payload ? `"${comm.decrypted_payload}"` : "N/A";
      }
    } else {
      valBackendStatus.textContent = "DISCONNECTED (DEV MODE)";
      valBackendStatus.className = "data-val accent-amber";

      valSecTrackingState.textContent = g.state;
      valSecBeaconVisible.textContent = ts.inFov ? "VISIBLE" : "HIDDEN";
      valSecConfidence.textContent = g.state === "LOCKED" ? "95%" : "0%";
      valSecMotionConsistency.textContent = "STANDBY";
      valSecTrustState.textContent = "UNTRUSTED";
      valSecAuth.textContent = "DISCONNECTED";
      valSecAuthorization.textContent = "BLOCKED";
      valSecTxAllowed.textContent = "NO (BLOCKED)";
      valSecTxAllowed.className = "data-val accent-red";
      valSecReason.textContent = "BACKEND DISCONNECTED (OFFLINE DEV MODE)";
    }
  }

  // Communication Action Buttons Setup
  if (btnStartAuth) {
    btnStartAuth.addEventListener("click", () => {
      simulator.getBridgeClient().startAuthentication();
    });
  }

  if (btnStartTransfer) {
    btnStartTransfer.addEventListener("click", () => {
      simulator.getBridgeClient().startTransfer("ASTRA LINK SECURE TEST PAYLOAD");
    });
  }

  if (btnInjectFaults) {
    btnInjectFaults.addEventListener("click", () => {
      faultStateIndex = (faultStateIndex + 1) % 3;
      if (faultStateIndex === 0) {
        btnInjectFaults.textContent = "Faults: Off";
        simulator.getBridgeClient().setFaultInjection(0.0, 0.0, false);
      } else if (faultStateIndex === 1) {
        btnInjectFaults.textContent = "Loss: 25%";
        simulator.getBridgeClient().setFaultInjection(0.25, 0.0, false);
      } else {
        btnInjectFaults.textContent = "Tamper: On";
        simulator.getBridgeClient().setFaultInjection(0.0, 0.0, true);
      }
    });
  }

  if (btnSimulateLinkLoss) {
    btnSimulateLinkLoss.addEventListener("click", () => {
      simulator.breakLock();
      simulator.getBridgeClient().simulateLinkLoss();
    });
  }

  if (btnResumeTransfer) {
    btnResumeTransfer.addEventListener("click", () => {
      simulator.forceLock();
      simulator.getBridgeClient().resumeTransfer();
    });
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
