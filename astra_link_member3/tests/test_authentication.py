"""Unit tests for Phase 2: Mutual Authentication and Replay Protection."""

import time
import pytest
from pathlib import Path

from src.identity import (
    TerminalCredentials,
    TerminalIdentity,
    TerminalNotFoundError,
    TerminalRegistry,
    generate_credentials,
)
from src.authentication import (
    AuthState,
    AuthenticationChallenge,
    AuthenticationResponse,
    AuthenticationSession,
    ExpiredTimestampError,
    FreshnessValidator,
    FutureTimestampError,
    InvalidSignatureError,
    InvalidTranscriptError,
    ReplayAttackError,
    ReplayKey,
    ReplayProtectionCache,
    authenticate_mutually,
    create_challenge,
    create_response,
    verify_response,
)


@pytest.fixture
def t1_identity() -> TerminalIdentity:
    return TerminalIdentity.create_new("T1")


@pytest.fixture
def t2_identity() -> TerminalIdentity:
    return TerminalIdentity.create_new("T2")


@pytest.fixture
def registry(t1_identity: TerminalIdentity, t2_identity: TerminalIdentity) -> TerminalRegistry:
    reg = TerminalRegistry()
    reg.register_public_credentials(t1_identity.public_credentials)
    reg.register_public_credentials(t2_identity.public_credentials)
    return reg


# 1. Valid T1 challenge
def test_valid_t1_challenge():
    challenge = create_challenge("T1", "T2", tracking_epoch=1)
    assert challenge.initiator_id == "T1"
    assert challenge.responder_id == "T2"
    assert len(challenge.nonce) == 32
    assert len(challenge.session_id) == 32
    assert challenge.tracking_epoch == 1
    assert challenge.protocol_version == "1.0"


# 2. Valid T2 response
def test_valid_t2_response(t2_identity: TerminalIdentity):
    challenge = create_challenge("T1", "T2", tracking_epoch=1)
    response = create_response(challenge, t2_identity)
    assert response.responder_id == "T2"
    assert response.session_id == challenge.session_id
    assert len(response.signature_hex) == 128


# 3. Valid signature verification
def test_valid_signature_verification(t2_identity: TerminalIdentity, registry: TerminalRegistry):
    challenge = create_challenge("T1", "T2", tracking_epoch=1)
    response = create_response(challenge, t2_identity)
    verified = verify_response(challenge, response, registry)
    assert verified is True


# 4. Invalid signature
def test_invalid_signature_rejection(t2_identity: TerminalIdentity, registry: TerminalRegistry):
    challenge = create_challenge("T1", "T2", tracking_epoch=1)
    response = create_response(challenge, t2_identity)
    
    corrupt_sig = "00" * 64
    tampered_response = AuthenticationResponse(
        session_id=response.session_id,
        responder_id=response.responder_id,
        signature_hex=corrupt_sig,
    )

    with pytest.raises(InvalidSignatureError):
        verify_response(challenge, tampered_response, registry)


# 5. Wrong terminal identity
def test_wrong_terminal_identity(t1_identity: TerminalIdentity, t2_identity: TerminalIdentity, registry: TerminalRegistry):
    challenge = create_challenge("T1", "T2", tracking_epoch=1)
    with pytest.raises(InvalidTranscriptError) as exc:
        create_response(challenge, t1_identity)
    assert "Responder identity mismatch" in str(exc.value)


# 6. Unknown terminal
def test_unknown_terminal_rejection(t2_identity: TerminalIdentity):
    empty_registry = TerminalRegistry()
    challenge = create_challenge("T1", "T2", tracking_epoch=1)
    response = create_response(challenge, t2_identity)

    with pytest.raises(TerminalNotFoundError):
        verify_response(challenge, response, empty_registry)


# 7. Modified transcript
def test_modified_transcript_detection(t2_identity: TerminalIdentity, registry: TerminalRegistry):
    challenge = create_challenge("T1", "T2", tracking_epoch=1)
    response = create_response(challenge, t2_identity)

    modified_challenge = AuthenticationChallenge(
        initiator_id=challenge.initiator_id,
        responder_id=challenge.responder_id,
        nonce=challenge.nonce,
        session_id=challenge.session_id,
        tracking_epoch=challenge.tracking_epoch,
        timestamp=challenge.timestamp,
        protocol_version="2.0",
    )

    with pytest.raises(InvalidSignatureError):
        verify_response(modified_challenge, response, registry)


# 8. Modified nonce
def test_modified_nonce_rejection(t2_identity: TerminalIdentity, registry: TerminalRegistry):
    challenge = create_challenge("T1", "T2", tracking_epoch=1)
    response = create_response(challenge, t2_identity)

    modified_challenge = AuthenticationChallenge(
        initiator_id=challenge.initiator_id,
        responder_id=challenge.responder_id,
        nonce="ffff" * 8,
        session_id=challenge.session_id,
        tracking_epoch=challenge.tracking_epoch,
        timestamp=challenge.timestamp,
        protocol_version=challenge.protocol_version,
    )

    with pytest.raises(InvalidSignatureError):
        verify_response(modified_challenge, response, registry)


