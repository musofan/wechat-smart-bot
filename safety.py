"""Behavioral safety envelope for sending. Every gate here exists to keep the
account's automation footprint human-like and low-risk. can_send() must return
True before any real message goes out."""

from __future__ import annotations

import os
import time


class SafetyEnvelope:
    def __init__(self, clock=time.time, min_gap_s: float = 8.0, per_hour_cap: int = 40,
                 business_hours=(9, 22), stop_file: str = "data/STOP", hour_of=None):
        self.clock = clock
        self.min_gap_s = min_gap_s
        self.per_hour_cap = per_hour_cap
        self.business_hours = business_hours
        self.stop_file = stop_file
        self._hour_of = hour_of  # optional injected fn(ts)->hour, for testing
        self._sent: list[float] = []

    def _hour(self, ts: float) -> int:
        if self._hour_of:
            return self._hour_of(ts)
        import datetime
        return datetime.datetime.fromtimestamp(ts).hour

    def can_send(self) -> tuple[bool, str]:
        now = self.clock()
        if self.stop_file and os.path.exists(self.stop_file):
            return False, "kill-switch present (data/STOP)"
        lo, hi = self.business_hours
        h = self._hour(now)
        if not (lo <= h < hi):
            return False, f"outside business hours ({lo}:00-{hi}:00), now {h}:00"
        self._sent = [t for t in self._sent if now - t < 3600]
        if len(self._sent) >= self.per_hour_cap:
            return False, f"hourly cap reached ({self.per_hour_cap}/h)"
        if self._sent and (now - self._sent[-1]) < self.min_gap_s:
            return False, f"min gap not elapsed ({self.min_gap_s}s)"
        return True, "ok"

    def record_send(self):
        self._sent.append(self.clock())
