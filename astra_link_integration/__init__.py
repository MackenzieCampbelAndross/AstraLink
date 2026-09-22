"""Astra Link Integration Package.

Provides integration adapters and pipelines bridging Member 2 (Tracking & Vision)
with Member 3 (Security & Trust Layer).
"""

import sys
from pathlib import Path

# Ensure Member 2 and Member 3 source paths are in sys.path
_repo_root = Path(__file__).resolve().parent.parent
_m2_src = _repo_root / "astra-link-member2" / "src"
_m3_root = _repo_root / "astra_link_member3"

if _m2_src.exists() and str(_m2_src) not in sys.path:
    sys.path.insert(0, str(_m2_src))
if _m3_root.exists() and str(_m3_root) not in sys.path:
    sys.path.insert(0, str(_m3_root))

from .adapter import TrackingAdapter
from .pipeline import IntegratedTrackingSecurityPipeline

__all__ = [
    "TrackingAdapter",
    "IntegratedTrackingSecurityPipeline",
]
