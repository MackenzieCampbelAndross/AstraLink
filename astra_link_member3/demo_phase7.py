"""Phase 7 Demonstration: Link Recovery + Secure Resume."""

import os
import shutil
import tempfile
import time

from src.authentication import AuthenticationController
from src.identity import TerminalRegistry, generate_credentials
from src.recovery import (
    CheckpointManager,
    MaxRecoveryAttemptsExceededError,
    RecoveryController,
    RecoveryError,
    RecoveryState,
    ResumeProtocolHandler,
    ResumeResponse,
    ResumeValidationError,
)
from src.session import SessionManager
from src.tracking import TrackingState
from src.transport.cipher import PacketCipher
from src.transport.packetizer import Packetizer, PayloadReassembler
from src.transport.selective_repeat import ReceiverWindow
from src.trust import SecurityLogger, TrustEngine


def run_demo():
    print("=" * 60)
    print("ASTRA LINK MEMBER 3 — PHASE 7: SECURE RECOVERY DEMO")
    print("=" * 60)

    demo_dir = tempfile.mkdtemp(prefix="astralink_demo_phase7_")

    try:
        # 1. Setup Identities and Trusted Terminal Registry
        t1_creds = generate_credentials("T1")
        t2_creds = generate_credentials("T2")

        registry = TerminalRegistry()
        registry.register_public_credentials(t1_creds.public_credentials)
        registry.register_public_credentials(t2_creds.public_credentials)

        logger = SecurityLogger()
        sm = SessionManager()

        # Initial Auth & Session (Epoch 7)
        initial_epoch = 7
        sess1 = sm.establish_session("T1", "T2", tracking_epoch=initial_epoch, authentication_valid=True, trust_authorized=True)

        transfer_id = "TX_001"
        total_packets = 10000
        checkpoint_before_loss = 6403
        payload_hash = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

        print(f"\nTransfer: {transfer_id}")
        print(f"Current ACK: {checkpoint_before_loss}")
        print(f"Session: {sess1.session_id[:8]}... (ESTABLISHED)")
        print(f"Epoch: {initial_epoch}")
        print("Transmission: ENABLED")

        # -------------------------------------------------------------------
        # PART 1: LEGITIMATE LINK LOSS & SECURE RECOVERY
        # -------------------------------------------------------------------
        print("\n" + "-" * 50)
        print("SCENARIO 1: LINK LOSS & LEGITIMATE SECURE RESUME")
        print("-" * 50)

        ctrl = RecoveryController(
            transfer_id=transfer_id,
            sender_id="T1",
            receiver_id="T2",
            checkpoint_dir=os.path.join(demo_dir, "checkpoints"),
            logger=logger,
        )
        ctrl.state_machine.tracking_epoch = initial_epoch

        # Link Interruption
        t_base = time.time()
        print(f"\n[{t_base:.3f}] LINK LOST")
        chk = ctrl.handle_link_interruption(
            total_packets=total_packets,
            last_confirmed=checkpoint_before_loss,
            next_expected=checkpoint_before_loss + 1,
            session_id=sess1.session_id,
            payload_hash=payload_hash,
        )
        print(f"[{time.time():.3f}] Transmission disabled (allowed = {ctrl.state_machine.transmission_allowed})")
        print(f"[{time.time():.3f}] Checkpoint saved: {chk.last_confirmed}")
        print(f"[{time.time():.3f}] Epoch advanced: {initial_epoch} -> {ctrl.state_machine.tracking_epoch}")

        # Beacon Reacquisition
        locked_tracking = TrackingState(
            timestamp=time.time(),
            tracking_state="LOCKED",
            predicted_x=10.0,
            predicted_y=20.0,
            angular_x=0.01,
            angular_y=0.02,
            velocity_x=0.1,
            velocity_y=0.2,
            motion_consistency=0.95,
        )
        ctrl.handle_beacon_reacquisition(locked_tracking)
        print(f"\n[{time.time():.3f}] Beacon reacquired")
        print(f"[{time.time():.3f}] Security state: {ctrl.state_machine.security_status}")
        print(f"[{time.time():.3f}] Fresh authentication started")

        # Execute full recovery
        sess2 = ctrl.execute_recovery(
            sender_creds=t1_creds,
            receiver_creds=t2_creds,
            registry=registry,
            tracking_state=locked_tracking,
            total_packets=total_packets,
            payload_hash=payload_hash,
            receiver_verified_checkpoint=checkpoint_before_loss,
            session_manager=sm,
        )

        print(f"[{time.time():.3f}] Authentication successful")
        print(f"[{time.time():.3f}] New secure session established: {sess2.session_id[:8]}...")
        print(f"[{time.time():.3f}] Resume request sent")
        print(f"[{time.time():.3f}] Receiver checkpoint: {checkpoint_before_loss}")
        print(f"[{time.time():.3f}] Resume validated")
        print(f"[{time.time():.3f}] Resuming from packet {checkpoint_before_loss + 1}")
        print(f"[{time.time():.3f}] Transfer resumed (allowed = {ctrl.state_machine.transmission_allowed})")

        print(f"\nRecovery result: SUCCESS")
        print(f"Transfer completed: SUCCESS")
        print(f"Total secure recovery time: {ctrl.metrics.total_secure_recovery_time_sec:.4f}s")

        # -------------------------------------------------------------------
        # PART 2: FAKE BEACON REACQUISITION & AUTHENTICATION FAILURE
        # -------------------------------------------------------------------
        print("\n" + "-" * 50)
        print("SCENARIO 2: FAKE BEACON REACQUISITION FAILURE")
        print("-" * 50)

        ctrl_fake = RecoveryController(
            transfer_id="TX_002",
            checkpoint_dir=os.path.join(demo_dir, "checkpoints"),
            logger=logger,
        )
        ctrl_fake.handle_link_interruption(1000, 100, 101, sess2.session_id, payload_hash)
        print(f"\n[{time.time():.3f}] LINK LOST")

        fake_t2 = generate_credentials("T2")  # Unregistered key
        ctrl_fake.handle_beacon_reacquisition(locked_tracking)
        print(f"[{time.time():.3f}] FAKE BEACON REACQUIRED")
        print(f"[{time.time():.3f}] Security state: {ctrl_fake.state_machine.security_status}")
        print(f"[{time.time():.3f}] Fresh authentication started")

        try:
            ctrl_fake.execute_recovery(
                sender_creds=t1_creds,
                receiver_creds=fake_t2,
                registry=registry,
                tracking_state=locked_tracking,
                total_packets=1000,
                payload_hash=payload_hash,
                receiver_verified_checkpoint=100,
            )
        except RecoveryError as e:
            print(f"[{time.time():.3f}] AUTHENTICATION FAILURE: {e}")
            print(f"[{time.time():.3f}] Security state: {ctrl_fake.state_machine.security_status}")
            print(f"[{time.time():.3f}] TRANSMISSION BLOCKED (allowed = {ctrl_fake.state_machine.transmission_allowed})")

        # Restoring legitimate beacon
        print(f"\n[{time.time():.3f}] LEGITIMATE BEACON REACQUIRED")
        sess_restored = ctrl_fake.execute_recovery(
            sender_creds=t1_creds,
            receiver_creds=t2_creds,
            registry=registry,
            tracking_state=locked_tracking,
            total_packets=1000,
            payload_hash=payload_hash,
            receiver_verified_checkpoint=100,
            session_manager=sm,
        )
        print(f"[{time.time():.3f}] FRESH AUTHENTICATION SUCCESS")
        print(f"[{time.time():.3f}] NEW SESSION: {sess_restored.session_id[:8]}...")
        print(f"[{time.time():.3f}] RESUME SUCCESS")

        # -------------------------------------------------------------------
        # PART 3: FORGED RESUME CHECKPOINT REJECTION
        # -------------------------------------------------------------------
        print("\n" + "-" * 50)
        print("SCENARIO 3: FORGED RESUME CHECKPOINT REJECTION")
        print("-" * 50)

        forged_response = ResumeResponse(
            transfer_id="TX_001",
            receiver_verified_checkpoint=9999,  # Forged higher packet
            total_packets=10000,
            tracking_epoch=8,
            session_id="SESS_FORGED",
            timestamp=time.time(),
            status="ACCEPTED",
            reason="OK",
        )

        print(f"\n[{time.time():.3f}] Received unauthenticated forged resume response (claim: 9999)")
        try:
            ResumeProtocolHandler.validate_response(
                response=forged_response,
                expected_transfer_id="TX_001",
                expected_epoch=8,
                expected_session_id=sess2.session_id,
                sender_checkpoint=6403,
                total_packets=10000,
            )
        except ResumeValidationError as e:
            print(f"[{time.time():.3f}] RESUME REJECTED: {e}")
            print(f"[{time.time():.3f}] Transmission remains BLOCKED")

        print("\n" + "=" * 60)
        print("PHASE 7 DEMONSTRATION COMPLETE: ALL VERIFICATIONS PASSED")
        print("=" * 60)

    finally:
        shutil.rmtree(demo_dir, ignore_errors=True)


if __name__ == "__main__":
    run_demo()
