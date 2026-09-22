"""Terminal identity abstraction and trusted terminal registry."""

import json
from pathlib import Path
from typing import Dict, List, Optional, Union

from cryptography.hazmat.primitives.asymmetric import ed25519, x25519

from .credentials import (
    TerminalCredentials,
    TerminalPublicCredentials,
)
from .key_management import (
    CredentialNotFoundError,
    generate_credentials,
    load_credentials,
    validate_credentials,
)


class TerminalNotFoundError(CredentialNotFoundError):
    """Raised when an operation references an unknown or unregistered terminal."""
    pass


class TerminalIdentity:
    """Abstraction representing a single Astra Link terminal's cryptographic identity."""

    def __init__(self, credentials: TerminalCredentials):
        validate_credentials(credentials)
        self._credentials = credentials

    @property
    def terminal_id(self) -> str:
        return self._credentials.terminal_id

    @property
    def public_credentials(self) -> TerminalPublicCredentials:
        return self._credentials.public_credentials

    @property
    def identity_public_key(self) -> ed25519.Ed25519PublicKey:
        return self._credentials.public_credentials.identity_public_key

    @property
    def agreement_public_key(self) -> x25519.X25519PublicKey:
        return self._credentials.public_credentials.agreement_public_key

    @property
    def fingerprint(self) -> str:
        return self._credentials.fingerprint

    @property
    def has_private_key(self) -> bool:
        return self._credentials.has_private_key

    def get_identity_private_key(self) -> ed25519.Ed25519PrivateKey:
        """Access the Ed25519 private key if present."""
        if not self._credentials.private_credentials:
            raise ValueError(f"Terminal {self.terminal_id} does not contain private key material.")
        return self._credentials.private_credentials.identity_private_key

    def get_agreement_private_key(self) -> x25519.X25519PrivateKey:
        """Access the X25519 private key if present."""
        if not self._credentials.private_credentials:
            raise ValueError(f"Terminal {self.terminal_id} does not contain private key material.")
        return self._credentials.private_credentials.agreement_private_key

    def validate(self) -> bool:
        """Validate identity credentials."""
        return validate_credentials(self._credentials)

    @classmethod
    def create_new(cls, terminal_id: str) -> "TerminalIdentity":
        """Generate a brand new TerminalIdentity instance."""
        creds = generate_credentials(terminal_id)
        return cls(creds)

    @classmethod
    def from_dir(
        cls,
        terminal_id: str,
        keys_dir: Union[str, Path],
        load_private: bool = True,
    ) -> "TerminalIdentity":
        """Load a TerminalIdentity from saved PEM files."""
        creds = load_credentials(terminal_id, keys_dir, load_private=load_private)
        return cls(creds)

    def __repr__(self) -> str:
        return f"TerminalIdentity(terminal_id={self.terminal_id!r}, fingerprint={self.fingerprint!r})"


class TerminalRegistry:
    """Trusted store for authorized Astra Link terminals and public credentials."""

    def __init__(self, config_path: Optional[Union[str, Path]] = None):
        self._configured_terminals: Dict[str, dict] = {}
        self._public_credentials: Dict[str, TerminalPublicCredentials] = {}

        if config_path:
            self.load_config(config_path)

    def load_config(self, config_path: Union[str, Path]) -> None:
        """Load configured authorized terminals from JSON configuration file."""
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        data = json.loads(path.read_text(encoding="utf-8"))
        terminals_list = data.get("terminals", [])
        for t_info in terminals_list:
            tid = t_info.get("terminal_id")
            if tid:
                self._configured_terminals[tid] = t_info
                # If entry contains public key credentials, parse & register them
                if "identity_public_key" in t_info and "agreement_public_key" in t_info:
                    try:
                        pub_creds = TerminalPublicCredentials.from_dict(t_info)
                        self._public_credentials[tid] = pub_creds
                    except ValueError:
                        pass

    def save_config(self, config_path: Union[str, Path]) -> None:
        """Save registered terminal metadata & public keys to terminals.json."""
        path = Path(config_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        terminals_list = []
        for tid in sorted(self.list_known_terminals()):
            if tid in self._public_credentials:
                pub_creds = self._public_credentials[tid]
                name = self._configured_terminals.get(tid, {}).get("name", f"Terminal {tid}")
                terminals_list.append(pub_creds.to_dict(name=name))
            else:
                t_info = self._configured_terminals.get(tid, {"terminal_id": tid, "name": f"Terminal {tid}"})
                terminals_list.append(t_info)

        payload = {"terminals": terminals_list}
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def register_public_credentials(
        self, public_creds: TerminalPublicCredentials, name: Optional[str] = None
    ) -> None:
        """Register public credentials for a terminal."""
        if not isinstance(public_creds, TerminalPublicCredentials):
            raise ValueError("Expected TerminalPublicCredentials instance.")
        tid = public_creds.terminal_id
        self._public_credentials[tid] = public_creds
        
        current_name = name or self._configured_terminals.get(tid, {}).get("name") or f"Terminal {tid}"
        self._configured_terminals[tid] = public_creds.to_dict(name=current_name)

    def load_keys_from_dir(self, keys_dir: Union[str, Path]) -> None:
        """Load public credentials for all known terminals found in keys_dir."""
        base_dir = Path(keys_dir)
        if not base_dir.exists():
            return

        for t_dir in base_dir.iterdir():
            if t_dir.is_dir():
                tid = t_dir.name
                try:
                    creds = load_credentials(tid, base_dir, load_private=False)
                    self.register_public_credentials(creds.public_credentials)
                except CredentialNotFoundError:
                    continue

    def is_known(self, terminal_id: str) -> bool:
        """Check if a terminal is registered in the trusted registry."""
        return terminal_id in self._configured_terminals or terminal_id in self._public_credentials

    def get_public_credentials(self, terminal_id: str) -> TerminalPublicCredentials:
        """Retrieve public credentials for a known terminal.
        
        Raises:
            TerminalNotFoundError: If terminal is unknown or public key is not registered.
        """
        if not self.is_known(terminal_id):
            raise TerminalNotFoundError(f"Terminal '{terminal_id}' is not a recognized terminal.")

        if terminal_id not in self._public_credentials:
            raise TerminalNotFoundError(
                f"Terminal '{terminal_id}' is authorized in config but public credentials are not loaded."
            )

        return self._public_credentials[terminal_id]

    def get_fingerprint(self, terminal_id: str) -> str:
        """Get the human readable identity fingerprint for a known terminal."""
        creds = self.get_public_credentials(terminal_id)
        return creds.compute_fingerprint()

    def list_known_terminals(self) -> List[str]:
        """Return a sorted list of all known terminal IDs."""
        all_ids = set(self._configured_terminals.keys()).union(self._public_credentials.keys())
        return sorted(list(all_ids))
