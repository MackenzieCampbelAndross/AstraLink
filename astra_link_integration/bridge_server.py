"""Astra Link Telemetry Bridge Server.

Provides a real-time WebSocket service linking Member 1 (TypeScript/Three.js frontend)
to Member 2 (Python Optical Tracker) and Member 3 (Security & Trust Layer).
"""

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import websockets

# Ensure Member 2 and Member 3 source paths are available in sys.path
_repo_root = Path(__file__).resolve().parent.parent
_m2_src = _repo_root / "astra-link-member2" / "src"
_m3_root = _repo_root / "astra_link_member3"
_m3_src = _repo_root / "astra_link_member3" / "src"

if _m2_src.exists() and str(_m2_src) not in sys.path:
    sys.path.insert(0, str(_m2_src))
if _m3_src.exists() and str(_m3_src) not in sys.path:
    sys.path.insert(0, str(_m3_src))
if _m3_root.exists() and str(_m3_root) not in sys.path:
    sys.path.insert(0, str(_m3_root))

from astra_link_tracking.models.interfaces import DetectionResult, TrackingMode
from astra_link_tracking.tracking.tracker import Tracker
from astra_link_integration.adapter import TrackingAdapter
from astra_link_integration.pipeline import IntegratedTrackingSecurityPipeline
from astra_link_integration.secure_communication_manager import SecureCommunicationManager
from src.trust.security_state import SecurityState

logging.basicConfig(level=logging.INFO, format="[BridgeServer] %(levelname)s - %(message)s")


