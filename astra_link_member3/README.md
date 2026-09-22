# Astra Link Member 3 — Security + Communication Layer

This repository contains **Phase 1: Terminal Identity**, **Phase 2: Mutual Authentication**, **Phase 3: Trust + Transmission Authorization**, **Phase 4: Secure Session Establishment**, **Phase 5: Secure Data Transmission**, **Phase 6: ACK + Selective Repeat ARQ**, **Phase 7: Link Recovery + Secure Resume**, and **Phase 8: Attack Simulation + Security Metrics + Final Verification** for Astra Link.

---

## Cryptographic & Reliable Transport Architecture

Astra Link enforces a complete secure and reliable data transport pipeline:

```text
Mutual Authentication (Phase 2)
      ↓
Trust Evaluation & Transmission Authorization Gate (Phase 3)
      ↓
Ephemeral X25519 Exchange & HKDF Key Derivation (Phase 4)
      ↓
Directional Key Separation (T1 -> T2 and T2 -> T1) (Phase 4)
      ↓
Application Payload & Packetization (Phase 5)
      ↓
AES-GCM Authenticated Encryption with AAD Metadata Binding (Phase 5)
      ↓
Sliding Window Flow Control (Phase 6)
      ↓
Link Interruption -> Immediate Transmission Stop (Phase 7)
      ↓
Atomic Transfer Checkpoint Persistence (Phase 7)
      ↓
Beacon Reacquisition -> Security State: LOCKED_UNVERIFIED (Phase 7)
      ↓
Fresh Phase 2 Mutual Authentication & New Tracking Epoch (Phase 7)
      ↓
New X25519 ECDH Exchange & New Secure Session Keys (Phase 7)
      ↓
Authenticated Resume Protocol Negotiation (Phase 7)
      ↓
Active Attack Simulation & Verification (Phase 8)
      ↓
Selective Retransmission from Last Confirmed Checkpoint (Phase 6 & 7)
      ↓
Contiguous Reassembly & Complete Payload Recovery (Phase 6 & 7)
```

---

## Phase 8: Attack Simulation + Security Metrics + Final Verification

### Objective
Phase 8 intentionally attacks the Astra Link Member 3 system under a documented threat model to evaluate and measure system resilience, security invariant enforcement, recovery performance, and application goodput.

### Threat Model
The simulated attacker:
- Can observe public protocol exchanges and encrypted packet payloads.
- Can clone visual beacon characteristics (`tracking_state = LOCKED`).
- Can replay previously captured authentication messages.
- Can tamper with transmitted ciphertext, nonces, sequence numbers, session IDs, transfer IDs, and direction tags.
- Can inject forged control messages (ACKs and Resume Responses).
- Can inject duplicate packets or reuse packets across sessions/directions.
- Can introduce physical motion anomalies and optical jamming/degradation.

The attacker does **NOT** possess:
- Legitimate Ed25519 identity private keys.
- Legitimate X25519 agreement private keys.
- Derived AES-GCM session keys.

> [!CAUTION]
> **Limitations Statement**: Measured security results and rejection rates apply strictly to the implemented simulated attack model, protocol invariants, and controlled test conditions.

---

### Executed Attack Simulations (`src/attacks/`)