# 9. Modified session ID
def test_modified_session_id_rejection(t2_identity: TerminalIdentity, registry: TerminalRegistry):
    challenge = create_challenge("T1", "T2", tracking_epoch=1)
    response = create_response(challenge, t2_identity)

    tampered_response = AuthenticationResponse(
        session_id="a" * 32,
        responder_id=response.responder_id,
        signature_hex=response.signature_hex,
    )

    with pytest.raises(InvalidTranscriptError) as exc:
        verify_response(challenge, tampered_response, registry)
    assert "Session ID mismatch" in str(exc.value)


# 10. Modified tracking epoch
def test_modified_tracking_epoch_rejection(t2_identity: TerminalIdentity, registry: TerminalRegistry):
    challenge_epoch7 = create_challenge("T1", "T2", tracking_epoch=7)
    response = create_response(challenge_epoch7, t2_identity)

    with pytest.raises(InvalidTranscriptError) as exc:
        verify_response(challenge_epoch7, response, registry, expected_epoch=8)
    assert "Tracking epoch mismatch" in str(exc.value)


# 11. Expired timestamp
def test_expired_timestamp_rejection(t2_identity: TerminalIdentity, registry: TerminalRegistry):
    old_time = time.time() - 100.0
    challenge = AuthenticationChallenge(
        initiator_id="T1",
        responder_id="T2",
        nonce="11" * 16,
        session_id="22" * 16,
        tracking_epoch=1,
        timestamp=old_time,
    )
    response = create_response(challenge, t2_identity)
    validator = FreshnessValidator(window_seconds=30.0)

    with pytest.raises(ExpiredTimestampError):
        verify_response(challenge, response, registry, freshness_validator=validator)


# 12. Future timestamp outside tolerance
def test_future_timestamp_outside_tolerance(t2_identity: TerminalIdentity, registry: TerminalRegistry):
    future_time = time.time() + 100.0
    challenge = AuthenticationChallenge(
        initiator_id="T1",
        responder_id="T2",
        nonce="11" * 16,
        session_id="22" * 16,
        tracking_epoch=1,
        timestamp=future_time,
    )
    response = create_response(challenge, t2_identity)
    validator = FreshnessValidator(window_seconds=30.0)

    with pytest.raises(FutureTimestampError):
        verify_response(challenge, response, registry, freshness_validator=validator)


# 13. Fresh nonce accepted
def test_fresh_nonce_accepted(t2_identity: TerminalIdentity, registry: TerminalRegistry):
    cache = ReplayProtectionCache()
    c1 = create_challenge("T1", "T2")
    r1 = create_response(c1, t2_identity)
    assert verify_response(c1, r1, registry, replay_cache=cache) is True

    c2 = create_challenge("T1", "T2")
    r2 = create_response(c2, t2_identity)
    assert verify_response(c2, r2, registry, replay_cache=cache) is True


# 14. Reused nonce rejected
def test_reused_nonce_rejected(t2_identity: TerminalIdentity, registry: TerminalRegistry):
    cache = ReplayProtectionCache()
    challenge = create_challenge("T1", "T2")
    response = create_response(challenge, t2_identity)

    assert verify_response(challenge, response, registry, replay_cache=cache) is True

    with pytest.raises(ReplayAttackError):
        verify_response(challenge, response, registry, replay_cache=cache)


# 15. Mutual authentication succeeds
def test_mutual_authentication_succeeds(t1_identity: TerminalIdentity, t2_identity: TerminalIdentity, registry: TerminalRegistry):
    result = authenticate_mutually(t1_identity, t2_identity, registry, tracking_epoch=1)
    assert result["local_authenticated"] is True
    assert result["remote_authenticated"] is True
    assert result["mutual_authentication_success"] is True


# 16. One sided authentication failure
def test_one_sided_authentication_failure(t1_identity: TerminalIdentity, registry: TerminalRegistry):
    fake_t2 = TerminalIdentity.create_new("T2")
    with pytest.raises(InvalidSignatureError):
        authenticate_mutually(t1_identity, fake_t2, registry)


# 17. Authentication state transitions
def test_authentication_state_transitions():
    sess = AuthenticationSession("T1")
    assert sess.state == AuthState.UNAUTHENTICATED

    sess.mark_authenticating("session_123")
    assert sess.state == AuthState.AUTHENTICATING

    sess.mark_remote_authenticated("T2")
    assert sess.state == AuthState.AUTHENTICATING

    sess.mark_local_authenticated()
    assert sess.state == AuthState.AUTHENTICATED
    assert sess.mutual_authentication_success is True

    sess.mark_failed()
    assert sess.state == AuthState.FAILED
    assert sess.mutual_authentication_success is False


