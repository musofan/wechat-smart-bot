"""Safety envelope for the action layer — gates that prevent unintended sends.

Every gate returns ``(can_send: bool, reason: str)`` via ``Safety.can_send()``.
All gates use an injected ``clock`` (default ``time.time``) for testability.
"""

from __future__ import annotations

import logging
import os
import time as _time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from config import Config

logger = logging.getLogger(__name__)

# Sentinel value: the kill-switch file path
_STOP_FILE = Path("data") / "STOP"


@dataclass
class Safety:
    """Composite safety gate aggregating all checks.

    Args:
        config: Application config (for business hours, min gap).
        clock: Use ``time.time`` (real) or a fake in tests.
        stop_file: Path to the kill-switch file. Default ``data/STOP``.
        min_gap_seconds: Minimum seconds between two consecutive sends.
        max_per_hour: Maximum sends allowed in any sliding 60-minute window.
    """

    config: Config
    clock: Callable[[], float] = field(default=lambda: _time.time())
    stop_file: Path = field(default_factory=lambda: _STOP_FILE)

    # Rate-limit state (mutable)
    _last_send_ts: float = field(default=0.0, repr=False)
    _send_timestamps: list[float] = field(default_factory=list, repr=False)

    def __post_init__(self):
        # Ensure _send_timestamps is a fresh list per instance
        if not hasattr(self, "_send_timestamps") or self._send_timestamps is None:
            self._send_timestamps = []

    def can_send(self) -> tuple[bool, str]:
        """Check all safety gates.

        Returns:
            (True, "") if all gates pass.
            (False, "reason...") on the first failing gate.
        """
        # 1. Kill-switch
        if self.stop_file.exists():
            return (False, "Kill-switch active: STOP file exists")

        # 2. Business hours
        ok, reason = self._check_business_hours()
        if not ok:
            return (ok, reason)

        # 3. Minimum gap
        ok, reason = self._check_min_gap()
        if not ok:
            return (ok, reason)

        # 4. Per-hour cap
        ok, reason = self._check_hourly_cap()
        if not ok:
            return (ok, reason)

        return (True, "")

    def record_send(self) -> None:
        """Record that a send occurred (updates rate-limit state).

        Call this after a successful send.
        """
        now = self.clock()
        self._last_send_ts = now
        self._send_timestamps.append(now)
        # Prune timestamps older than 1 hour to keep the list bounded
        cutoff = now - 3600
        self._send_timestamps = [t for t in self._send_timestamps if t >= cutoff]

    # ---- Internal gates ----

    def _check_business_hours(self) -> tuple[bool, str]:
        """Check if current time falls within business hours."""
        now = self.clock()
        local_now = _time.localtime(now)
        minutes = local_now.tm_hour * 60 + local_now.tm_min
        start, end = self.config.BUSINESS_HOURS
        # Handle overnight ranges (not expected here but be safe)
        if end <= start:
            end += 1440  # 24 h
        if start <= minutes < end or start <= minutes + 1440 < end:
            return (True, "")
        return (False, f"Outside business hours ({start // 60}:{start % 60:02d}-"
                       f"{end // 60}:{end % 60:02d})")

    def _check_min_gap(self) -> tuple[bool, str]:
        """Check the minimum gap between sends."""
        if self._last_send_ts == 0:
            return (True, "")
        elapsed = self.clock() - self._last_send_ts
        min_gap = self.config.SCAN_INTERVAL  # reuse scan interval as min gap
        if elapsed < min_gap:
            return (False, f"Rate-limited: {elapsed:.1f}s < {min_gap}s min gap")
        return (True, "")

    def _check_hourly_cap(self) -> tuple[bool, str]:
        """Check the per-hour send cap (default 50)."""
        now = self.clock()
        cutoff = now - 3600
        recent = [t for t in self._send_timestamps if t >= cutoff]
        cap = int(os.getenv("RATE_CAP_PER_HOUR", "50"))
        if len(recent) >= cap:
            return (False, f"Hourly cap reached: {len(recent)} >= {cap}")
        return (True, "")