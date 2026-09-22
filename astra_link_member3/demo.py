"""Phase 1 Terminal Identity Demonstration for Astra Link."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.identity import (
    TerminalIdentity,
    TerminalRegistry,
    generate_credentials,
    save_credentials,
)


def run_demo():
    print("==================================================")
    print("    ASTRA LINK MEMBER 3 - PHASE 1 DEMONSTRATION  ")
    print("==================================================")
    print()

    keys_dir = PROJECT_ROOT / "keys"
    config_path = PROJECT_ROOT / "config" / "terminals.json"

    # 1. Generate T1 Identity
    t1_identity = TerminalIdentity.create_new("T1")
    save_credentials(t1_identity._credentials, keys_dir)
    print("T1 identity created")
    print(f"T1 fingerprint: {t1_identity.fingerprint}")

    # 2. Generate T2 Identity
    t2_identity = TerminalIdentity.create_new("T2")
    save_credentials(t2_identity._credentials, keys_dir)
    print("T2 identity created")
    print(f"T2 fingerprint: {t2_identity.fingerprint}")
    print()

    # 3. Register public credentials in registry & save config
    registry = TerminalRegistry()
    registry.register_public_credentials(t1_identity.public_credentials, name="Terminal 1 (Ground Base)")
    registry.register_public_credentials(t2_identity.public_credentials, name="Terminal 2 (Mobile Asset)")
    registry.save_config(config_path)

    # 4. Reload registry from config file to verify persistence
    reloaded_registry = TerminalRegistry(config_path)

    # 5. Lookup Public Identities in Registry
    if reloaded_registry.is_known("T1"):
        t1_pub = reloaded_registry.get_public_credentials("T1")
        print("T1 public identity available")
        print(f"   Registered Fingerprint: {t1_pub.compute_fingerprint()}")

    if reloaded_registry.is_known("T2"):
        t2_pub = reloaded_registry.get_public_credentials("T2")
        print("T2 public identity available")
        print(f"   Registered Fingerprint: {t2_pub.compute_fingerprint()}")

    print("Registry lookup successful")
    print()

    # 6. Validate loaded credentials from disk
    t1_loaded = TerminalIdentity.from_dir("T1", keys_dir, load_private=True)
    t2_loaded = TerminalIdentity.from_dir("T2", keys_dir, load_private=True)

    t1_valid = t1_loaded.validate()
    t2_valid = t2_loaded.validate()

    if t1_valid and t2_valid:
        print("Credential validation successful")
    else:
        print("Credential validation failed")

    print()
    print("--------------------------------------------------")
    print("Security Verification:")
    print(f"T1 object string representation: {t1_loaded}")
    print(f"T1 private credential representation: {t1_loaded._credentials.private_credentials}")
    print("Notice: No private key material is exposed or printed.")
    print("==================================================")


if __name__ == "__main__":
    run_demo()
