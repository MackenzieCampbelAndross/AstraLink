"""Key management functions for generating, loading, saving, and validating terminal credentials."""

from pathlib import Path
from typing import Union

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, x25519

from .credentials import (
    TerminalCredentials,
    TerminalPrivateCredentials,
    TerminalPublicCredentials,
)


class IdentityError(Exception):
    """Base exception for terminal identity module."""
    pass


class CredentialNotFoundError(IdentityError):
    """Raised when credentials for a terminal cannot be found."""
    pass


class InvalidCredentialError(IdentityError):
    """Raised when credential data is corrupted, invalid, or mismatched."""
    pass


def generate_credentials(terminal_id: str) -> TerminalCredentials:
    """Generate fresh Ed25519 and X25519 key pairs for a terminal ID.
    
    Args:
        terminal_id: The terminal identifier (e.g. "T1", "T2").
        
    Returns:
        A TerminalCredentials object containing public and private keys.
    """
    if not terminal_id or not isinstance(terminal_id, str):
        raise ValueError("terminal_id must be a non-empty string.")

    identity_private = ed25519.Ed25519PrivateKey.generate()
    identity_public = identity_private.public_key()

    agreement_private = x25519.X25519PrivateKey.generate()
    agreement_public = agreement_private.public_key()

    public_creds = TerminalPublicCredentials(
        terminal_id=terminal_id,
        identity_public_key=identity_public,
        agreement_public_key=agreement_public,
    )

    private_creds = TerminalPrivateCredentials(
        terminal_id=terminal_id,
        identity_private_key=identity_private,
        agreement_private_key=agreement_private,
    )

    return TerminalCredentials(
        public_credentials=public_creds,
        private_credentials=private_creds,
    )


def save_credentials(credentials: TerminalCredentials, base_dir: Union[str, Path]) -> Path:
    """Save terminal credentials to PEM files under base_dir/<terminal_id>/.
    
    Args:
        credentials: The credentials bundle to save.
        base_dir: Directory where keys should be saved.
        
    Returns:
        Path to the terminal's key directory.
    """
    if not validate_credentials(credentials):
        raise InvalidCredentialError(f"Cannot save invalid credentials for {credentials.terminal_id}")

    target_dir = Path(base_dir) / credentials.terminal_id
    target_dir.mkdir(parents=True, exist_ok=True)

    # Save Public Keys
    pub_id_pem = credentials.public_credentials.identity_public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    (target_dir / "identity_public.pem").write_bytes(pub_id_pem)

    pub_agr_pem = credentials.public_credentials.agreement_public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    (target_dir / "agreement_public.pem").write_bytes(pub_agr_pem)

    # Save Private Keys (if present)
    if credentials.private_credentials is not None:
        priv_id_pem = credentials.private_credentials.identity_private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        (target_dir / "identity_private.pem").write_bytes(priv_id_pem)

        priv_agr_pem = credentials.private_credentials.agreement_private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        (target_dir / "agreement_private.pem").write_bytes(priv_agr_pem)

    return target_dir


