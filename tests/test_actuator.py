"""Tests for wechat_actuator.py — DryRunActuator and LiveActuator."""

from __future__ import annotations

import pytest

from wechat_actuator import (
    DryRunActuator,
    _bezier_path,
    _log_normal_delay,
    new_actuator,
)


class TestDryRunActuator:
    """Verify the recording (dry-run) actuator records intended actions."""

    def test_records_open(self):
        act = DryRunActuator()
        act.open_conversation(220)
        assert act.actions == [("open", 220)]

    def test_records_send(self):
        act = DryRunActuator()
        act.send_text("您好，有什么可以帮您的？")
        assert act.actions == [("send", "您好，有什么可以帮您的？")]

    def test_records_focus(self):
        act = DryRunActuator()
        act.focus_input()
        assert act.actions == [("focus_input", None)]

    def test_sequence(self):
        """Simulate a full send sequence and verify all three actions."""
        act = DryRunActuator()
        act.open_conversation(100)
        act.focus_input()
        act.send_text("hello")
        assert act.actions == [
            ("open", 100),
            ("focus_input", None),
            ("send", "hello"),
        ]

    def test_empty_initial_state(self):
        act = DryRunActuator()
        assert act.actions == []


class TestNewActuatorFactory:
    """Factory dry_run flag behaviour."""

    def test_dry_run_returns_dry(self):
        act = new_actuator(dry_run=True)
        assert isinstance(act, DryRunActuator)

    def test_live_requires_rect(self):
        with pytest.raises(ValueError, match="window_rect"):
            new_actuator(dry_run=False)

    def test_live_not_executed_in_test(self):
        """LiveActuator is guarded behind @pytest.mark.live; test never runs it."""
        # We just verify the factory raises because we didn't pass window_rect
        with pytest.raises(ValueError, match="window_rect"):
            new_actuator(dry_run=False)


class TestHelpers:
    """Test internal helper functions (mock-safe, no real input)."""

    def test_log_normal_delay_positive(self):
        d = _log_normal_delay(100, 0.4)
        assert isinstance(d, float)
        assert d > 0

    def test_bezier_path_returns_coords(self):
        pts = _bezier_path(0, 0, 100, 200)
        assert len(pts) == 11  # steps=10 → 11 points
        # Start and end should match
        assert pts[0] == (0, 0)
        assert pts[-1] == (100, 200)


@pytest.mark.live
class TestLiveActuator:
    """Live actuator tests — guarded behind @pytest.mark.live.

    These tests are SKIPPED in CI / normal runs.  Run with:
        pytest --run-live tests/test_actuator.py
    """

    def test_import_live_actuator(self):
        """Just verify the class can be imported and constructed."""
        from wechat_actuator import LiveActuator
        act = LiveActuator(window_rect=(0, 0, 800, 600))
        assert act._rect == (0, 0, 800, 600)

    def test_screen_xy(self):
        from wechat_actuator import LiveActuator
        act = LiveActuator(window_rect=(100, 50, 500, 350))
        x, y = act._screen_xy(0.5, 0.5)
        # 100 + 0.5 * (500-100) = 300, 50 + 0.5 * (350-50) = 200
        assert (x, y) == (300, 200)

    def test_screen_xy_zero(self):
        from wechat_actuator import LiveActuator
        act = LiveActuator(window_rect=(10, 20, 110, 120))
        x, y = act._screen_xy(0, 0)
        assert (x, y) == (10, 20)