"""Sliding window, SenderWindow, ReceiverWindow, and Selective Repeat ARQ logic."""

import time
from typing import Dict, List, Optional, Set, Tuple

from .ack import AckMessage
from .cipher import TransportError
from .packet import EncryptedPacket


class MaxRetriesExceededError(TransportError):
    """Raised when a packet exceeds the maximum configured retransmission retries."""
    pass


class SenderWindow:
    """Manages sender sliding window, in-flight packet tracking, and selective retransmissions."""

    def __init__(self, window_size: int = 32, max_retries: int = 5):
        self.window_size = max(1, int(window_size))
        self.max_retries = max(1, int(max_retries))

        self.base_sequence: int = 1
        self.next_sequence: int = 1
        self.in_flight: Dict[int, EncryptedPacket] = {}
        self.sent_timestamps: Dict[int, float] = {}
        self.retry_counts: Dict[int, int] = {}
        self.acknowledged: Set[int] = set()

    def can_send_next(self) -> bool:
        """Check if sliding window has remaining capacity."""
        return (self.next_sequence - self.base_sequence) < self.window_size

    def add_sent_packet(self, packet: EncryptedPacket, current_time: Optional[float] = None) -> None:
        """Track a sent packet in the sliding window."""
        seq = packet.sequence_number
        now = current_time if current_time is not None else time.time()

        self.in_flight[seq] = packet
        self.sent_timestamps[seq] = now
        if seq not in self.retry_counts:
            self.retry_counts[seq] = 0

        if seq >= self.next_sequence:
            self.next_sequence = seq + 1

    def process_ack(self, ack_msg: AckMessage) -> Tuple[int, List[int]]:
        """Process an incoming AckMessage, mark confirmed packets, and advance window base.
        
        Returns:
            Tuple of (new_base_sequence, newly_acknowledged_sequence_numbers)
        """
        newly_ack = []

        # 1. Process cumulative ACK (all sequences <= cumulative_ack are confirmed)
        for seq in range(self.base_sequence, ack_msg.cumulative_ack + 1):
            if seq not in self.acknowledged:
                self.acknowledged.add(seq)
                newly_ack.append(seq)

        # 2. Process selective ACK (SACK sequence list)
        for seq in ack_msg.selective_ack:
            if seq not in self.acknowledged:
                self.acknowledged.add(seq)
                newly_ack.append(seq)

        # 3. Advance base_sequence over contiguous acknowledged sequence numbers
        while self.base_sequence in self.acknowledged:
            self.base_sequence += 1

        # 4. Clean up confirmed packets from in-flight tracking
        for seq in newly_ack:
            self.in_flight.pop(seq, None)
            self.sent_timestamps.pop(seq, None)

        return self.base_sequence, newly_ack

    def get_timed_out_packets(
        self,
        current_time: Optional[float] = None,
        timeout_seconds: float = 0.100,
    ) -> List[EncryptedPacket]:
        """Identify unacknowledged packets that have timed out and require selective retransmission.
        
        Raises:
            MaxRetriesExceededError: If a packet exceeds max_retries.
        """
        now = current_time if current_time is not None else time.time()
        to_retransmit = []

        # Order by sequence number
        for seq in sorted(list(self.in_flight.keys())):
            if seq in self.acknowledged:
                continue

            sent_time = self.sent_timestamps.get(seq, now)
            if (now - sent_time) >= timeout_seconds:
                self.retry_counts[seq] = self.retry_counts.get(seq, 0) + 1
                if self.retry_counts[seq] > self.max_retries:
                    raise MaxRetriesExceededError(
                        f"Packet sequence {seq} for transfer '{self.in_flight[seq].transfer_id}' "
                        f"exceeded maximum retries ({self.max_retries})"
                    )

                # Reset timer for retransmitted packet
                self.sent_timestamps[seq] = now
                to_retransmit.append(self.in_flight[seq])

        return to_retransmit


class ReceiverWindow:
    """Manages receiver cumulative/selective ACK state, out-of-order buffering, and contiguous delivery."""

    def __init__(self):
        self.cumulative_ack: int = 0
        self.received_out_of_order: Dict[int, bytes] = {}
        self.received_sequences: Set[int] = set()

    def process_received_packet(
        self,
        packet: EncryptedPacket,
        plaintext: bytes,
    ) -> Tuple[AckMessage, List[Tuple[int, bytes]], bool]:
        """Process a valid decrypted packet, update SACK state, and return deliverable contiguous chunks.
        
        Returns:
            Tuple of (AckMessage, deliverable_chunks, is_duplicate: bool)
        """
        seq = packet.sequence_number
        is_duplicate = seq in self.received_sequences

        if is_duplicate:
            # Duplicate packet detected -> build ACK confirming existing state without double delivery
            sack_list = sorted([s for s in self.received_sequences if s > self.cumulative_ack])
            ack = AckMessage(
                protocol_version=packet.protocol_version,
                session_id=packet.session_id,
                transfer_id=packet.transfer_id,
                direction=packet.direction,
                cumulative_ack=self.cumulative_ack,
                selective_ack=sack_list,
            )
            return ack, [], True

        self.received_sequences.add(seq)
        deliverable_chunks: List[Tuple[int, bytes]] = []

        if seq == self.cumulative_ack + 1:
            # Contiguous arrival!
            self.cumulative_ack = seq
            deliverable_chunks.append((seq, plaintext))

            # Contiguous advancement loop over out-of-order buffer
            while (self.cumulative_ack + 1) in self.received_out_of_order:
                next_seq = self.cumulative_ack + 1
                chunk = self.received_out_of_order.pop(next_seq)
                self.cumulative_ack = next_seq
                deliverable_chunks.append((next_seq, chunk))
        else:
            # Out-of-order arrival! Buffer packet chunk
            self.received_out_of_order[seq] = plaintext

        # Compute SACK list (non-contiguous sequences above cumulative_ack)
        sack_list = sorted([s for s in self.received_sequences if s > self.cumulative_ack])

        ack = AckMessage(
            protocol_version=packet.protocol_version,
            session_id=packet.session_id,
            transfer_id=packet.transfer_id,
            direction=packet.direction,
            cumulative_ack=self.cumulative_ack,
            selective_ack=sack_list,
        )

        return ack, deliverable_chunks, False

    def clear(self) -> None:
        """Reset receiver window state."""
        self.cumulative_ack = 0
        self.received_out_of_order.clear()
        self.received_sequences.clear()
