"""High-level RecoveryController coordinating link loss, checkpointing, reauthentication, new session creation, resume negotiation, and transmission resumption."""

import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple

from ..authentication import AuthenticationController
from ..identity import TerminalCredentials, TerminalRegistry
from ..optical_challenge import PhysicalConsistencyValidator, ProbeGenerator
from ..session import ActiveSession, SessionManager
from ..tracking.tracking_state import TrackingState
from ..trust import SecurityLogger, TransmissionAuthorizationGate, TrustEngine
from .checkpoint import Checkpoint, CheckpointManager, CheckpointRollbackError, CorruptedCheckpointError, InvalidCheckpointError
from .resume import ResumeProtocolHandler, ResumeRequest, ResumeResponse, ResumeValidationError
from .session_recovery import RecoveryState, RecoveryStateMachine


class RecoveryError(Exception):
    """Base exception for recovery operations."""
    pass


class MaxRecoveryAttemptsExceededError(RecoveryError):
    """Raised when recovery retries exceed the maximum configured threshold."""
    pass


@dataclass
class RecoveryMetrics:
    """Calculates empirical recovery metrics without fabricated values."""

    checkpoint_save_time_ms: float = 0.0
    reacquisition_duration_sec: float = 0.0
    reauthentication_latency_sec: float = 0.0
    session_establishment_latency_sec: float = 0.0
    resume_negotiation_latency_sec: float = 0.0
    packets_retransmitted_after_recovery: int = 0
    packets_recovered: int = 0
    recovery_attempts_count: int = 0
    success_count: int = 0
    total_attempts_count: int = 0

    @property
    def total_secure_recovery_time_sec(self) -> float:
        """T_secure_recovery = T_reacquisition + T_authentication + T_session + T_resume"""
        return round(
            self.reacquisition_duration_sec
            + self.reauthentication_latency_sec
            + self.session_establishment_latency_sec
            + self.resume_negotiation_latency_sec,
            4,
        )

    @property
    def recovery_success_rate(self) -> float:
        if self.total_attempts_count <= 0:
            return 0.0
        return round(self.success_count / self.total_attempts_count, 4)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "checkpoint_save_time_ms": self.checkpoint_save_time_ms,
            "reacquisition_duration_sec": self.reacquisition_duration_sec,
            "reauthentication_latency_sec": self.reauthentication_latency_sec,
            "session_establishment_latency_sec": self.session_establishment_latency_sec,
            "resume_negotiation_latency_sec": self.resume_negotiation_latency_sec,
            "total_secure_recovery_time_sec": self.total_secure_recovery_time_sec,
            "packets_retransmitted_after_recovery": self.packets_retransmitted_after_recovery,
            "packets_recovered": self.packets_recovered,
            "recovery_success_rate": self.recovery_success_rate,
        }


