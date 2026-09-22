"""Unit tests for Phase 1: Terminal Identity."""

import pytest
from pathlib import Path
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, x25519

from src.identity import (
    CredentialNotFoundError,
    InvalidCredentialError,
    TerminalCredentials,
    TerminalIdentity,
    TerminalNotFoundError,
    TerminalPrivateCredentials,
    TerminalPublicCredentials,
    TerminalRegistry,
    generate_credentials,
    load_credentials,
    save_credentials,
    validate_credentials,
)


@pytest.fixture
def temp_keys_dir(tmp_path: Path) -> Path:
    """Fixture providing a temporary directory for saving and loading keys."""
    keys_dir = tmp_path / "keys"
    keys_dir.mkdir()
    return keys_dir


@pytest.fixture
def temp_config_file(tmp_path: Path) -> Path:
    """Fixture providing a temporary terminals.json config file."""
    config_file = tmp_path / "terminals.json"
    config_file.write_text(
        '{"terminals": [{"terminal_id": "T1", "name": "Term 1"}, {"terminal_id": "T2", "name": "Term 2"}]}',
        encoding="utf-8",
    )
    return config_file


# 1. T1 credential generation
def test_t1_credential_generation():
    creds = generate_credentials("T1")
    assert creds.terminal_id == "T1"
    assert creds.has_private_key is True
    assert isinstance(creds.public_credentials.identity_public_key, ed25519.Ed25519PublicKey)
    assert isinstance(creds.public_credentials.agreement_public_key, x25519.X25519PublicKey)
    assert isinstance(creds.private_credentials.identity_private_key, ed25519.Ed25519PrivateKey)
    assert isinstance(creds.private_credentials.agreement_private_key, x25519.X25519PrivateKey)


# 2. T2 credential generation
def test_t2_credential_generation():
    creds = generate_credentials("T2")
    assert creds.terminal_id == "T2"
    assert creds.has_private_key is True
    assert isinstance(creds.public_credentials.identity_public_key, ed25519.Ed25519PublicKey)
    assert isinstance(creds.public_credentials.agreement_public_key, x25519.X25519PublicKey)


# 3. Credentials can be saved
def test_credentials_can_be_saved(temp_keys_dir: Path):
    creds = generate_credentials("T1")
    saved_path = save_credentials(creds, temp_keys_dir)
    assert saved_path.exists()
    assert (saved_path / "identity_public.pem").exists()
    assert (saved_path / "identity_private.pem").exists()
    assert (saved_path / "agreement_public.pem").exists()
    assert (saved_path / "agreement_private.pem").exists()


# 4. Credentials can be loaded
def test_credentials_can_be_loaded(temp_keys_dir: Path):
    generated = generate_credentials("T1")
    save_credentials(generated, temp_keys_dir)
    
    loaded = load_credentials("T1", temp_keys_dir, load_private=True)
    assert loaded.terminal_id == "T1"
    assert loaded.has_private_key is True
    assert validate_credentials(loaded) is True


# 5. Loaded public keys match generated public keys
def test_loaded_public_keys_match_generated(temp_keys_dir: Path):
    generated = generate_credentials("T1")
    save_credentials(generated, temp_keys_dir)
    loaded = load_credentials("T1", temp_keys_dir)

    gen_id_bytes = generated.public_credentials.get_identity_bytes()
    load_id_bytes = loaded.public_credentials.get_identity_bytes()
    assert gen_id_bytes == load_id_bytes

    gen_agr_bytes = generated.public_credentials.get_agreement_bytes()
    load_agr_bytes = loaded.public_credentials.get_agreement_bytes()
    assert gen_agr_bytes == load_agr_bytes


# 6. Loaded private keys match generated private keys
def test_loaded_private_keys_match_generated(temp_keys_dir: Path):
    generated = generate_credentials("T1")
    save_credentials(generated, temp_keys_dir)
    loaded = load_credentials("T1", temp_keys_dir, load_private=True)

    gen_id_priv_pem = generated.private_credentials.identity_private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    load_id_priv_pem = loaded.private_credentials.identity_private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    assert gen_id_priv_pem == load_id_priv_pem