1. **Cloned Beacon Attack (`src/attacks/cloned_beacon.py`)**: Clones visual beacon (`LOCKED` status) without legitimate Ed25519 credentials $\to$ Mutual authentication fails $\to$ `UNTRUSTED` $\to$ Transmission BLOCKED.
2. **Replay Attack (`src/attacks/replay.py`)**: Replays valid authentication response across same/new epoch, same/new session, opposite direction $\to$ Detected by 5-field `ReplayProtectionCache` $\to$ REJECTED.
3. **Packet Tampering Attack (`src/attacks/packet_tampering.py`)**: Flips bits in ciphertext, nonce, session_id, transfer_id, sequence_number, or direction $\to$ AES-GCM tag/AAD check fails $\to$ PACKET REJECTED $\to$ Not acknowledged.
4. **Forged ACK Attack (`src/attacks/forged_ack.py`)**: Injects forged ACKs (unknown terminal, wrong session/transfer, impossible sequence numbers, premature completion claim) $\to$ ACK REJECTED $\to$ Sender window base sequence unchanged.
5. **Forged Resume Checkpoint Attack (`src/attacks/forged_resume.py`)**: Injects fake resume response (`last_confirmed = 10000`, `-1`, `> total_packets`, wrong transfer/session/epoch) $\to$ `ResumeValidationError` $\to$ Transfer state unchanged.
6. **Delayed Auth Response Attack**: Delays valid auth response beyond freshness window $\to$ `ExpiredTimestampError` $\to$ Authentication REJECTED.
7. **Invalid Credential Attack (`src/attacks/invalid_credentials.py`)**: Attacker with valid keys not present in `TerminalRegistry` $\to$ Unknown terminal $\to$ REJECTED.
8. **Inconsistent Motion Anomaly Attack (`src/attacks/jamming.py`)**: Valid auth + locked tracking, but low motion consistency (0.35) or physical response error $\to$ `TRUST = DEGRADED` $\to$ Transmission BLOCKED.
9. **Optical Jamming / Degradation (`src/attacks/jamming.py`)**: Reduced signal quality / beacon dropout $\to$ Tracking state `LOST` $\to$ Transmission suspended $\to$ Graceful recovery required.
10. **Duplicate Packet Injection**: Re-transmits valid packet $\to$ Receiver detects duplicate sequence $\to$ Discarded without double application payload delivery.
11. **Cross-Session Packet Reuse**: Transmits Session A packet under Session B $\to$ Decryption fails $\to$ REJECTED.
12. **Cross-Direction Packet Reuse**: Transmits T1 $\to$ T2 packet under T2 $\to$ T1 context $\to$ Decryption fails $\to$ REJECTED.

---

### Programmatic Security Policy Invariants

Phase 8 programmatically verifies 14 core security policy invariants:
1. Tracking lock alone cannot authorize transmission.
2. Authentication failure cannot authorize transmission.
3. Invalid freshness cannot authorize transmission.
4. Invalid physical consistency cannot authorize transmission.
5. Missing secure session cannot authorize transmission.
6. Invalid packet integrity cannot produce application data.
7. Forged ACK cannot advance sender state.
8. Forged resume information cannot alter transfer checkpoint.
9. Reacquisition cannot automatically restore trust.
10. New tracking epoch requires fresh authentication.
11. New session requires fresh session keys.
12. Transfer state survives legitimate session replacement.
13. Duplicate packets cannot duplicate application payload.
14. Recovery failure leaves transmission blocked.

---

### Machine-Readable Security & Transport Reports

Reports are automatically generated under `outputs/reports/`:
- `outputs/reports/phase8_security_report.json`: Contains quantitative event metrics, attack counts, and rates with explicit numerators and denominators.
- `outputs/reports/phase8_transport_report.json`: Contains transport packet throughput, retransmissions, recovery latencies, and goodput ($\text{goodput\_kbps}$).

> [!IMPORTANT]
> Reports contain **ZERO secret cryptographic material** (no private keys, session keys, or raw secrets).

---

## Directory Structure

