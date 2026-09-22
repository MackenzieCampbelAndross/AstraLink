"""CLI tool to generate and save cryptographic identity keys for Astra Link terminals."""

import argparse
import sys
from pathlib import Path

# Add src to sys.path so tool can be executed directly
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.identity import (
    TerminalRegistry,
    generate_credentials,
    save_credentials,
)


def main():
    parser = argparse.ArgumentParser(
        description="Generate Astra Link terminal identities and cryptographic keys."
    )
    parser.add_argument(
        "--terminals",
        nargs="+",
        default=["T1", "T2"],
        help="Terminal IDs to generate keys for (default: T1 T2).",
    )
    parser.add_argument(
        "--outdir",
        type=str,
        default=str(PROJECT_ROOT / "keys"),
        help="Directory to save generated key pairs (default: ./keys).",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=str(PROJECT_ROOT / "config" / "terminals.json"),
        help="Path to terminals.json configuration registry file.",
    )

    args = parser.parse_args()
    outdir = Path(args.outdir)
    config_path = Path(args.config)

    print("==================================================")
    print("      ASTRA LINK - KEY GENERATION TOOL            ")
    print("==================================================")
    print(f"Key Directory: {outdir}")
    print(f"Config File:   {config_path}\n")

    registry = TerminalRegistry(config_path if config_path.exists() else None)

    for tid in args.terminals:
        print(f"[*] Generating key pairs for Terminal [{tid}]...")
        creds = generate_credentials(tid)
        target_path = save_credentials(creds, outdir)
        registry.register_public_credentials(creds.public_credentials)

        print(f"    - Identity Key:  Ed25519 (32-byte public key)")
        print(f"    - Agreement Key: X25519  (32-byte public key)")
        print(f"    - Fingerprint:   {creds.fingerprint}")
        print(f"    - Saved to:      {target_path}")
        print(f"    [+] Credentials generated & saved successfully.\n")

    registry.save_config(config_path)
    print(f"[+] Updated public terminal registry at {config_path}")

    print("==================================================")
    print("KEY GENERATION COMPLETE.")
    print("Private keys are saved in PEM format under keys/.")
    print("Public credentials are registered in config/terminals.json.")
    print("Ensure private keys are kept secret & ignored by Git.")
    print("==================================================")


if __name__ == "__main__":
    main()
