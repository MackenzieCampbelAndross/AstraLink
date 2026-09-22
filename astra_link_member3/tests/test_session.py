"""Unit tests for Phase 4: Secure Session Establishment."""

import time
import pytest
from cryptography.hazmat.primitives.asymmetric import x25519

from src.session import (
    ActiveSession,
    DerivedSessionKeys,
    EphemeralKeyPair,
    KeyExchange,
    SessionAuthorizationError,
    SessionContext,
    SessionManager,
    SessionNotFoundError,
    SessionState,
    derive_session_key_material,
    execute_rekey,
)


# 1. Ephemeral X25519 key pair generation
def test_ephemeral_key_pair_generation():
    kp = EphemeralKeyPair.generate("T1")
    assert kp.terminal_id == "T1"
    assert isinstance(kp.public_key, x25519.X25519PublicKey)
    assert len(kp.get_public_bytes()) == 32


# 2. T1 and T2 produce different ephemeral public keys
def test_t1_t2_different_ephemeral_public_keys():
    kp1 = EphemeralKeyPair.generate("T1")
    kp2 = EphemeralKeyPair.generate("T2")
    assert kp1.get_public_bytes() != kp2.get_public_bytes()


# 3. T1 and T2 derive the same shared secret
def test_t1_t2_derive_same_shared_secret():
    t1_ephemeral = EphemeralKeyPair.generate("T1")
    t2_ephemeral = EphemeralKeyPair.generate("T2")

    ss1 = KeyExchange.derive_shared_secret(t1_ephemeral, t2_ephemeral.public_key)
    ss2 = KeyExchange.derive_shared_secret(t2_ephemeral, t1_ephemeral.public_key)

    assert ss1 == ss2
    assert len(ss1) == 32


# 4. Different ephemeral key pairs produce different shared secrets
def test_different_ephemerals_produce_different_shared_secrets():
    t1_a = EphemeralKeyPair.generate("T1")
    t2_a = EphemeralKeyPair.generate("T2")
    t1_b = EphemeralKeyPair.generate("T1")
    t2_b = EphemeralKeyPair.generate("T2")

    ss_a = KeyExchange.derive_shared_secret(t1_a, t2_a.public_key)
    ss_b = KeyExchange.derive_shared_secret(t1_b, t2_b.public_key)

    assert ss_a != ss_b


# 5. HKDF derives deterministic output for identical inputs
def test_hkdf_derivation_deterministic():
    t1_ephemeral = EphemeralKeyPair.generate("T1")
    t2_ephemeral = EphemeralKeyPair.generate("T2")
    ss = KeyExchange.derive_shared_secret(t1_ephemeral, t2_ephemeral.public_key)

    ctx = SessionContext(
        session_id="session_100",
        initiator_id="T1",
        responder_id="T2",
        tracking_epoch=1,
        created_at=1000.0,
        initiator_ephemeral_public_key=t1_ephemeral.public_key,
        responder_ephemeral_public_key=t2_ephemeral.public_key,
    )

    keys1 = derive_session_key_material(ss, ctx)
    keys2 = derive_session_key_material(ss, ctx)

    assert keys1.initiator_to_responder_key == keys2.initiator_to_responder_key
    assert keys1.responder_to_initiator_key == keys2.responder_to_initiator_key


# 6. Different session IDs produce different derived keys
def test_different_session_ids_produce_different_keys():
    t1_ephemeral = EphemeralKeyPair.generate("T1")
    t2_ephemeral = EphemeralKeyPair.generate("T2")
    ss = KeyExchange.derive_shared_secret(t1_ephemeral, t2_ephemeral.public_key)

    ctx1 = SessionContext(
        session_id="session_A",
        initiator_id="T1",
        responder_id="T2",
        tracking_epoch=1,
        created_at=1000.0,
        initiator_ephemeral_public_key=t1_ephemeral.public_key,
        responder_ephemeral_public_key=t2_ephemeral.public_key,
    )

    ctx2 = SessionContext(
        session_id="session_B",
        initiator_id="T1",
        responder_id="T2",
        tracking_epoch=1,
        created_at=1000.0,
        initiator_ephemeral_public_key=t1_ephemeral.public_key,
        responder_ephemeral_public_key=t2_ephemeral.public_key,
    )

    keys1 = derive_session_key_material(ss, ctx1)
    keys2 = derive_session_key_material(ss, ctx2)

    assert keys1.initiator_to_responder_key != keys2.initiator_to_responder_key


# 7. Different tracking epochs produce different derived keys
def test_different_tracking_epochs_produce_different_keys():
    t1_ephemeral = EphemeralKeyPair.generate("T1")
    t2_ephemeral = EphemeralKeyPair.generate("T2")
    ss = KeyExchange.derive_shared_secret(t1_ephemeral, t2_ephemeral.public_key)

    ctx_epoch1 = SessionContext(
        session_id="session_100",
        initiator_id="T1",
        responder_id="T2",
        tracking_epoch=1,
        created_at=1000.0,
        initiator_ephemeral_public_key=t1_ephemeral.public_key,
        responder_ephemeral_public_key=t2_ephemeral.public_key,
    )

    ctx_epoch2 = SessionContext(
        session_id="session_100",
        initiator_id="T1",
        responder_id="T2",
        tracking_epoch=2,
        created_at=1000.0,
        initiator_ephemeral_public_key=t1_ephemeral.public_key,
        responder_ephemeral_public_key=t2_ephemeral.public_key,
    )

    keys1 = derive_session_key_material(ss, ctx_epoch1)
    keys2 = derive_session_key_material(ss, ctx_epoch2)

    assert keys1.initiator_to_responder_key != keys2.initiator_to_responder_key