```text
astra_link_member3/
├── config/
│   ├── recovery_config.json   # Phase 7 recovery configuration
│   ├── session_config.json    # Phase 4 session configuration
│   ├── terminals.json         # Phase 1 trusted terminal registry
│   ├── transport_config.json  # Phase 5 & 6 transport configuration
│   └── trust_config.json      # Phase 3 trust configuration
├── outputs/
│   ├── checkpoints/           # Persistent transfer checkpoints
│   └── reports/               # Machine-readable JSON security reports
├── src/
│   ├── attacks/               # Phase 8 Attack Simulators (Attacks 1-12)
│   │   ├── __init__.py
│   │   ├── cloned_beacon.py   # FakeBeaconAttack
│   │   ├── forged_ack.py      # ForgedAckAttack
│   │   ├── forged_resume.py   # ForgedResumeAttack
│   │   ├── invalid_credentials.py # InvalidCredentialAttack
│   │   ├── jamming.py         # OpticalJammingAttack
│   │   ├── packet_tampering.py# PacketTamperingAttack
│   │   └── replay.py          # ReplayAttack
│   ├── authentication/        # Phase 2 challenge-response mutual auth
│   ├── identity/              # Phase 1 Ed25519 & X25519 credentials
│   ├── metrics/               # Phase 8 Security Metrics & Reports
│   │   ├── __init__.py
│   │   └── security_metrics.py# SecurityMetricsTracker & ExperimentRunner
│   ├── optical_challenge/     # Phase 3 optical probe challenge
│   ├── recovery/              # Phase 7 Link Recovery & Secure Resume
│   ├── session/               # Phase 4 session manager & HKDF
│   ├── tracking/              # TrackingState data model
│   ├── transport/             # Phase 5 & 6 ARQ & PacketCipher
│   └── trust/                 # Phase 3 TrustEngine & authorization gate
├── tests/
│   ├── test_arq.py            # Phase 6 tests (30 tests)
│   ├── test_attacks.py        # Phase 8 attack & invariant tests (27 tests)
│   ├── test_authentication.py # Phase 2 tests (26 tests)
│   ├── test_end_to_end.py     # End-to-End integration tests (2 tests)
│   ├── test_identity.py       # Phase 1 tests (14 tests)
│   ├── test_recovery.py       # Phase 7 tests (32 tests)
│   ├── test_session.py        # Phase 4 tests (23 tests)
│   ├── test_transport.py      # Phase 5 tests (32 tests)
│   └── test_trust.py          # Phase 3 tests (17 tests)
├── demo_phase2.py             # Phase 2 Demonstration
├── demo_phase3.py             # Phase 3 Demonstration
├── demo_phase4.py             # Phase 4 Demonstration
├── demo_phase5.py             # Phase 5 Demonstration
├── demo_phase6.py             # Phase 6 Demonstration
├── demo_phase7.py             # Phase 7 Demonstration
├── demo_phase8.py             # Phase 8 Final Security Validation Demonstration
├── .gitignore                 # Git ignore rules
├── requirements.txt           # Dependencies
└── README.md
```

---

## Running Demonstrations & Tests

### 1. Key Generation
```bash
python tools/generate_keys.py
```

### 2. Phase 8 Final Security Demonstration
```bash
python demo_phase8.py
```

Runs all 7 scenarios, prints presentation-ready security validation output, and saves JSON report files under `outputs/reports/`.

### 3. Automated Test Suite
```bash
python -m pytest tests/
```

Runs all **203 unit and integration tests** across Phase 1 through Phase 8.
   - `SenderWindow`: Tracks `base_sequence`, `next_sequence`, `in_flight` packets, timestamps, and retry counts. Enforces `window_size` (default: 32).
   - `get_timed_out_packets`: Identifies packets exceeding `ack_timeout_ms` (default: 100ms) for selective retransmission. Raises `MaxRetriesExceededError` if `max_retries` (default: 5) is exceeded.
   - `ReceiverWindow`: Manages `cumulative_ack`, buffers out-of-order valid packets in `received_out_of_order`, tracks `received_sequences`, and outputs contiguous deliverable payload chunks.

3. **Transport Metrics (`src/transport/metrics.py`)**
   - `TransportMetrics`: Records empirical statistics (`packets_sent`, `packets_received`, `packets_lost`, `packets_retransmitted`, `duplicate_packets`, `ack_count`, `transfer_duration`, `goodput_bps`).