class RecoveryController:
    """Coordinates link interruption handling, persistent checkpointing, fresh mutual reauthentication,
    new session establishment, and authenticated resume protocol."""

    def __init__(
        self,
        transfer_id: str,
        sender_id: str = "T1",
        receiver_id: str = "T2",
        checkpoint_dir: str = "outputs/checkpoints",
        max_recovery_attempts: int = 3,
        recovery_timeout_ms: int = 5000,
        logger: Optional[SecurityLogger] = None,
    ):
        self.transfer_id = transfer_id
        self.sender_id = sender_id
        self.receiver_id = receiver_id
        self.max_recovery_attempts = max(1, int(max_recovery_attempts))
        self.recovery_timeout_ms = max(100, int(recovery_timeout_ms))
        self.logger = logger or SecurityLogger()

        self.checkpoint_manager = CheckpointManager(checkpoint_dir=checkpoint_dir)
        self.state_machine = RecoveryStateMachine(transfer_id=transfer_id)
        self.metrics = RecoveryMetrics()

        self.recovery_attempts: int = 0
        self.current_checkpoint: Optional[Checkpoint] = None
        self.active_session: Optional[ActiveSession] = None
        self._last_link_lost_timestamp: Optional[float] = None
        self._last_reacq_timestamp: Optional[float] = None

    def handle_link_interruption(
        self,
        total_packets: int,
        last_confirmed: int,
        next_expected: int,
        session_id: str,
        payload_hash: str,
    ) -> Checkpoint:
        """Handle link loss: stop transmission, save checkpoint, advance tracking epoch."""
        t_start = time.time()
        self._last_link_lost_timestamp = t_start

        # 1. Log LINK_LOST
        self.logger.log_event(
            "LINK_LOST",
            self.sender_id,
            self.receiver_id,
            {"transfer_id": self.transfer_id, "epoch": self.state_machine.tracking_epoch},
        )

        # 2. Update state machine
        old_epoch = self.state_machine.tracking_epoch
        self.state_machine.handle_link_loss(reason="OPTICAL_BEACON_LOST")
        new_epoch = self.state_machine.tracking_epoch

        # 3. Create & Save persistent checkpoint
        chk = Checkpoint(
            transfer_id=self.transfer_id,
            total_packets=total_packets,
            last_confirmed=last_confirmed,
            next_expected=next_expected,
            session_id=session_id,
            tracking_epoch=old_epoch,
            payload_hash=payload_hash,
            checkpoint_timestamp=round(t_start, 3),
        )

        t_save_start = time.time()
        self.checkpoint_manager.save_checkpoint(chk)
        t_save_end = time.time()
        self.metrics.checkpoint_save_time_ms = round((t_save_end - t_save_start) * 1000.0, 3)

        self.current_checkpoint = chk

        # 4. Log CHECKPOINT_SAVED & NEW_TRACKING_EPOCH
        self.logger.log_event(
            "CHECKPOINT_SAVED",
            self.sender_id,
            self.receiver_id,
            {"transfer_id": self.transfer_id, "last_confirmed": last_confirmed, "next_expected": next_expected},
        )
        self.logger.log_event(
            "NEW_TRACKING_EPOCH",
            self.sender_id,
            self.receiver_id,
            {"transfer_id": self.transfer_id, "old_epoch": old_epoch, "new_epoch": new_epoch},
        )

        return chk

    def handle_beacon_reacquisition(self, tracking_state: TrackingState) -> None:
        """Handle Member 2 beacon reacquisition.
        
        BEACON REACQUIRED != AUTOMATIC TRUST != AUTOMATIC RESUME
        """
        t_reacq = time.time()
        self._last_reacq_timestamp = t_reacq
        if self._last_link_lost_timestamp is not None:
            self.metrics.reacquisition_duration_sec = round(t_reacq - self._last_link_lost_timestamp, 4)

        self.logger.log_event(
            "REACQUISITION_STARTED",
            self.sender_id,
            self.receiver_id,
            {"transfer_id": self.transfer_id, "tracking_state": tracking_state.tracking_state},
        )

        self.state_machine.handle_reacquisition(tracking_state)

        self.logger.log_event(
            "BEACON_REACQUIRED",
            self.sender_id,
            self.receiver_id,
            {"transfer_id": self.transfer_id, "security_status": self.state_machine.security_status},
        )

    def execute_recovery(
        self,
        sender_creds: TerminalCredentials,
        receiver_creds: TerminalCredentials,
        registry: TerminalRegistry,
        tracking_state: TrackingState,
        total_packets: int,
        payload_hash: str,
        receiver_verified_checkpoint: int,
        session_manager: Optional[SessionManager] = None,
        trust_engine: Optional[TrustEngine] = None,
    ) -> ActiveSession:
        """Execute complete secure recovery workflow.
        
        Returns:
            New ActiveSession with fresh session keys.
            
        Raises:
            MaxRecoveryAttemptsExceededError: If retry limit exceeded.
            RecoveryError: If security verification fails at any stage.
        """
        self.metrics.total_attempts_count += 1
        self.recovery_attempts += 1

        if self.recovery_attempts > self.max_recovery_attempts:
            self.state_machine.handle_failure("MAX_RECOVERY_ATTEMPTS_EXCEEDED")
            self.logger.log_event(
                "RECOVERY_FAILED",
                self.sender_id,
                self.receiver_id,
                {
                    "transfer_id": self.transfer_id,
                    "reason": "MAX_RECOVERY_ATTEMPTS_EXCEEDED",
                    "attempts": self.recovery_attempts,
                },
            )
            raise MaxRecoveryAttemptsExceededError(
                f"Recovery failed: Exceeded maximum attempts ({self.max_recovery_attempts})"
            )

        try:
            # 1. Reacquisition state check
            if not tracking_state.is_locked:
                raise RecoveryError("Target optical beacon is not locked.")

            if self.state_machine.state != RecoveryState.REACQUIRING:
                self.handle_beacon_reacquisition(tracking_state)

            # 2. FRESH MUTUAL REAUTHENTICATION (Phase 2)
            t_auth_start = time.time()
            self.state_machine.transition_to_authenticating()
            self.logger.log_event(
                "REAUTHENTICATION_STARTED",
                self.sender_id,
                self.receiver_id,
                {"transfer_id": self.transfer_id, "epoch": self.state_machine.tracking_epoch},
            )

            auth_controller = AuthenticationController(registry=registry)
            auth_result = auth_controller.execute_mutual_authentication(
                t1_creds=sender_creds,
                t2_creds=receiver_creds,
                tracking_epoch=self.state_machine.tracking_epoch,
            )

            t_auth_end = time.time()
            self.metrics.reauthentication_latency_sec = round(t_auth_end - t_auth_start, 4)

            if not auth_result.authenticated:
                self.logger.log_event(
                    "REAUTHENTICATION_FAILURE",
                    self.sender_id,
                    self.receiver_id,
                    {"transfer_id": self.transfer_id, "reason": auth_result.reason},
                )
                self.state_machine.handle_failure(f"REAUTHENTICATION_FAILED: {auth_result.reason}")
                self.logger.log_event(
                    "RECOVERY_FAILED",
                    self.sender_id,
                    self.receiver_id,
                    {"transfer_id": self.transfer_id, "reason": "REAUTHENTICATION_FAILURE"},
                )
                raise RecoveryError(f"Fresh reauthentication failed: {auth_result.reason}")

            self.state_machine.handle_authentication_success()
            self.logger.log_event(
                "REAUTHENTICATION_SUCCESS",
                self.sender_id,
                self.receiver_id,
                {"transfer_id": self.transfer_id, "epoch": self.state_machine.tracking_epoch},
            )

            # 3. FRESH TRUST EVALUATION (Phase 3)
            engine = trust_engine or TrustEngine()
            probe_gen = ProbeGenerator()
            probe_challenge = probe_gen.generate_challenge(
                session_id="RECOVERY_PROBE",
                tracking_epoch=self.state_machine.tracking_epoch,
                tracking_state=tracking_state,
            )
            from ..optical_challenge import OpticalResponseSimulator
            resp_sim = OpticalResponseSimulator()
            responses = resp_sim.simulate_legitimate_response(probe_challenge, tracking_state)
            val = PhysicalConsistencyValidator()
            phys_result = val.validate(probe_challenge, responses, tracking_state)

            trust_res = engine.evaluate(
                terminal_id=self.sender_id,
                remote_terminal_id=self.receiver_id,
                tracking_state=tracking_state,
                authentication_valid=auth_result.authenticated,
                freshness_valid=True,
                physical_validation_result=phys_result,
                logger=self.logger,
            )

            auth_gate = TransmissionAuthorizationGate.can_transmit(
                trust_result=trust_res,
                logger=self.logger,
                terminal_id=self.sender_id,
                remote_terminal_id=self.receiver_id,
            )

            if not auth_gate.authorized:
                self.state_machine.handle_failure(f"TRUST_AUTHORIZATION_FAILED: {auth_gate.reason}")
                self.logger.log_event(
                    "RECOVERY_FAILED",
                    self.sender_id,
                    self.receiver_id,
                    {"transfer_id": self.transfer_id, "reason": "TRUST_NOT_AUTHORIZED"},
                )
                raise RecoveryError(f"Trust authorization failed during recovery: {auth_gate.reason}")

            # 4. NEW SECURE SESSION (Phase 4)
            t_sess_start = time.time()
            self.logger.log_event(
                "NEW_SESSION_STARTED",
                self.sender_id,
                self.receiver_id,
                {"transfer_id": self.transfer_id, "epoch": self.state_machine.tracking_epoch},
            )

            sm = session_manager or SessionManager()
            new_session = sm.establish_session(
                initiator_id=self.sender_id,
                responder_id=self.receiver_id,
                tracking_epoch=self.state_machine.tracking_epoch,
                authentication_valid=True,
                trust_authorized=True,
            )

            t_sess_end = time.time()
            self.metrics.session_establishment_latency_sec = round(t_sess_end - t_sess_start, 4)

            self.state_machine.handle_session_establishment(new_session.session_id)
            self.active_session = new_session

            # 5. RESUME REQUEST & RESPONSE NEGOTIATION (Phase 7)
            t_res_start = time.time()
            self.state_machine.transition_to_resuming()

            sender_last_confirmed = self.current_checkpoint.last_confirmed if self.current_checkpoint else 0

            # Sender builds ResumeRequest
            req = ResumeProtocolHandler.create_request(
                transfer_id=self.transfer_id,
                total_packets=total_packets,
                tracking_epoch=self.state_machine.tracking_epoch,
                session_id=new_session.session_id,
                sender_checkpoint=sender_last_confirmed,
                payload_hash=payload_hash,
            )

            # Encrypt request with sender->receiver key
            req_packet = ResumeProtocolHandler.encrypt_message(
                msg_bytes=req.to_bytes(),
                session_key=new_session.derived_keys.initiator_to_responder_key,
                protocol_version="1.0",
                session_id=new_session.session_id,
                transfer_id=self.transfer_id,
                sequence_number=1,
                direction="T1_TO_T2",
            )
            self.logger.log_event(
                "RESUME_REQUEST_SENT",
                self.sender_id,
                self.receiver_id,
                {"transfer_id": self.transfer_id, "sender_checkpoint": sender_last_confirmed},
            )

            # Receiver decrypts & processes ResumeRequest
            decrypted_req_bytes = ResumeProtocolHandler.decrypt_message(
                packet=req_packet,
                session_key=new_session.derived_keys.initiator_to_responder_key,
            )
            received_req = ResumeRequest.from_bytes(decrypted_req_bytes)

            resp = ResumeProtocolHandler.process_request(
                request=received_req,
                expected_transfer_id=self.transfer_id,
                expected_epoch=self.state_machine.tracking_epoch,
                expected_session_id=new_session.session_id,
                expected_payload_hash=payload_hash,
                receiver_verified_checkpoint=receiver_verified_checkpoint,
            )

            # Receiver encrypts response with receiver->sender key
            resp_packet = ResumeProtocolHandler.encrypt_message(
                msg_bytes=resp.to_bytes(),
                session_key=new_session.derived_keys.responder_to_initiator_key,
                protocol_version="1.0",
                session_id=new_session.session_id,
                transfer_id=self.transfer_id,
                sequence_number=1,
                direction="T2_TO_T1",
            )
            self.logger.log_event(
                "RESUME_RESPONSE_RECEIVED",
                self.sender_id,
                self.receiver_id,
                {
                    "transfer_id": self.transfer_id,
                    "receiver_checkpoint": receiver_verified_checkpoint,
                    "status": resp.status,
                },
            )

            # Sender decrypts and validates response
            decrypted_resp_bytes = ResumeProtocolHandler.decrypt_message(
                packet=resp_packet,
                session_key=new_session.derived_keys.responder_to_initiator_key,
            )
            received_resp = ResumeResponse.from_bytes(decrypted_resp_bytes)

            is_valid, reason = ResumeProtocolHandler.validate_response(
                response=received_resp,
                expected_transfer_id=self.transfer_id,
                expected_epoch=self.state_machine.tracking_epoch,
                expected_session_id=new_session.session_id,
                sender_checkpoint=sender_last_confirmed,
                total_packets=total_packets,
            )

            t_res_end = time.time()
            self.metrics.resume_negotiation_latency_sec = round(t_res_end - t_res_start, 4)

            if not is_valid:
                self.logger.log_event(
                    "RESUME_REJECTED",
                    self.sender_id,
                    self.receiver_id,
                    {"transfer_id": self.transfer_id, "reason": reason},
                )
                self.state_machine.handle_failure(f"RESUME_REJECTED: {reason}")
                self.logger.log_event(
                    "RECOVERY_FAILED",
                    self.sender_id,
                    self.receiver_id,
                    {"transfer_id": self.transfer_id, "reason": "RESUME_REJECTED"},
                )
                raise ResumeValidationError(f"Resume validation failed: {reason}")

            self.logger.log_event(
                "RESUME_VALIDATED",
                self.sender_id,
                self.receiver_id,
                {
                    "transfer_id": self.transfer_id,
                    "receiver_verified_checkpoint": receiver_verified_checkpoint,
                },
            )

            # 6. RESUME TRANSMISSION ALLOWED
            self.state_machine.handle_resume_validated()
            self.metrics.success_count += 1

            resuming_from = receiver_verified_checkpoint + 1
            self.logger.log_event(
                "TRANSFER_RESUMED",
                self.sender_id,
                self.receiver_id,
                {
                    "transfer_id": self.transfer_id,
                    "resuming_from_packet": resuming_from,
                    "epoch": self.state_machine.tracking_epoch,
                },
            )

            return new_session

        except Exception as e:
            if not isinstance(e, (RecoveryError, ResumeValidationError, MaxRecoveryAttemptsExceededError)):
                self.state_machine.handle_failure(str(e))
                self.logger.log_event(
                    "RECOVERY_FAILED",
                    self.sender_id,
                    self.receiver_id,
                    {"transfer_id": self.transfer_id, "reason": str(e)},
                )
            raise