# 8. Different peer identities produce different derived keys
def test_different_peer_identities_produce_different_keys():
    t1_ephemeral = EphemeralKeyPair.generate("T1")
    t2_ephemeral = EphemeralKeyPair.generate("T2")
    ss = KeyExchange.derive_shared_secret(t1_ephemeral, t2_ephemeral.public_key)

    ctx1 = SessionContext(
        session_id="session_100",
        initiator_id="T1",
        responder_id="T2",
        tracking_epoch=1,
        created_at=1000.0,
        initiator_ephemeral_public_key=t1_ephemeral.public_key,
        responder_ephemeral_public_key=t2_ephemeral.public_key,
    )

    ctx2 = SessionContext(
        session_id="session_100",
        initiator_id="T1",
        responder_id="T3",  # Peer T3
        tracking_epoch=1,
        created_at=1000.0,
        initiator_ephemeral_public_key=t1_ephemeral.public_key,
        responder_ephemeral_public_key=t2_ephemeral.public_key,
    )

    keys1 = derive_session_key_material(ss, ctx1)
    keys2 = derive_session_key_material(ss, ctx2)

    assert keys1.initiator_to_responder_key != keys2.initiator_to_responder_key


# 9. Initiator and responder derive matching directional key material
def test_initiator_and_responder_derive_matching_directional_keys():
    t1_ephemeral = EphemeralKeyPair.generate("T1")
    t2_ephemeral = EphemeralKeyPair.generate("T2")

    ss1 = KeyExchange.derive_shared_secret(t1_ephemeral, t2_ephemeral.public_key)
    ss2 = KeyExchange.derive_shared_secret(t2_ephemeral, t1_ephemeral.public_key)

    ctx = SessionContext(
        session_id="session_shared",
        initiator_id="T1",
        responder_id="T2",
        tracking_epoch=1,
        created_at=1000.0,
        initiator_ephemeral_public_key=t1_ephemeral.public_key,
        responder_ephemeral_public_key=t2_ephemeral.public_key,
    )

    keys1 = derive_session_key_material(ss1, ctx)
    keys2 = derive_session_key_material(ss2, ctx)

    # T1 -> T2 key derived on T1 side matches T1 -> T2 key derived on T2 side
    assert keys1.t1_to_t2_key == keys2.t1_to_t2_key
    assert keys1.t2_to_t1_key == keys2.t2_to_t1_key
    assert keys1.t1_to_t2_key != keys1.t2_to_t1_key  # Clean directional separation


# 10. Mutual authentication required before session establishment
def test_mutual_auth_required_before_session():
    manager = SessionManager()
    with pytest.raises(SessionAuthorizationError) as exc:
        manager.establish_session(
            initiator_id="T1",
            responder_id="T2",
            tracking_epoch=1,
            authentication_valid=False,  # Unauthenticated
            trust_authorized=True,
        )
    assert "BLOCKED" in str(exc.value)


# 11. Unauthenticated terminal cannot establish session
def test_unauthenticated_terminal_cannot_establish_session():
    manager = SessionManager()
    with pytest.raises(SessionAuthorizationError):
        manager.establish_session(
            initiator_id="T1",
            responder_id="T2",
            tracking_epoch=1,
            authentication_valid=False,
            trust_authorized=False,
        )


# 12. Valid authenticated terminals establish session
def test_valid_authenticated_terminals_establish_session():
    manager = SessionManager()
    session = manager.establish_session(
        initiator_id="T1",
        responder_id="T2",
        tracking_epoch=1,
        authentication_valid=True,
        trust_authorized=True,
    )
    assert session.session_id is not None
    assert session.state == SessionState.ESTABLISHED
    assert len(session.derived_keys.t1_to_t2_key) == 32
    assert len(session.derived_keys.t2_to_t1_key) == 32


# 13. Session has explicit ESTABLISHED state
def test_session_explicit_established_state():
    manager = SessionManager()
    session = manager.establish_session("T1", "T2", 1, True, True)
    assert session.state == SessionState.ESTABLISHED
    assert manager.is_session_valid(session.session_id) is True


# 14. Session expiration works
def test_session_expiration_works():
    manager = SessionManager(session_lifetime_seconds=5.0)
    session = manager.establish_session("T1", "T2", 1, True, True)
    
    # Valid at creation time
    assert manager.is_session_valid(session.session_id, current_time=session.context.created_at) is True

    # Expired 10 seconds later
    expired_time = session.context.created_at + 10.0
    assert manager.is_session_valid(session.session_id, current_time=expired_time) is False
    assert session.state == SessionState.EXPIRED


