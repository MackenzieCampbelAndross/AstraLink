"""Secure transport module implementing AES-GCM, packetization, and Selective Repeat ARQ."""

from .ack import AckMessage
from .cipher import InvalidPacketError, PacketCipher, TransportError, generate_gcm_nonce
from .metrics import TransportMetrics
from .packet import EncryptedPacket, compute_packet_aad
from .packetizer import Packetizer, PayloadReassembler
from .receiver import SecureReceiver
from .selective_repeat import MaxRetriesExceededError, ReceiverWindow, SenderWindow
from .sender import SecureSender, UnauthorizedTransmissionError

__all__ = [
    "EncryptedPacket",
    "compute_packet_aad",
    "TransportError",
    "InvalidPacketError",
    "generate_gcm_nonce",
    "PacketCipher",
    "Packetizer",
    "PayloadReassembler",
    "UnauthorizedTransmissionError",
    "SecureSender",
    "SecureReceiver",
    "AckMessage",
    "SenderWindow",
    "ReceiverWindow",
    "MaxRetriesExceededError",
    "TransportMetrics",
]
