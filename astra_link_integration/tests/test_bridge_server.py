"""Integration tests for Astra Link Telemetry Bridge Server."""

import json
import pytest
from astra_link_integration.bridge_server import AstraLinkBridgeServer


def test_bridge_server_ping():
    """Verify ping message returns pong status."""
    server = AstraLinkBridgeServer()
    response = server.process_message(json.dumps({"type": "ping"}))

    assert response["type"] == "pong"
    assert response["status"] == "connected"


def test_bridge_server_valid_detection_telemetry():
    """Verify valid detection telemetry processes through Member 2 & 3 and returns complete response."""
    server = AstraLinkBridgeServer()

    payload = {
        "type": "detection_telemetry",
        "timestamp": 10.5,
        "frame_id": 101,
        "centroid_x": 320.0,
        "centroid_y": 240.0,
        "confidence": 0.95,
        "visible": True,
    }

    # Process consecutive frames to establish LOCKED state
    response = None
    for i in range(1, 5):
        payload["frame_id"] = i
        payload["timestamp"] = 0.05 * i
        response = server.process_message(json.dumps(payload))

    assert response["type"] == "telemetry_response"
    assert response["timestamp"] == 0.20
    assert response["frame_id"] == 4

    # Verify Member 2 tracking_state output
    ts = response["tracking_state"]
    assert ts["mode"] == "locked"
    assert isinstance(ts["predicted_x"], float)
    assert isinstance(ts["predicted_y"], float)

    # Verify camera_command output
    cc = response["camera_command"]
    assert isinstance(cc["pan_command"], float)
    assert isinstance(cc["tilt_command"], float)

    # Verify Member 3 security_state output
    sec = response["security_state"]
    assert sec["state"] == "AUTHORIZED"
    assert sec["trust_authorized"] is True
    assert sec["transmission_allowed"] is True


def test_bridge_server_unauthenticated_state_blocks_transmission():
    """Verify set_auth_state message can toggle authentication and block transmission gate."""
    server = AstraLinkBridgeServer()

    # Disable authentication
    server.process_message(json.dumps({"type": "set_auth_state", "authenticated": False}))

    payload = {
        "type": "detection_telemetry",
        "timestamp": 1.0,
        "frame_id": 1,
        "centroid_x": 320.0,
        "centroid_y": 240.0,
        "confidence": 0.95,
        "visible": True,
    }

    response = server.process_message(json.dumps(payload))

    sec = response["security_state"]
    assert sec["authentication_valid"] is False
    assert sec["transmission_allowed"] is False
    assert isinstance(sec["reason"], str) and len(sec["reason"]) > 0


def test_bridge_server_malformed_json_handling():
    """Verify malformed JSON payload returns error response safely without crash."""
    server = AstraLinkBridgeServer()
    response = server.process_message("NOT_VALID_JSON{{{")

    assert response["type"] == "error"
    assert "INVALID_JSON" in response["reason"]


def test_bridge_server_invalid_field_types_handling():
    """Verify bad field types in detection payload return error response safely."""
    server = AstraLinkBridgeServer()

    payload = {
        "type": "detection_telemetry",
        "timestamp": "INVALID_TIMESTAMP_STRING",
        "frame_id": "NOT_AN_INT",
    }

    response = server.process_message(json.dumps(payload))

    assert response["type"] == "error"
    assert "MALFORMED_DETECTION" in response["reason"]