# 15. Terminated session cannot be used as active
def test_terminated_session_cannot_be_used():
    manager = SessionManager()
    session = manager.establish_session("T1", "T2", 1, True, True)
    assert manager.is_session_valid(session.session_id) is True

    manager.terminate_session(session.session_id)
    assert session.state == SessionState.TERMINATED
    assert manager.is_session_valid(session.session_id) is False


# 16. Rekey produces new key material
def test_rekey_produces_new_key_material():
    manager = SessionManager()
    session = manager.establish_session("T1", "T2", 1, True, True)
    old_key_t1_t2 = session.derived_keys.t1_to_t2_key
    old_key_t2_t1 = session.derived_keys.t2_to_t1_key

    updated_session = manager.rekey_session(session.session_id)
    new_key_t1_t2 = updated_session.derived_keys.t1_to_t2_key
    new_key_t2_t1 = updated_session.derived_keys.t2_to_t1_key

    assert old_key_t1_t2 != new_key_t1_t2
    assert old_key_t2_t1 != new_key_t2_t1
    assert updated_session.state == SessionState.ESTABLISHED


# 17. Rekey does not alter transfer state representation
def test_rekey_preserves_session_context_fields():
    manager = SessionManager()
    session = manager.establish_session("T1", "T2", 7, True, True)
    orig_session_id = session.session_id
    orig_epoch = session.tracking_epoch

    rekeyed = manager.rekey_session(session.session_id)
    assert rekeyed.session_id == orig_session_id
    assert rekeyed.tracking_epoch == orig_epoch


# 18. Session IDs are fresh
def test_session_ids_are_fresh():
    manager = SessionManager()
    s1 = manager.establish_session("T1", "T2", 1, True, True)
    s2 = manager.establish_session("T1", "T2", 1, True, True)
    assert s1.session_id != s2.session_id


# 19. Ephemeral keys are fresh per session
def test_ephemeral_keys_fresh_per_session():
    manager = SessionManager()
    s1 = manager.establish_session("T1", "T2", 1, True, True)
    s2 = manager.establish_session("T1", "T2", 1, True, True)
    assert s1.initiator_ephemeral.get_public_bytes() != s2.initiator_ephemeral.get_public_bytes()


# 20. Private/shared secret material is not leaked through repr/str/logging
def test_private_material_not_leaked():
    kp = EphemeralKeyPair.generate("T1")
    kp_str = str(kp)
    assert "[REDACTED]" in kp_str

    ctx = SessionContext("s1", "T1", "T2", 1, 100.0, kp.public_key, kp.public_key)
    derived = DerivedSessionKeys(b"1" * 32, b"2" * 32, "T1", "T2")
    derived_str = str(derived)
    assert "[REDACTED]" in derived_str


# 21. Negative test: ID mismatch in rekey
def test_rekey_id_mismatch_fails():
    t1_ephemeral = EphemeralKeyPair.generate("T1")
    t2_ephemeral = EphemeralKeyPair.generate("T2")
    wrong_ephemeral = EphemeralKeyPair.generate("T99")

    ctx = SessionContext("s1", "T1", "T2", 1, 100.0, t1_ephemeral.public_key, t2_ephemeral.public_key)
    with pytest.raises(ValueError) as exc:
        execute_rekey(ctx, wrong_ephemeral, t2_ephemeral)
    assert "Initiator ID mismatch" in str(exc.value)


# 22. Negative test: Epoch mismatch in HKDF
def test_negative_epoch_mismatch_derivation():
    t1_ephemeral = EphemeralKeyPair.generate("T1")
    t2_ephemeral = EphemeralKeyPair.generate("T2")
    ss = KeyExchange.derive_shared_secret(t1_ephemeral, t2_ephemeral.public_key)

    c1 = SessionContext("s1", "T1", "T2", 1, 100.0, t1_ephemeral.public_key, t2_ephemeral.public_key)
    c2 = SessionContext("s1", "T1", "T2", 2, 100.0, t1_ephemeral.public_key, t2_ephemeral.public_key)

    k1 = derive_session_key_material(ss, c1)
    k2 = derive_session_key_material(ss, c2)

    assert k1.t1_to_t2_key != k2.t1_to_t2_key


# 23. Negative test: Modified ephemeral public key
def test_negative_modified_ephemeral_public_key():
    t1_ephemeral = EphemeralKeyPair.generate("T1")
    t2_ephemeral = EphemeralKeyPair.generate("T2")
    t3_ephemeral = EphemeralKeyPair.generate("T2")  # Modified public key!

    ss = KeyExchange.derive_shared_secret(t1_ephemeral, t2_ephemeral.public_key)

    c1 = SessionContext("s1", "T1", "T2", 1, 100.0, t1_ephemeral.public_key, t2_ephemeral.public_key)
    c2 = SessionContext("s1", "T1", "T2", 1, 100.0, t1_ephemeral.public_key, t3_ephemeral.public_key)

    k1 = derive_session_key_material(ss, c1)
    k2 = derive_session_key_material(ss, c2)

    assert k1.t1_to_t2_key != k2.t1_to_t2_key