class AstraLinkBridgeServer:
    """Real-time WebSocket server connecting Member 1 simulation to Members 2 & 3."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8765):
        self.host = host
        self.port = port
        self.tracker = Tracker()
        self.pipeline = IntegratedTrackingSecurityPipeline(min_motion_consistency=0.80)
        self.comm_mgr = SecureCommunicationManager()
        self.terminal_id = "T1"
        self.remote_terminal_id = "T2"
        self.authenticated = True  # Mutual authentication state
        self.freshness = True
        self.last_m2_state = None
        self.last_sec_eval = None

    def process_message(self, message_str: str) -> Dict[str, Any]:
        """Process incoming JSON message from Member 1 and return TelemetryResponse."""
        try:
            data = json.loads(message_str)
        except Exception as e:
            return {"type": "error", "reason": f"INVALID_JSON: {e}"}

        if not isinstance(data, dict):
            return {"type": "error", "reason": "MALFORMED_MESSAGE_PAYLOAD_NOT_DICT"}

        msg_type = data.get("type", "detection_telemetry")

        if msg_type == "ping":
            return {"type": "pong", "status": "connected"}

        if msg_type == "set_auth_state":
            self.authenticated = bool(data.get("authenticated", True))
            self.freshness = bool(data.get("freshness", True))
            return {
                "type": "auth_state_ack",
                "authenticated": self.authenticated,
                "freshness": self.freshness,
            }

        # Secure Communication Operations
        if msg_type == "start_authentication":
            res = self.comm_mgr.start_authentication()
            return {"type": "authentication_response", **res}

        if msg_type == "start_transfer":
            payload_str = str(data.get("payload", "ASTRA LINK SECURE TEST PAYLOAD"))
            sec_eval = self.last_sec_eval
            if sec_eval is None and self.last_m2_state is not None:
                _, _, sec_eval = self.pipeline.process_telemetry(self.last_m2_state, self.terminal_id, self.remote_terminal_id, self.authenticated, self.freshness)

            res = self.comm_mgr.start_transfer(payload_str, sec_eval)
            return {"type": "transfer_start_response", **res}

        if msg_type == "inject_faults":
            loss_rate = float(data.get("loss_rate", 0.0))
            ack_loss_rate = float(data.get("ack_loss_rate", 0.0))
            tamper_enabled = bool(data.get("tamper_enabled", False))
            self.comm_mgr.set_fault_injection(loss_rate, ack_loss_rate, tamper_enabled)
            return {"type": "faults_injected_ack", **self.comm_mgr.get_telemetry()["fault_injection"]}

        if msg_type == "simulate_link_loss":
            res = self.comm_mgr.simulate_link_loss(reason=str(data.get("reason", "USER_SIMULATED_LINK_LOSS")))
            return {"type": "link_loss_response", **res}

        if msg_type == "resume_transfer":
            sec_eval = self.last_sec_eval
            if sec_eval is None and self.last_m2_state is not None:
                _, _, sec_eval = self.pipeline.process_telemetry(self.last_m2_state, self.terminal_id, self.remote_terminal_id, self.authenticated, self.freshness)

            res = self.comm_mgr.reacquire_and_resume(sec_eval)
            return {"type": "resume_response", **res}

        # Parse DetectionResult payload
        try:
            timestamp = float(data.get("timestamp", 0.0))
            frame_id = int(data.get("frame_id", 0))
            cx = data.get("centroid_x")
            cy = data.get("centroid_y")
            confidence = float(data.get("confidence", 0.0))
            visible = bool(data.get("visible", False))

            centroid_x = float(cx) if cx is not None else None
            centroid_y = float(cy) if cy is not None else None

            detection = DetectionResult(
                timestamp=timestamp,
                frame_id=frame_id,
                centroid_x=centroid_x,
                centroid_y=centroid_y,
                confidence=confidence,
                visible=visible,
            )
        except Exception as e:
            return {"type": "error", "reason": f"MALFORMED_DETECTION: {e}"}

        # 1. Member 2 Tracker update
        m2_state, camera_cmd = self.tracker.update(detection)
        self.last_m2_state = m2_state

        # 2. Member 3 Security Pipeline evaluation
        m3_state, trust_result, auth_result = self.pipeline.process_telemetry(
            m2_tracking_state=m2_state,
            terminal_id=self.terminal_id,
            remote_terminal_id=self.remote_terminal_id,
            authentication_valid=self.authenticated,
            freshness_valid=self.freshness,
        )
        self.last_sec_eval = auth_result

        # 3. Advance active secure communication transfer step
        self.comm_mgr.step_transfer(auth_result)

        # 4. Format response preserving Member 2 & Member 3 semantics
        response = {
            "type": "telemetry_response",
            "timestamp": timestamp,
            "frame_id": frame_id,
            "tracking_state": {
                "mode": m2_state.state.value,
                "predicted_x": float(m2_state.predicted_x),
                "predicted_y": float(m2_state.predicted_y),
                "angular_x": float(m2_state.angular_x),
                "angular_y": float(m2_state.angular_y),
                "velocity_x": float(m2_state.velocity_x),
                "velocity_y": float(m2_state.velocity_y),
                "motion_consistency": bool(m2_state.motion_consistency),
                "confidence": float(m2_state.confidence),
                "time_since_last_detection": float(m2_state.time_since_last_detection),
            },
            "camera_command": {
                "pan_command": float(camera_cmd.pan_command),
                "tilt_command": float(camera_cmd.tilt_command),
                "slew_rate": [float(camera_cmd.slew_rate[0]), float(camera_cmd.slew_rate[1])],
                "command_mode": str(camera_cmd.command_mode),
            },
            "security_state": {
                "state": "SECURE" if auth_result.allowed else "BLOCKED",
                "trust_authorized": trust_result.trust_authorized,
                "tracking_valid": trust_result.tracking_valid,
                "motion_consistent": trust_result.motion_consistent,
                "authentication_valid": trust_result.authentication_valid,
                "freshness_valid": trust_result.freshness_valid,
                "physical_valid": trust_result.physical_valid,
                "transmission_allowed": auth_result.allowed,
                "reason": auth_result.reason,
            },
            "communication_telemetry": self.comm_mgr.get_telemetry(),
        }

        return response

    async def handle_client(self, websocket: websockets.WebSocketServerProtocol):
        """Handle continuous WebSocket client connection."""
        client_address = websocket.remote_address
        logging.info(f"Client connected: {client_address}")
        try:
            async for message in websocket:
                response = self.process_message(message)
                await websocket.send(json.dumps(response))
        except websockets.exceptions.ConnectionClosedOK:
            logging.info(f"Client disconnected cleanly: {client_address}")
        except websockets.exceptions.ConnectionClosedError as e:
            logging.warning(f"Client disconnected with error: {client_address} - {e}")
        except Exception as e:
            logging.error(f"Unexpected error handling client {client_address}: {e}")

    async def start(self):
        """Start async WebSocket server."""
        logging.info(f"Starting Astra Link Telemetry Bridge Server on ws://{self.host}:{self.port}...")
        async with websockets.serve(self.handle_client, self.host, self.port):
            await asyncio.Future()  # Keep server running


def main():
    server = AstraLinkBridgeServer()
    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        logging.info("Server shutting down cleanly.")


if __name__ == "__main__":
    main()
