export interface BridgeDetectionPayload {
  type: "detection_telemetry";
  timestamp: number;
  frame_id: number;
  centroid_x: number | null;
  centroid_y: number | null;
  confidence: number;
  visible: boolean;
}

export interface BridgeTelemetryResponse {
  type: "telemetry_response";
  timestamp: number;
  frame_id: number;
  tracking_state: {
    mode: string;
    predicted_x: number;
    predicted_y: number;
    angular_x: number;
    angular_y: number;
    velocity_x: number;
    velocity_y: number;
    motion_consistency: boolean;
    confidence: number;
    time_since_last_detection: number;
  };
  camera_command: {
    pan_command: number;
    tilt_command: number;
    slew_rate: [number, number];
    command_mode: string;
  };
  security_state: {
    state: string;
    trust_authorized: boolean;
    tracking_valid: boolean;
    motion_consistent: boolean;
    authentication_valid: boolean;
    freshness_valid: boolean;
    physical_valid: boolean;
    transmission_allowed: boolean;
    reason: string;
  };
}

export interface BridgeStatusCallbacks {
  onStatusChange?: (connected: boolean) => void;
  onTelemetryResponse?: (data: BridgeTelemetryResponse) => void;
}

export class PythonBridgeClient {
  private ws: WebSocket | null = null;
  private connected: boolean = false;
  private serverUrl: string;
  private callbacks: BridgeStatusCallbacks = {};
  private reconnectTimer: any = null;

  constructor(serverUrl: string = "ws://127.0.0.1:8765", callbacks?: BridgeStatusCallbacks) {
    this.serverUrl = serverUrl;
    if (callbacks) this.callbacks = callbacks;
  }

  public connect(): void {
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      return;
    }

    try {
      this.ws = new WebSocket(this.serverUrl);

      this.ws.onopen = () => {
        this.connected = true;
        console.log("[BridgeClient] Connected to Python Security & Tracking Gateway:", this.serverUrl);
        if (this.callbacks.onStatusChange) {
          this.callbacks.onStatusChange(true);
        }
        if (this.reconnectTimer) {
          clearTimeout(this.reconnectTimer);
          this.reconnectTimer = null;
        }
      };

      this.ws.onmessage = (event) => {
        try {
          const response = JSON.parse(event.data);
          if (response.type === "telemetry_response" && this.callbacks.onTelemetryResponse) {
            this.callbacks.onTelemetryResponse(response as BridgeTelemetryResponse);
          }
        } catch (e) {
          console.error("[BridgeClient] Message parse error:", e);
        }
      };

      this.ws.onclose = () => {
        this.setDisconnected();
      };

      this.ws.onerror = () => {
        this.setDisconnected();
      };
    } catch (e) {
      this.setDisconnected();
    }
  }

  private setDisconnected(): void {
    if (this.connected) {
      this.connected = false;
      console.warn("[BridgeClient] Disconnected from Python Gateway. Entering offline dev mode.");
      if (this.callbacks.onStatusChange) {
        this.callbacks.onStatusChange(false);
      }
    }
    this.scheduleReconnect();
  }

  private scheduleReconnect(): void {
    if (!this.reconnectTimer) {
      this.reconnectTimer = setTimeout(() => {
        this.reconnectTimer = null;
        this.connect();
      }, 3000);
    }
  }

  public isConnected(): boolean {
    return this.connected;
  }

  public sendDetection(payload: BridgeDetectionPayload): void {
    if (this.connected && this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(payload));
    }
  }

  public disconnect(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.connected = false;
  }
}
