"""PacketCipher executing AES-GCM authenticated encryption and decryption."""

import hashlib
from typing import Union

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .packet import EncryptedPacket, compute_packet_aad


class TransportError(Exception):
    """Base exception for transport layer errors."""
    pass


class InvalidPacketError(TransportError):
    """Raised when AES-GCM decryption fails due to corrupted ciphertext, invalid tag, or tampered metadata."""
    pass


def generate_gcm_nonce(
    session_id: str,
    direction: str,
    sequence_number: int,
    transfer_id: str,
) -> bytes:
    """Derive a unique 96-bit (12-byte) AES-GCM nonce for a packet context.
    
    Guarantees nonce uniqueness per (session_id, direction, sequence_number, transfer_id)
    and enables deterministic reproducibility for packet retransmissions.
    """
    raw_str = f"ASTRA-NONCE:{session_id}:{direction}:{sequence_number}:{transfer_id}"
    digest = hashlib.sha256(raw_str.encode("utf-8")).digest()
    return digest[:12]  # Exactly 12 bytes (96 bits) for GCM


class PacketCipher:
    """Executes AES-GCM authenticated encryption and decryption for transmission packets."""

    @staticmethod
    def encrypt(
        key: bytes,
        plaintext: bytes,
        protocol_version: str,
        session_id: str,
        transfer_id: str,
        sequence_number: int,
        direction: str,
    ) -> EncryptedPacket:
        """Encrypt plaintext payload using AES-GCM with AAD metadata binding.
        
        Args:
            key: 32-byte directional session key.
            plaintext: Raw payload bytes to encrypt.
            protocol_version: Protocol version string.
            session_id: Active session ID.
            transfer_id: Logical transfer ID.
            sequence_number: Monotonic sequence number.
            direction: Direction string ("T1_TO_T2" or "T2_TO_T1").
            
        Returns:
            EncryptedPacket containing ciphertext, tag, nonce, and metadata.
        """
        if not isinstance(key, bytes) or len(key) != 32:
            raise ValueError("Directional key must be exactly 32 bytes.")
        if not isinstance(plaintext, bytes):
            raise TypeError("Plaintext payload must be bytes.")

        # 1. Derive 12-byte GCM nonce
        nonce_bytes = generate_gcm_nonce(session_id, direction, sequence_number, transfer_id)

        # 2. Compute canonical AAD bytes
        aad_bytes = compute_packet_aad(protocol_version, session_id, transfer_id, sequence_number, direction)

        # 3. AES-GCM Encrypt
        aesgcm = AESGCM(key)
        ciphertext_bytes = aesgcm.encrypt(nonce_bytes, plaintext, aad_bytes)

        return EncryptedPacket(
            protocol_version=protocol_version,
            session_id=session_id,
            transfer_id=transfer_id,
            sequence_number=sequence_number,
            direction=direction,
            nonce_hex=nonce_bytes.hex(),
            ciphertext_hex=ciphertext_bytes.hex(),
        )

    @staticmethod
    def decrypt(
        key: bytes,
        packet: EncryptedPacket,
    ) -> bytes:
        """Decrypt EncryptedPacket and verify AES-GCM authentication tag and AAD metadata.
        
        Args:
            key: 32-byte directional session key.
            packet: EncryptedPacket instance to decrypt.
            
        Returns:
            Decrypted plaintext bytes.
            
        Raises:
            InvalidPacketError: If authentication tag verification or AAD validation fails.
        """
        if not isinstance(key, bytes) or len(key) != 32:
            raise ValueError("Directional key must be exactly 32 bytes.")
        if not isinstance(packet, EncryptedPacket):
            raise TypeError("Expected EncryptedPacket instance.")

        # 1. Reconstruct expected AAD
        aad_bytes = packet.compute_aad()
        nonce_bytes = packet.get_nonce_bytes()
        ciphertext_bytes = packet.get_ciphertext_bytes()

        # 2. AES-GCM Decrypt & Tag Verification
        aesgcm = AESGCM(key)
        try:
            plaintext = aesgcm.decrypt(nonce_bytes, ciphertext_bytes, aad_bytes)
            return plaintext
        except (InvalidTag, ValueError) as e:
            raise InvalidPacketError(
                f"AES-GCM packet verification failed for transfer '{packet.transfer_id}' seq {packet.sequence_number}: {e}"
            ) from e