def load_credentials(
    terminal_id: str,
    base_dir: Union[str, Path],
    load_private: bool = True,
) -> TerminalCredentials:
    """Load terminal credentials from disk PEM files.
    
    Args:
        terminal_id: The terminal identifier.
        base_dir: Base directory containing key folders.
        load_private: Whether to load private keys as well.
        
    Returns:
        TerminalCredentials instance.
        
    Raises:
        CredentialNotFoundError: If credential directory or public key files are missing.
        InvalidCredentialError: If loaded files are corrupted, invalid, or mismatched.
    """
    target_dir = Path(base_dir) / terminal_id
    if not target_dir.exists() or not target_dir.is_dir():
        raise CredentialNotFoundError(f"Credential directory not found for terminal {terminal_id} at {target_dir}")

    pub_id_path = target_dir / "identity_public.pem"
    pub_agr_path = target_dir / "agreement_public.pem"

    if not pub_id_path.exists() or not pub_agr_path.exists():
        raise CredentialNotFoundError(f"Public credential files missing for terminal {terminal_id}")

    try:
        pub_id_key = serialization.load_pem_public_key(pub_id_path.read_bytes())
        if not isinstance(pub_id_key, ed25519.Ed25519PublicKey):
            raise InvalidCredentialError(f"Identity key for {terminal_id} is not an Ed25519 public key")

        pub_agr_key = serialization.load_pem_public_key(pub_agr_path.read_bytes())
        if not isinstance(pub_agr_key, x25519.X25519PublicKey):
            raise InvalidCredentialError(f"Agreement key for {terminal_id} is not an X25519 public key")

    except (ValueError, TypeError) as e:
        raise InvalidCredentialError(f"Failed to parse public keys for terminal {terminal_id}: {e}") from e

    public_creds = TerminalPublicCredentials(
        terminal_id=terminal_id,
        identity_public_key=pub_id_key,
        agreement_public_key=pub_agr_key,
    )

    private_creds = None

    if load_private:
        priv_id_path = target_dir / "identity_private.pem"
        priv_agr_path = target_dir / "agreement_private.pem"

        if not priv_id_path.exists() or not priv_agr_path.exists():
            raise CredentialNotFoundError(f"Private credential files missing for terminal {terminal_id}")

        try:
            priv_id_key = serialization.load_pem_private_key(priv_id_path.read_bytes(), password=None)
            if not isinstance(priv_id_key, ed25519.Ed25519PrivateKey):
                raise InvalidCredentialError(f"Identity private key for {terminal_id} is not Ed25519")

            priv_agr_key = serialization.load_pem_private_key(priv_agr_path.read_bytes(), password=None)
            if not isinstance(priv_agr_key, x25519.X25519PrivateKey):
                raise InvalidCredentialError(f"Agreement private key for {terminal_id} is not X25519")

        except (ValueError, TypeError) as e:
            raise InvalidCredentialError(f"Failed to parse private keys for terminal {terminal_id}: {e}") from e

        # Validate that loaded private keys match public keys
        derived_pub_id = priv_id_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw
        )
        loaded_pub_id = pub_id_key.public_bytes(
            encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw
        )
        if derived_pub_id != loaded_pub_id:
            raise InvalidCredentialError(f"Private identity key does not match public key for {terminal_id}")

        derived_pub_agr = priv_agr_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw
        )
        loaded_pub_agr = pub_agr_key.public_bytes(
            encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw
        )
        if derived_pub_agr != loaded_pub_agr:
            raise InvalidCredentialError(f"Private agreement key does not match public key for {terminal_id}")

        private_creds = TerminalPrivateCredentials(
            terminal_id=terminal_id,
            identity_private_key=priv_id_key,
            agreement_private_key=priv_agr_key,
        )

    creds = TerminalCredentials(public_credentials=public_creds, private_credentials=private_creds)
    validate_credentials(creds)
    return creds


def validate_credentials(credentials: TerminalCredentials) -> bool:
    """Validate integrity and consistency of terminal credentials.
    
    Returns:
        True if credentials pass validation.
        
    Raises:
        InvalidCredentialError: If credentials fail validation.
    """
    if not credentials.terminal_id or not isinstance(credentials.terminal_id, str):
        raise InvalidCredentialError("Terminal ID must be a non-empty string.")

    if not isinstance(credentials.public_credentials.identity_public_key, ed25519.Ed25519PublicKey):
        raise InvalidCredentialError("Identity public key must be Ed25519PublicKey.")

    if not isinstance(credentials.public_credentials.agreement_public_key, x25519.X25519PublicKey):
        raise InvalidCredentialError("Agreement public key must be X25519PublicKey.")

    if credentials.private_credentials is not None:
        if not isinstance(credentials.private_credentials.identity_private_key, ed25519.Ed25519PrivateKey):
            raise InvalidCredentialError("Identity private key must be Ed25519PrivateKey.")

        if not isinstance(credentials.private_credentials.agreement_private_key, x25519.X25519PrivateKey):
            raise InvalidCredentialError("Agreement private key must be X25519PrivateKey.")

        # Check match between public key and private key
        id_derived = credentials.private_credentials.identity_private_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw
        )
        id_actual = credentials.public_credentials.get_identity_bytes()
        if id_derived != id_actual:
            raise InvalidCredentialError(f"Identity private key does not match public key for {credentials.terminal_id}")

        agr_derived = credentials.private_credentials.agreement_private_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw
        )
        agr_actual = credentials.public_credentials.get_agreement_bytes()
        if agr_derived != agr_actual:
            raise InvalidCredentialError(f"Agreement private key does not match public key for {credentials.terminal_id}")

    return True
