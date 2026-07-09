"""Tests for safety.py — all gates verified with injected clock."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


from config import Config
from safety import Safety


def _config_with_hours(start_hour: int = 9, end_hour: int = 22) -> Config:
    """Create a Config with specific business hours and short intervals for testing."""
    old_bh = os.environ.pop("BUSINESS_HOURS", None)  # clear any env override
    cfg = Config()
    cfg.BUSINESS_HOURS = (start_hour * 60, end_hour * 60)
    cfg.SCAN_INTERVAL = 2  # short gap for tests
    return cfg


class _FakeClock:
    """Injected clock that returns a fixed timestamp."""

    def __init__(self, ts: float):
        self._ts = ts

    def __call__(self) -> float:
        return self._ts


class TestKillSwitch:
    """STOP file gate."""

    def test_stop_file_blocks(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            stop = Path(tmpdir) / "STOP"
            stop.touch()
            safety = Safety(config=_config_with_hours(), stop_file=stop)
            ok, reason = safety.can_send()
            assert not ok
            assert "STOP file" in reason

    def test_no_stop_file_allows(self):
        cfg = _config_with_hours()
        safety = Safety(config=cfg)
        # Need to be within business hours — freeze time at 12:00
        import time
        now = time.mktime(time.strptime("2026-07-09 12:00:00", "%Y-%m-%d %H:%M:%S"))
        safety.clock = _FakeClock(now)
        ok, reason = safety.can_send()
        assert ok, f"Expected ok, got: {reason}"


class TestBusinessHours:
    """Business-hours gate."""

    def test_within_hours(self):
        cfg = _config_with_hours(9, 22)
        # 12:00 is well within 09:00-22:00
        now = _fake_ts("12:00")
        safety = Safety(config=cfg, clock=_FakeClock(now))
        ok, reason = safety.can_send()
        assert ok, f"Expected ok, got: {reason}"

    def test_before_hours(self):
        cfg = _config_with_hours(9, 22)
        now = _fake_ts("08:30")
        safety = Safety(config=cfg, clock=_FakeClock(now))
        ok, reason = safety.can_send()
        assert not ok
        assert "business" in reason.lower()

    def test_after_hours(self):
        cfg = _config_with_hours(9, 22)
        now = _fake_ts("23:00")
        safety = Safety(config=cfg, clock=_FakeClock(now))
        ok, reason = safety.can_send()
        assert not ok
        assert "business" in reason.lower()

    def test_edge_start(self):
        cfg = _config_with_hours(9, 22)
        now = _fake_ts("09:00")
        safety = Safety(config=cfg, clock=_FakeClock(now))
        ok, reason = safety.can_send()
        assert ok, f"Expected ok at start, got: {reason}"

    def test_edge_end(self):
        cfg = _config_with_hours(9, 22)
        now = _fake_ts("21:59")
        safety = Safety(config=cfg, clock=_FakeClock(now))
        ok, reason = safety.can_send()
        assert ok, f"Expected ok before end, got: {reason}"

    def test_at_end_exclusive(self):
        cfg = _config_with_hours(9, 22)
        now = _fake_ts("22:00")
        safety = Safety(config=cfg, clock=_FakeClock(now))
        ok, reason = safety.can_send()
        assert not ok


class TestMinGap:
    """Minimum gap gate."""

    def test_first_send_allows(self):
        cfg = _config_with_hours()
        now = _fake_ts("12:00")
        safety = Safety(config=cfg, clock=_FakeClock(now))
        ok, reason = safety.can_send()
        assert ok

    def test_after_gap_allows(self):
        cfg = _config_with_hours()
        now = _fake_ts("12:00")
        clock = _FakeClock(now)
        safety = Safety(config=cfg, clock=clock)
        safety.record_send()
        # Advance clock past the min gap
        clock._ts = now + cfg.SCAN_INTERVAL + 1
        ok, reason = safety.can_send()
        assert ok, f"Expected ok after gap, got: {reason}"

    def test_too_soon_blocks(self):
        cfg = _config_with_hours()
        now = _fake_ts("12:00")
        clock = _FakeClock(now)
        safety = Safety(config=cfg, clock=clock)
        safety.record_send()
        # No time advance — should be blocked
        ok, reason = safety.can_send()
        assert not ok
        assert "rate-limited" in reason.lower()


class TestHourlyCap:
    """Per-hour cap gate."""

    def test_under_cap_allows(self):
        cfg = _config_with_hours()
        now = _fake_ts("12:00")
        clock = _FakeClock(now)
        safety = Safety(config=cfg, clock=clock)
        ok, reason = safety.can_send()
        assert ok

    def test_at_cap_blocks(self):
        cfg = _config_with_hours()
        now = _fake_ts("12:00")
        clock = _FakeClock(now)
        safety = Safety(config=cfg, clock=clock)
        # Record 50 sends (default cap) — advance time between each to avoid min-gap
        for i in range(50):
            clock._ts = now + i * (cfg.SCAN_INTERVAL + 1)
            safety.record_send()
        # Advance one more gap so min-gap passes
        clock._ts = now + 50 * (cfg.SCAN_INTERVAL + 1)
        ok, reason = safety.can_send()
        assert not ok
        assert "hourly cap" in reason.lower()

    def test_after_hour_resets(self):
        cfg = _config_with_hours()
        now = _fake_ts("12:00")
        clock = _FakeClock(now)
        safety = Safety(config=cfg, clock=clock)
        # Record 50 sends spaced out so min-gap doesn't fire
        for i in range(50):
            clock._ts = now + i * (cfg.SCAN_INTERVAL + 1)
            safety.record_send()
        # Advance 61 minutes — the sliding window should drop all old entries
        clock._ts = now + 3660
        ok, reason = safety.can_send()
        assert ok, f"Expected ok after hour reset, got: {reason}"

    def test_near_cap_allows(self):
        cfg = _config_with_hours()
        now = _fake_ts("12:00")
        clock = _FakeClock(now)
        safety = Safety(config=cfg, clock=clock)
        for i in range(49):
            clock._ts = now + i * (cfg.SCAN_INTERVAL + 1)
            safety.record_send()
        # Advance past min-gap before checking
        clock._ts = now + 49 * (cfg.SCAN_INTERVAL + 1)
        ok, reason = safety.can_send()
        assert ok, f"Expected ok at 49/50, got: {reason}"


class TestRecordSend:
    """Verify record_send updates internal state."""

    def test_updates_last_send(self):
        cfg = _config_with_hours()
        now = _fake_ts("12:00")
        clock = _FakeClock(now)
        safety = Safety(config=cfg, clock=clock)
        assert safety._last_send_ts == 0.0
        safety.record_send()
        assert safety._last_send_ts == now

    def test_adds_to_timestamps(self):
        cfg = _config_with_hours()
        now = _fake_ts("12:00")
        clock = _FakeClock(now)
        safety = Safety(config=cfg, clock=clock)
        safety.record_send()
        assert len(safety._send_timestamps) == 1
        assert safety._send_timestamps[0] == now


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _fake_ts(time_str: str, date_str: str = "2026-07-09") -> float:
    """Convert 'HH:MM' to a Unix timestamp in **local time** (any date)."""
    import time
    t = time.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    return time.mktime(t)