# 18. Security check: private key material is never exposed
def test_private_key_protection_in_auth_objects(t2_identity: TerminalIdentity):
    challenge = create_challenge("T1", "T2")
    response = create_response(challenge, t2_identity)

    ch_str = str(challenge)
    res_str = str(response)

    assert "PrivateKey" not in ch_str
    assert "PrivateKey" not in res_str


# =====================================================================
# ENHANCED REPLAY PROTECTION TESTS (SPECIFICALLY FOR REPLAY CACHE FIX)
# =====================================================================

# 19. Same complete authentication context -> replay rejected
def test_replay_same_complete_context_rejected():
    cache = ReplayProtectionCache()
    c = AuthenticationChallenge(
        initiator_id="T1", responder_id="T2", nonce="N1", session_id="S1", tracking_epoch=7, timestamp=time.time()
    )
    cache.check_and_register(c)
    assert cache.is_replayed(c) is True
    with pytest.raises(ReplayAttackError):
        cache.check_and_register(c)


# 20. Same nonce but different session ID -> treated as different context
def test_replay_same_nonce_different_session_accepted():
    cache = ReplayProtectionCache()
    c1 = AuthenticationChallenge(
        initiator_id="T1", responder_id="T2", nonce="N1", session_id="S1", tracking_epoch=7, timestamp=time.time()
    )
    c2 = AuthenticationChallenge(
        initiator_id="T1", responder_id="T2", nonce="N1", session_id="S2", tracking_epoch=7, timestamp=time.time()
    )
    cache.check_and_register(c1)
    assert cache.is_replayed(c1) is True
    assert cache.is_replayed(c2) is False
    cache.check_and_register(c2)  # Should succeed cleanly


# 21. Same nonce and session but different tracking epoch -> different context
def test_replay_same_nonce_different_epoch_accepted():
    cache = ReplayProtectionCache()
    c1 = AuthenticationChallenge(
        initiator_id="T1", responder_id="T2", nonce="N1", session_id="S1", tracking_epoch=7, timestamp=time.time()
    )
    c2 = AuthenticationChallenge(
        initiator_id="T1", responder_id="T2", nonce="N1", session_id="S1", tracking_epoch=8, timestamp=time.time()
    )
    cache.check_and_register(c1)
    assert cache.is_replayed(c1) is True
    assert cache.is_replayed(c2) is False
    cache.check_and_register(c2)  # Should succeed cleanly


# 22. Different terminal direction -> different context
def test_replay_different_direction_accepted():
    cache = ReplayProtectionCache()
    c1 = AuthenticationChallenge(
        initiator_id="T1", responder_id="T2", nonce="N1", session_id="S1", tracking_epoch=7, timestamp=time.time()
    )
    c2 = AuthenticationChallenge(
        initiator_id="T2", responder_id="T1", nonce="N1", session_id="S1", tracking_epoch=7, timestamp=time.time()
    )
    cache.check_and_register(c1)
    assert cache.is_replayed(c1) is True
    assert cache.is_replayed(c2) is False
    cache.check_and_register(c2)  # Should succeed cleanly


# 23. Fresh nonce/session/context -> accepted
def test_replay_fresh_context_accepted():
    cache = ReplayProtectionCache()
    c1 = AuthenticationChallenge(
        initiator_id="T1", responder_id="T2", nonce="N1", session_id="S1", tracking_epoch=1, timestamp=time.time()
    )
    cache.check_and_register(c1)
    assert len(cache) == 1


# 24. Expired replay entries are removed or no longer considered active
def test_replay_ttl_expiry():
    cache = ReplayProtectionCache(ttl_seconds=1.0)
    now = 1000.0
    c1 = AuthenticationChallenge(
        initiator_id="T1", responder_id="T2", nonce="N1", session_id="S1", tracking_epoch=1, timestamp=now
    )
    cache.check_and_register(c1, current_time=now)
    assert cache.is_replayed(c1, current_time=now + 0.5) is True

    # At 2.0s later (> ttl_seconds 1.0s), entry must expire
    assert cache.is_replayed(c1, current_time=now + 2.0) is False
    # Registering again after expiry should succeed
    cache.check_and_register(c1, current_time=now + 2.0)


# 25. Cache does not exceed configured maximum size
def test_replay_max_entries_limit():
    cache = ReplayProtectionCache(max_entries=3, ttl_seconds=300.0)
    now = 1000.0

    for i in range(5):
        c = AuthenticationChallenge(
            initiator_id="T1", responder_id="T2", nonce=f"N{i}", session_id=f"S{i}", tracking_epoch=1, timestamp=now
        )
        cache.check_and_register(c, current_time=now)

    assert len(cache) == 3


# 26. Manual clear still works if retained
def test_replay_manual_clear():
    cache = ReplayProtectionCache()
    c1 = AuthenticationChallenge(
        initiator_id="T1", responder_id="T2", nonce="N1", session_id="S1", tracking_epoch=1, timestamp=time.time()
    )
    cache.check_and_register(c1)
    assert len(cache) == 1
    cache.clear()
    assert len(cache) == 0
    assert cache.is_replayed(c1) is False
