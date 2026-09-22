"""Astra Link Telemetry Bridge Server.

Provides a real-time WebSocket service linking Member 1 (TypeScript/Three.js frontend)
to Member 2 (Python Optical Tracker) and Member 3 (Security & Trust Layer).

Architecture:
    Frontend (Member 1)
           │
           ▼ WebSocket (ws://127.0.0.1:8765)
    bridge_server.py
           │
           ├── 1. Parse DetectionResult JSON
           ├── 2. Run Member 2 Tracker.update()
           ├── 3. Adapt M2 TrackingState via TrackingAdapter
           ├── 4. Evaluate Member 3 TrustEngine & TransmissionAuthorizationGate
           └── 5. Send TelemetryResponse JSON back to Frontend
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

if _m2_src.exists() and str(_m2_src) not in sys.path:
    sys.path.insert(0, str(_m2_src))
if _m3_root.exists() and str(_m3_root) not in sys.path:
    sys.path.insert(0, str(_m3_root))

from astra_link_tracking.models.interfaces import DetectionResult, TrackingMode
from astra_link_tracking.tracking.tracker import Tracker
from astra_link_integration.adapter import TrackingAdapter
from astra_link_integration.pipeline import IntegratedTrackingSecurityPipeline
from src.trust.security_state import SecurityState

logging.basicConfig(level=logging.INFO, format="[BridgeServer] %(levelname)s - %(message)s")


class AstraLinkBridgeServer:
    """Real-time WebSocket server connecting Member 1 simulation to Members 2 & 3."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8765):
        self.host = host
        self.port = port
        self.tracker = Tracker()
        self.pipeline = IntegratedTrackingSecurityPipeline(min_motion_consistency=0.80)
        self.terminal_id = "T1"
        self.remote_terminal_id = "T2"
        self.authenticated = True  # Mutual authentication state
        self.freshness = True

    def process_message(self, message_str: str) -> Dict[str, Any]:
        """Process incoming JSON message from Member 1 and return TelemetryResponse.

        Args:
            message_str: Raw JSON message string received from WebSocket client.

        Returns:
            Dictionary response payload to send back to client.
        """
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

        # Parse DetectionResult
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

        # 2. Member 3 Security Pipeline evaluation
        m3_state, trust_result, auth_result = self.pipeline.process_telemetry(
            m2_tracking_state=m2_state,
            terminal_id=self.terminal_id,
            remote_terminal_id=self.remote_terminal_id,
            authentication_valid=self.authenticated,
            freshness_valid=self.freshness,
        )

        # 3. Format response preserving Member 2 & Member 3 semantics
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
                "slew_rate": list(camera_cmd.slew_rate) if camera_cmd.slew_rate else [0.0, 0.0],
                "command_mode": str(camera_cmd.command_mode),
            },
            "security_state": {
                "state": trust_result.security_state.value,
                "trust_authorized": bool(trust_result.trust_authorized),
                "tracking_valid": bool(trust_result.tracking_valid),
                "motion_consistent": bool(trust_result.motion_consistent),
                "authentication_valid": bool(trust_result.authentication_valid),
                "freshness_valid": bool(trust_result.freshness_valid),
                "physical_valid": bool(trust_result.physical_valid),
                "transmission_allowed": bool(auth_result.allowed),
                "reason": str(auth_result.reason),
            },
        }

        return response

    async def handle_client(self, websocket, path=None):
        """Handle WebSocket connection lifecycle for Member 1 frontend."""
        logging.info("Member 1 Frontend connected to Python Bridge Server.")
        try:
            async for message in websocket:
                response = self.process_message(message)
                await websocket.send(json.dumps(response))
        except websockets.exceptions.ConnectionClosed:
            logging.info("Member 1 Frontend disconnected.")
        except Exception as e:
            logging.error(f"Error in websocket connection: {e}")

    async def start(self):
        """Start async WebSocket server."""
        logging.info(f"Starting Astra Link Telemetry Bridge Server on ws://{self.host}:{self.port}...")
        async with websockets.serve(self.handle_client, self.host, self.port):
            await asyncio.Future()  # Run forever


def main():
    server = AstraLinkBridgeServer()
    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        logging.info("Bridge Server stopped by user.")


if __name__ == "__main__":
    main()