# 7. T1 and T2 have different identities
def test_t1_and_t2_have_different_identities():
    t1 = generate_credentials("T1")
    t2 = generate_credentials("T2")

    assert t1.terminal_id != t2.terminal_id
    assert t1.fingerprint != t2.fingerprint


# 8. T1 and T2 have different public keys
def test_t1_and_t2_have_different_public_keys():
    t1 = generate_credentials("T1")
    t2 = generate_credentials("T2")

    assert t1.public_credentials.get_identity_bytes() != t2.public_credentials.get_identity_bytes()
    assert t1.public_credentials.get_agreement_bytes() != t2.public_credentials.get_agreement_bytes()


# 9. Public key fingerprints are deterministic
def test_public_key_fingerprints_are_deterministic(temp_keys_dir: Path):
    creds = generate_credentials("T1")
    fp1 = creds.fingerprint
    fp2 = creds.public_credentials.compute_fingerprint()
    assert fp1 == fp2
    assert fp1.startswith("SHA256:")

    # Reload from disk and verify fingerprint matches
    save_credentials(creds, temp_keys_dir)
    loaded = load_credentials("T1", temp_keys_dir)
    assert loaded.fingerprint == fp1


# 10. Unknown terminal lookup fails cleanly
def test_unknown_terminal_lookup_fails_cleanly(temp_config_file: Path):
    registry = TerminalRegistry(temp_config_file)
    assert registry.is_known("T99") is False

    with pytest.raises(TerminalNotFoundError) as exc_info:
        registry.get_public_credentials("T99")
    assert "T99" in str(exc_info.value)


# 11. Missing credential files produce a useful error
def test_missing_credential_files_produce_useful_error(temp_keys_dir: Path):
    with pytest.raises(CredentialNotFoundError) as exc_info:
        load_credentials("NONEXISTENT", temp_keys_dir)
    assert "NONEXISTENT" in str(exc_info.value)

    # Partial directory created without keys
    (temp_keys_dir / "PARTIAL").mkdir()
    with pytest.raises(CredentialNotFoundError) as exc_info:
        load_credentials("PARTIAL", temp_keys_dir)
    assert "missing" in str(exc_info.value).lower()


# 12. Invalid credential data is rejected
def test_invalid_credential_data_is_rejected(temp_keys_dir: Path):
    target_dir = temp_keys_dir / "CORRUPT"
    target_dir.mkdir()

    # Write junk bytes to key files
    (target_dir / "identity_public.pem").write_bytes(b"NOT A PEM KEY")
    (target_dir / "agreement_public.pem").write_bytes(b"NOT A PEM KEY")

    with pytest.raises(InvalidCredentialError) as exc_info:
        load_credentials("CORRUPT", temp_keys_dir)
    assert "CORRUPT" in str(exc_info.value)


# 13. Security check: private key is masked in repr and str
def test_private_key_masked_in_repr():
    creds = generate_credentials("T1")
    priv_repr = repr(creds.private_credentials)
    priv_str = str(creds.private_credentials)

    assert "[REDACTED]" in priv_repr
    assert "[REDACTED]" in priv_str
    assert "PrivateKey" not in priv_repr  # Raw object address or key material not exposed


# 14. TerminalIdentity abstraction behavior
def test_terminal_identity_class(temp_keys_dir: Path):
    identity = TerminalIdentity.create_new("T1")
    assert identity.terminal_id == "T1"
    assert identity.has_private_key is True
    assert identity.validate() is True

    save_credentials(identity._credentials, temp_keys_dir)
    loaded_id = TerminalIdentity.from_dir("T1", temp_keys_dir, load_private=False)
    assert loaded_id.has_private_key is False
    with pytest.raises(ValueError) as exc:
        loaded_id.get_identity_private_key()
    assert "private key material" in str(exc.value)
