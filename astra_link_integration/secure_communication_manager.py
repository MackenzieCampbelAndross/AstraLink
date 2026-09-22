"""Secure Communication Manager connecting Member 3 Authentication, Session, Transport, and Recovery stack."""

import hashlib
import json
import logging
import os
import random
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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

from src.authentication.mutual_auth import (
    AuthenticationSession,
    AuthState,
    create_challenge,
    create_response,
    verify_response,
)
from src.identity import TerminalIdentity, TerminalRegistry, generate_credentials
from src.recovery.checkpoint import Checkpoint, CheckpointManager
from src.recovery.resume import ResumeProtocolHandler, ResumeRequest
from src.recovery.session_recovery import RecoveryState, RecoveryStateMachine
from src.session import SessionManager
from src.tracking.tracking_state import TrackingState as Member3TrackingState
from src.transport.cipher import InvalidPacketError, PacketCipher
from src.transport.packet import EncryptedPacket
from src.transport.packetizer import Packetizer, PayloadReassembler
from src.transport.selective_repeat import ReceiverWindow, SenderWindow
from src.trust import SecurityLogger, TransmissionAuthorizationGate, TrustEngine, TrustEvaluationResult

logger = logging.getLogger("SecureCommunicationManager")


class SecureCommunicationManager:
    """Orchestrates end-to-end Member 3 authentication, session management, AES-GCM transport, ARQ, and recovery."""

    def __init__(self, checkpoint_dir: Optional[str] = None):
        self.checkpoint_dir = checkpoint_dir or tempfile.mkdtemp(prefix="astralink_checkpoints_")
        os.makedirs(self.checkpoint_dir, exist_ok=True)
        self.checkpoint_manager = CheckpointManager(checkpoint_dir=self.checkpoint_dir)

        # Identity & Credentials setup for T1 (Ground Station/Sender) and T2 (Satellite/Receiver)
        self.t1_creds = generate_credentials("T1")
        self.t2_creds = generate_credentials("T2")
        self.t1_identity = TerminalIdentity(self.t1_creds)
        self.t2_identity = TerminalIdentity(self.t2_creds)

        self.registry = TerminalRegistry()
        self.registry.register_public_credentials(self.t1_creds.public_credentials)
        self.registry.register_public_credentials(self.t2_creds.public_credentials)

        self.session_manager = SessionManager(session_lifetime_seconds=3600.0)
        self.trust_engine = TrustEngine()
        self.sec_logger = SecurityLogger()

        # Auth & Session State
        self.authenticated: bool = False
        self.current_session_id: Optional[str] = None
        self.session_history: List[str] = []

        # Transport & Transfer State
        self.transfer_id: Optional[str] = None
        self.payload_bytes: Optional[bytes] = None
        self.payload_hash: Optional[str] = None
        self.total_packets: int = 0
        self.chunks: List[Tuple[int, bytes]] = []
        self.encrypted_packets: Dict[int, EncryptedPacket] = {}
        self.acknowledged: Dict[int, bool] = {}
        self.sender_window: Optional[SenderWindow] = None
        self.receiver_window: Optional[ReceiverWindow] = None
        self.reassembler: Optional[PayloadReassembler] = None

        # Fault Injection Settings
        self.loss_rate: float = 0.0
        self.ack_loss_rate: float = 0.0
        self.tamper_enabled: bool = False

        # Metrics
        self.retransmissions: int = 0
        self.packet_loss_count: int = 0
        self.tamper_rejections: int = 0
        self.duplicate_packets: int = 0
        self.bytes_transferred: int = 0
        self.transfer_completed: bool = False
        self.decrypted_payload_str: Optional[str] = None

        # Link Recovery State
        self.recovery_sm: Optional[RecoveryStateMachine] = None
        self.saved_checkpoint: Optional[Checkpoint] = None

    def start_authentication(self) -> Dict[str, Any]:
        """Perform mutual authentication between T1 and T2 and establish an X25519 session."""
        try:
            # Phase 2 Mutual Auth Challenge Response
            epoch = 1 if not self.recovery_sm else self.recovery_sm.tracking_epoch
            challenge = create_challenge(initiator_id="T1", responder_id="T2", tracking_epoch=epoch)
            resp = create_response(challenge, self.t2_identity)
            auth_ok = verify_response(challenge, resp, self.registry)

            if not auth_ok:
                self.authenticated = False
                return {"success": False, "reason": "MUTUAL_AUTH_VERIFICATION_FAILED"}

            # Establish Session via SessionManager
            active_session = self.session_manager.establish_session(
                initiator_id="T1",
                responder_id="T2",
                tracking_epoch=epoch,
                authentication_valid=True,
                trust_authorized=True,
            )
            session_id = active_session.session_id

            self.authenticated = True
            self.current_session_id = session_id
            self.session_history.append(session_id)

            if self.recovery_sm:
                self.recovery_sm.current_session_id = session_id

            logger.info(f"Mutual authentication succeeded. Session established: {session_id}")
            return {
                "success": True,
                "session_id": session_id,
                "authenticated": True,
            }
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            self.authenticated = False
            return {"success": False, "reason": str(e)}

    def start_transfer(self, payload_str: str, security_eval_result: Any) -> Dict[str, Any]:
        """Initiate payload encryption and ARQ packet transfer under strict authorization gate."""
        if not self.authenticated or not self.current_session_id:
            return {"success": False, "reason": "NOT_AUTHENTICATED"}

        # Enforce Security Gate
        is_allowed = getattr(security_eval_result, "transmission_allowed", getattr(security_eval_result, "allowed", False))
        if not security_eval_result or not is_allowed:
            reason = getattr(security_eval_result, "reason", "SECURITY_GATE_BLOCKED")
            return {"success": False, "reason": f"TRANSMISSION_BLOCKED: {reason}"}

        # Session validity check
        if not self.session_manager.is_session_valid(self.current_session_id):
            return {"success": False, "reason": "SESSION_EXPIRED"}

        session = self.session_manager.get_session(self.current_session_id)
        directional_key = session.derived_keys.t1_to_t2_key

        self.payload_bytes = payload_str.encode("utf-8")
        self.payload_hash = hashlib.sha256(self.payload_bytes).hexdigest()
        self.transfer_id = f"TX_{int(time.time() * 1000)}"

        # Packetize payload into small chunks (packet_size=16 bytes for multi-packet demo)
        packetizer = Packetizer(packet_size=16)
        self.chunks = packetizer.packetize(self.payload_bytes, self.transfer_id)
        self.total_packets = len(self.chunks)

        # Encrypt packets with directional AES-GCM key
        self.encrypted_packets = {}
        for seq, chunk_bytes in self.chunks:
            pkt = PacketCipher.encrypt(
                key=directional_key,
                plaintext=chunk_bytes,
                protocol_version="1.0",
                session_id=self.current_session_id,
                transfer_id=self.transfer_id,
                sequence_number=seq,
                direction="T1_TO_T2",
            )
            self.encrypted_packets[seq] = pkt
            self.acknowledged[seq] = False

        # Windows & Reassembler setup
        self.sender_window = SenderWindow(window_size=8)
        self.receiver_window = ReceiverWindow()
        self.reassembler = PayloadReassembler()

        # Recovery state machine setup
        initial_epoch = 1 if not self.recovery_sm else self.recovery_sm.tracking_epoch
        self.recovery_sm = RecoveryStateMachine(
            transfer_id=self.transfer_id,
            initial_epoch=initial_epoch,
            initial_session_id=self.current_session_id,
        )

        self.transfer_completed = False
        self.decrypted_payload_str = None
        self.retransmissions = 0
        self.packet_loss_count = 0
        self.tamper_rejections = 0
        self.bytes_transferred = 0

        # Step initial packets into transmission stream
        self.step_transfer(security_eval_result)

        return {
            "success": True,
            "transfer_id": self.transfer_id,
            "total_packets": self.total_packets,
            "payload_bytes": len(self.payload_bytes),
        }

    def set_fault_injection(self, loss_rate: float, ack_loss_rate: float, tamper_enabled: bool):
        """Configure fault injection rates."""
        self.loss_rate = max(0.0, min(1.0, float(loss_rate)))
        self.ack_loss_rate = max(0.0, min(1.0, float(ack_loss_rate)))
        self.tamper_enabled = bool(tamper_enabled)

    def step_transfer(self, security_eval_result: Optional[Any] = None) -> None:
        """Advance packet transmission & ARQ ACKs by 1-2 packets per render loop."""
        if not self.transfer_id or self.transfer_completed:
            return

        # Check recovery state & security gate
        if self.recovery_sm and self.recovery_sm.state not in (RecoveryState.CONNECTED, RecoveryState.RESUMING):
            return

        is_allowed = getattr(security_eval_result, "transmission_allowed", getattr(security_eval_result, "allowed", False))
        if security_eval_result and not is_allowed:
            if self.recovery_sm and self.recovery_sm.state == RecoveryState.CONNECTED:
                self.simulate_link_loss("SECURITY_GATE_REVOKED")
            return

        if not self.current_session_id or not self.session_manager.is_session_valid(self.current_session_id):
            return

        session = self.session_manager.get_session(self.current_session_id)
        directional_key = session.derived_keys.t1_to_t2_key

        # Send packets sequentially within window
        for seq, packet in self.encrypted_packets.items():
            if self.acknowledged.get(seq, False):
                continue

            self.sender_window.add_sent_packet(packet)

            # Fault Injection: Packet Loss
            if self.loss_rate > 0.0 and random.random() < self.loss_rate:
                self.packet_loss_count += 1
                self.retransmissions += 1
                logger.info(f"[Fault Injection] Packet seq {seq} LOST in transit.")
                continue

            # Fault Injection: Packet Tampering
            pkt_to_process = packet
            if self.tamper_enabled and random.random() < 0.5:
                # Corrupt payload ciphertext bytes
                corrupted_ciphertext = bytearray(packet.ciphertext)
                if len(corrupted_ciphertext) > 0:
                    corrupted_ciphertext[0] ^= 0xFF
                pkt_to_process = EncryptedPacket(
                    protocol_version=packet.protocol_version,
                    session_id=packet.session_id,
                    transfer_id=packet.transfer_id,
                    sequence_number=packet.sequence_number,
                    direction=packet.direction,
                    iv=packet.iv,
                    tag=packet.tag,
                    ciphertext=bytes(corrupted_ciphertext),
                )
                logger.info(f"[Fault Injection] Packet seq {seq} TAMPERED.")

            # Attempt Decryption on Receiver Side
            try:
                decrypted_bytes = PacketCipher.decrypt(key=directional_key, packet=pkt_to_process)
            except InvalidPacketError:
                self.tamper_rejections += 1
                logger.warning(f"[Security Gate] Receiver rejected tampered packet seq {seq}! AES-GCM tag mismatch.")
                continue

            # Receiver Accepts Valid Packet
            ack_msg, deliverable_chunks, is_dup = self.receiver_window.process_received_packet(pkt_to_process, decrypted_bytes)
            if is_dup:
                self.duplicate_packets += 1

            for c_seq, c_bytes in deliverable_chunks:
                self.reassembler.accept_packet(c_seq, c_bytes)
                self.bytes_transferred += len(c_bytes)

            # Fault Injection: ACK Loss
            if self.ack_loss_rate > 0.0 and random.random() < self.ack_loss_rate:
                logger.info(f"[Fault Injection] ACK for seq {seq} LOST in transit.")
                continue

            # ACK received by Sender
            self.sender_window.process_ack(ack_msg)
            self.acknowledged[seq] = True

        # Check if transfer complete
        if self.reassembler and len(self.reassembler) >= self.total_packets and self.total_packets > 0:
            try:
                final_bytes = self.reassembler.reassemble()
                self.transfer_completed = True
                self.decrypted_payload_str = final_bytes.decode("utf-8")
                if self.recovery_sm:
                    self.recovery_sm.state = RecoveryState.COMPLETED
                logger.info(f"Secure Transfer Completed! Decrypted: '{self.decrypted_payload_str}'")
            except Exception as e:
                logger.error(f"Reassembly failure: {e}")

    def simulate_link_loss(self, reason: str = "OPTICAL_BEACON_LOST") -> Dict[str, Any]:
        """Trigger simulated link loss, stopping transmission and creating a verified checkpoint."""
        if not self.recovery_sm:
            return {"success": False, "reason": "NO_ACTIVE_TRANSFER"}

        # 1. Update recovery state machine
        self.recovery_sm.handle_link_loss(reason=reason)

        # 2. Find last confirmed sequence number
        last_confirmed = max([seq for seq, acked in self.acknowledged.items() if acked], default=-1)

        # 3. Create persistent checkpoint via CheckpointManager
        if self.transfer_id and self.payload_hash and self.current_session_id:
            ckpt = Checkpoint(
                transfer_id=self.transfer_id,
                total_packets=self.total_packets,
                last_confirmed=last_confirmed,
                next_expected=last_confirmed + 1,
                session_id=self.current_session_id,
                tracking_epoch=self.recovery_sm.tracking_epoch - 1,
                payload_hash=self.payload_hash,
                checkpoint_timestamp=time.time(),
            )
            self.checkpoint_manager.save_checkpoint(ckpt)
            self.saved_checkpoint = ckpt

        logger.info(
            f"Link lost. Recovery State: {self.recovery_sm.state.value}. Epoch: {self.recovery_sm.tracking_epoch}. Checkpointed at seq: {last_confirmed}"
        )
        return {
            "success": True,
            "recovery_state": self.recovery_sm.state.value,
            "tracking_epoch": self.recovery_sm.tracking_epoch,
            "last_confirmed": last_confirmed,
        }

    def reacquire_and_resume(self, security_eval_result: Any) -> Dict[str, Any]:
        """Execute full Phase 7 Link Recovery + Secure Resume protocol."""
        if not self.recovery_sm or not self.saved_checkpoint:
            return {"success": False, "reason": "NO_CHECKPOINT_TO_RESUME"}

        # 1. Reacquisition Check: Tracking must be locked & consistent
        tracking_valid = getattr(security_eval_result, "tracking_valid", getattr(security_eval_result, "allowed", True))
        if not security_eval_result or not tracking_valid:
            return {"success": False, "reason": "REACQUISITION_FAILED: TARGET_NOT_LOCKED"}

        # Handle Reacquisition -> state = REACQUIRING (LOCKED_UNVERIFIED)
        dummy_tracking = Member3TrackingState(
            timestamp=time.time(),
            tracking_state="LOCKED",
            predicted_x=320.0,
            predicted_y=240.0,
            angular_x=0.01,
            angular_y=0.01,
            velocity_x=0.0,
            velocity_y=0.0,
            motion_consistency=0.95,
        )
        self.recovery_sm.handle_reacquisition(dummy_tracking)

        # 2. Fresh Mutual Authentication -> state = AUTHENTICATING
        self.recovery_sm.transition_to_authenticating()
        auth_res = self.start_authentication()
        if not auth_res.get("success"):
            self.recovery_sm.handle_failure(f"REAUTHENTICATION_FAILED: {auth_res.get('reason')}")
            return {"success": False, "reason": f"REAUTHENTICATION_FAILED: {auth_res.get('reason')}"}

        self.recovery_sm.handle_authentication_success()

        # 3. Fresh X25519 Session Establishment -> state = ESTABLISHING_SESSION
        new_session_id = auth_res["session_id"]

        # Ensure fresh session key material!
        if len(self.session_history) > 1 and self.session_history[-1] == self.session_history[-2]:
            raise ValueError("Session key reuse detected!")

        self.recovery_sm.handle_session_establishment(new_session_id)

        # 4. Formulate ResumeRequest & Execute Resume Protocol Handler -> state = RESUMING
        self.recovery_sm.transition_to_resuming()

        resume_req = ResumeRequest(
            transfer_id=self.saved_checkpoint.transfer_id,
            total_packets=self.saved_checkpoint.total_packets,
            tracking_epoch=self.recovery_sm.tracking_epoch,
            session_id=new_session_id,
            sender_checkpoint=self.saved_checkpoint.last_confirmed,
            payload_hash=self.saved_checkpoint.payload_hash,
            timestamp=time.time(),
        )

        resume_resp = ResumeProtocolHandler.process_request(
            request=resume_req,
            expected_transfer_id=self.saved_checkpoint.transfer_id,
            expected_epoch=self.recovery_sm.tracking_epoch,
            expected_session_id=new_session_id,
            expected_payload_hash=self.saved_checkpoint.payload_hash,
            receiver_verified_checkpoint=self.saved_checkpoint.last_confirmed,
        )

        if resume_resp.status != "ACCEPTED":
            self.recovery_sm.handle_failure(resume_resp.reason)
            return {"success": False, "reason": f"RESUME_REJECTED: {resume_resp.reason}"}

        self.recovery_sm.handle_resume_validated()

        # Re-encrypt remaining packets (from last_confirmed + 1 onwards) using NEW session directional key!
        session = self.session_manager.get_session(new_session_id)
        new_key = session.derived_keys.t1_to_t2_key

        for seq, chunk_bytes in self.chunks:
            if seq > self.saved_checkpoint.last_confirmed:
                pkt = PacketCipher.encrypt(
                    key=new_key,
                    plaintext=chunk_bytes,
                    protocol_version="1.0",
                    session_id=new_session_id,
                    transfer_id=self.transfer_id,
                    sequence_number=seq,
                    direction="T1_TO_T2",
                )
                self.encrypted_packets[seq] = pkt

        resumption_point = resume_resp.receiver_verified_checkpoint + 1
        logger.info(f"Secure Resume Successful! Resuming from seq {resumption_point} with fresh session {new_session_id}")

        return {
            "success": True,
            "resumption_point": resumption_point,
            "new_session_id": new_session_id,
            "tracking_epoch": self.recovery_sm.tracking_epoch,
            "recovery_state": self.recovery_sm.state.value,
        }

    def get_telemetry(self) -> Dict[str, Any]:
        """Expose detailed real communication and recovery metrics for UI and bridge telemetry."""
        acked_count = sum(1 for acked in self.acknowledged.values() if acked)
        completion = (acked_count / self.total_packets) if self.total_packets > 0 else 0.0

        recovery_state_str = self.recovery_sm.state.value if self.recovery_sm else "IDLE"
        tracking_epoch = self.recovery_sm.tracking_epoch if self.recovery_sm else 1

        return {
            "authentication_state": "AUTHENTICATED" if self.authenticated else "UNAUTHENTICATED",
            "session_state": "ACTIVE" if (self.current_session_id and self.session_manager.is_session_valid(self.current_session_id)) else "INACTIVE",
            "session_id": self.current_session_id,
            "authorization_state": "AUTHORIZED" if self.authenticated else "UNAUTHORIZED",
            "transmission_allowed": self.authenticated and (self.recovery_sm.transmission_allowed if self.recovery_sm else True),
            "transfer_id": self.transfer_id,
            "total_packets": self.total_packets,
            "acknowledged_packets": acked_count,
            "retransmissions": self.retransmissions,
            "packet_loss": self.packet_loss_count,
            "tamper_rejections": self.tamper_rejections,
            "bytes_transferred": self.bytes_transferred,
            "transfer_completion": completion,
            "completed": self.transfer_completed,
            "recovery_state": recovery_state_str,
            "tracking_epoch": tracking_epoch,
            "decrypted_payload": self.decrypted_payload_str,
            "fault_injection": {
                "loss_rate": self.loss_rate,
                "ack_loss_rate": self.ack_loss_rate,
                "tamper_enabled": self.tamper_enabled,
            },
        }
