"""Packetizer for payload fragmentation and PayloadReassembler for receiver delivery."""

from typing import Dict, List, Set, Tuple


class Packetizer:
    """Fragments byte payloads into fixed-size chunks with monotonic 1-based sequence numbers."""

    def __init__(self, packet_size: int = 4096):
        self.packet_size = max(1, int(packet_size))

    def packetize(self, payload: bytes, transfer_id: str) -> List[Tuple[int, bytes]]:
        """Fragment byte payload into sequence-numbered chunks.
        
        Args:
            payload: Raw bytes to fragment.
            transfer_id: Transfer identifier string.
            
        Returns:
            List of (sequence_number, chunk_bytes) tuples starting at seq=1.
        """
        if not isinstance(payload, bytes):
            raise TypeError("Payload must be bytes.")

        if len(payload) == 0:
            return [(1, b"")]

        chunks = []
        seq = 1
        for i in range(0, len(payload), self.packet_size):
            chunk = payload[i : i + self.packet_size]
            chunks.append((seq, chunk))
            seq += 1

        return chunks


class PayloadReassembler:
    """Reassembles valid decrypted packet chunks into transfer order while detecting duplicates."""

    def __init__(self):
        self._received_chunks: Dict[int, bytes] = {}
        self._seen_sequences: Set[int] = set()

    def accept_packet(self, sequence_number: int, payload: bytes) -> bool:
        """Accept a decrypted packet chunk.
        
        Args:
            sequence_number: Packet sequence number.
            payload: Decrypted chunk bytes.
            
        Returns:
            True if packet was accepted as new; False if it was a duplicate packet.
        """
        if not isinstance(payload, bytes):
            raise TypeError("Payload must be bytes.")

        if sequence_number in self._seen_sequences:
            # Duplicate sequence detected -> ignore double delivery
            return False

        self._seen_sequences.add(sequence_number)
        self._received_chunks[sequence_number] = payload
        return True

    def reassemble(self) -> bytes:
        """Reassemble all accepted chunks in ascending sequence order."""
        sorted_seqs = sorted(self._received_chunks.keys())
        return b"".join(self._received_chunks[seq] for seq in sorted_seqs)

    def clear(self) -> None:
        """Reset reassembler state."""
        self._received_chunks.clear()
        self._seen_sequences.clear()

    def __len__(self) -> int:
        return len(self._received_chunks)
