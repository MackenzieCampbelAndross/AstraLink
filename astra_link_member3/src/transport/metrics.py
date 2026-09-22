"""Transport metrics tracking throughput, retransmissions, latency, and packet counts."""

import time
from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class TransportMetrics:
    """Tracks empirical transport execution metrics."""

    packets_sent: int = 0
    packets_received: int = 0
    packets_lost: int = 0
    packets_retransmitted: int = 0
    duplicate_packets: int = 0
    ack_count: int = 0
    start_time: float = field(default_factory=time.time)
    completion_time: float = 0.0
    total_bytes_transferred: int = 0

    def mark_started(self) -> None:
        self.start_time = time.time()

    def mark_completed(self) -> None:
        self.completion_time = time.time()

    @property
    def transfer_duration(self) -> float:
        end = self.completion_time if self.completion_time > 0 else time.time()
        return max(0.001, round(end - self.start_time, 4))

    @property
    def goodput_bps(self) -> float:
        duration = self.transfer_duration
        if duration <= 0:
            return 0.0
        return round((self.total_bytes_transferred * 8) / duration, 2)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "packets_sent": self.packets_sent,
            "packets_received": self.packets_received,
            "packets_lost": self.packets_lost,
            "packets_retransmitted": self.packets_retransmitted,
            "duplicate_packets": self.duplicate_packets,
            "ack_count": self.ack_count,
            "transfer_duration_sec": self.transfer_duration,
            "total_bytes_transferred": self.total_bytes_transferred,
            "goodput_bps": self.goodput_bps,
        }

    def __repr__(self) -> str:
        return (
            f"TransportMetrics(sent={self.packets_sent}, recv={self.packets_received}, "
            f"retrans={self.packets_retransmitted}, dups={self.duplicate_packets}, "
            f"duration={self.transfer_duration:.3f}s, goodput={self.goodput_bps} bps)"
        )