4. **Sender & Receiver ARQ Flow Control (`src/transport/sender.py`, `src/transport/receiver.py`)**
   - `SecureSender`: Enforces sliding window capacity, selective retransmission, and session/authorization preconditions.
   - `SecureReceiver`: Verifies AES-GCM integrity, generates authenticated `AckMessage` control packets, buffers out-of-order packets, and delivers contiguous payload.

---

## Project Structure

```text
astra_link_member3/
├── config/
│   ├── terminals.json         # Terminal identity registry
│   ├── trust_config.json      # Phase 3 trust parameters
│   ├── session_config.json    # Phase 4 session parameters
│   └── transport_config.json  # Phase 5 & 6 transport & ARQ parameters
├── src/
│   ├── identity/              # Phase 1: Terminal Identity
│   ├── authentication/        # Phase 2: Mutual Authentication
│   ├── tracking/              # Phase 3: Member 2 Tracking Interface
│   ├── optical_challenge/     # Phase 3: Optical Challenge & Physical Validation
│   ├── trust/                 # Phase 3: Trust Engine & Transmission Gate
│   ├── session/               # Phase 4: Secure Session Establishment
│   └── transport/             # Phase 5 & 6: Transport & Selective Repeat ARQ
│       ├── ack.py             # AckMessage & SACK control model
│       ├── selective_repeat.py# SenderWindow, ReceiverWindow, ARQ logic
│       ├── metrics.py         # TransportMetrics
│       ├── packet.py          # EncryptedPacket dataclass
│       ├── cipher.py          # PacketCipher (AES-GCM)
│       ├── packetizer.py      # Packetizer & PayloadReassembler
│       ├── sender.py          # SecureSender
│       └── receiver.py        # SecureReceiver
├── tools/
│   └── generate_keys.py       # Key generation CLI tool
├── tests/
│   ├── test_identity.py       # Phase 1 tests (14 tests)
│   ├── test_authentication.py # Phase 2 tests (26 tests)
│   ├── test_trust.py          # Phase 3 tests (17 tests)
│   ├── test_session.py        # Phase 4 tests (23 tests)
│   ├── test_transport.py      # Phase 5 tests (32 tests)
│   └── test_arq.py            # Phase 6 tests (30 tests)
├── keys/                      # Local PEM key storage (IGNORED BY GIT)
├── demo.py                    # Phase 1 Demonstration
├── demo_phase2.py             # Phase 2 Demonstration
├── demo_phase3.py             # Phase 3 Demonstration
├── demo_phase4.py             # Phase 4 Demonstration
├── demo_phase5.py             # Phase 5 Demonstration
├── demo_phase6.py             # Phase 6 Demonstration
├── .gitignore                 # Git ignore rules
├── requirements.txt           # Dependencies
└── README.md
```

---

## Running Demonstrations & Tests

### 1. Key Generation
```bash
python tools/generate_keys.py
```

### 2. Phase 6 Reliable Transport Demo
```bash
python demo_phase6.py
```

Demonstrates 5 scenarios:
- **Scenario 1 (Normal Transfer)**: 10 packets transmitted, ACKs received, completed.
- **Scenario 2 (Single Packet Loss)**: Packet 3 lost -> Cumulative ACK=2, SACK=4,5... -> Retransmit Packet 3 ONLY -> Completed.
- **Scenario 3 (Burst Loss)**: Packets 3 & 7 lost -> SACK identifies 3 & 7 missing -> Retransmit 3 & 7 ONLY -> Completed.
- **Scenario 4 (ACK Loss)**: Packet 5 ACK lost -> Sender timeout -> Retransmit 5 -> Receiver detects duplicate -> Resends ACK without double payload delivery.
- **Scenario 5 (Tampered Packet)**: Corrupt packet -> GCM verification failure -> Rejected -> Not acknowledged -> Retransmitted.

### 3. Automated Test Suite
```bash
python -m pytest tests/
```

Runs all 142 unit tests across Phase 1 through Phase 6.
