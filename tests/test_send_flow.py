"""Tests for SEND mode wiring (guarded behind DRY_RUN / Safety).

Every test verifies that:
- With ``DRY_RUN=True`` (default), the DryRun actuator only logs, never sends.
- Safety gates block sends when they should.
- The human-confirm queue parser works.
"""

from __future__ import annotations

import pytest

from bot_core import Bot
from config import Config
from reply_engine import ReplyEngine
from safety import Safety
from store import SuggestionStore
from tests.conftest import FakeLLM, RecordingActuator


@pytest.fixture
def bot_with_store():
    """A minimal Bot wired with DryRun actuator + in-memory store."""
    cfg = Config()
    cfg.MODE = "SEND"
    cfg.DRY_RUN = True
    cfg.SCAN_INTERVAL = 2

    llm = FakeLLM(reply="好的，我会尽快处理。")
    engine = ReplyEngine(llm=llm, knowledge_base="", persona="你是客服小助手")

    store = SuggestionStore()
    store.init()

    actuator = RecordingActuator()

    # We don't have capture/vision/reader for SEND (not needed — just use None)
    bot = Bot(
        capture=None,
        vision=None,
        reader=None,
        reply_engine=engine,
        store=store,
        actuator=actuator,
        config=cfg,
    )

    # Populate store with 3 suggestions
    store.save("张三", "请问价格多少？", draft_reply="我确认后回复您")
    store.save("李四", "我需要退款", draft_reply="退款问题已记录，稍后客服联系", needs_confirmation=True)
    store.save("王五", "明天有活动吗", draft_reply="有的，明天下午2点", needs_confirmation=False)

    return bot, store, actuator, cfg


class TestProcessPendingDryRun:
    """With DRY_RUN=True, process_pending must log but NOT send."""

    def test_process_pending_uses_dry_run_actuator(self, bot_with_store):
        bot, store, actuator, cfg = bot_with_store
        results = bot.process_pending(max_items=5)

        assert len(results) == 3, f"Expected 3 results, got {len(results)}"
        assert all(r["sent"] for r in results), "All should be 'sent' in dry-run mode"
        assert all(r["skipped_reason"] == "" for r in results)

        # Actuator must have been called, but with DRY actuator (RecordingActuator)
        assert len(actuator.actions) > 0, "Actuator should have been called"
        # Check we have open/focus/send sequences
        sends = [a for a in actuator.actions if a[0] == "send"]
        assert len(sends) == 3, f"Expected 3 send calls, got {len(sends)}"
        assert sends[0][1] == "我确认后回复您"
        assert sends[1][1] == "退款问题已记录，稍后客服联系"
        assert sends[2][1] == "有的，明天下午2点"

    def test_process_pending_no_pending(self, bot_with_store):
        """Empty store produces empty results."""
        bot, store, actuator, cfg = bot_with_store
        # Process all pending to clear them out
        bot.process_pending(max_items=100)
        actuator.actions.clear()

        results = bot.process_pending(max_items=5)
        assert results == []

    def test_process_pending_max_items(self, bot_with_store):
        """max_items limits how many suggestions are processed."""
        bot, store, actuator, cfg = bot_with_store
        results = bot.process_pending(max_items=2)
        assert len(results) == 2
        assert actuator.actions[0] == ("open", 0)
        assert actuator.actions[-1][0] == "send"


class TestSafetyIntegration:
    """Safety gate integration with process_pending."""

    def test_safety_blocks_outside_hours(self, bot_with_store):
        """Safety gate blocks sends outside business hours."""
        bot, store, actuator, cfg = bot_with_store
        cfg.DRY_RUN = False  # Enable live-safety checks

        # Freeze time at 03:00 (outside 09-22)
        import time
        early = time.mktime(time.strptime("2026-07-09 03:00:00", "%Y-%m-%d %H:%M:%S"))

        class _FakeClock:
            def __call__(self):
                return early

        cfg.SCAN_INTERVAL = 0
        safety = Safety(config=cfg, clock=_FakeClock())
        results = bot.process_pending(safety=safety, max_items=5)

        assert len(results) == 3
        assert all(not r["sent"] for r in results), "All should be blocked"
        assert any("business" in r["skipped_reason"].lower() for r in results)

    def test_safety_within_hours_allows(self, bot_with_store):
        """Safety gate allows sends within business hours."""
        bot, store, actuator, cfg = bot_with_store
        cfg.DRY_RUN = False

        import time
        noon = time.mktime(time.strptime("2026-07-09 12:00:00", "%Y-%m-%d %H:%M:%S"))

        class _FakeClock:
            def __call__(self):
                return noon

        cfg.SCAN_INTERVAL = 0
        safety = Safety(config=cfg, clock=_FakeClock())
        results = bot.process_pending(safety=safety, max_items=5)

        assert len(results) == 3
        assert all(r["sent"] for r in results)

    def test_dry_run_skips_safety(self, bot_with_store):
        """With DRY_RUN=True, safety gate is bypassed."""
        bot, store, actuator, cfg = bot_with_store
        cfg.DRY_RUN = True

        import time
        early = time.mktime(time.strptime("2026-07-09 03:00:00", "%Y-%m-%d %H:%M:%S"))

        class _FakeClock:
            def __call__(self):
                return early

        safety = Safety(config=cfg, clock=_FakeClock())
        results = bot.process_pending(safety=safety, max_items=5)

        assert len(results) == 3
        assert all(r["sent"] for r in results), "DRY_RUN should bypass safety"

    def test_update_status_on_send(self, bot_with_store):
        """After sending, suggestion status is updated to 'sent'."""
        bot, store, actuator, cfg = bot_with_store
        bot.process_pending(max_items=5)

        # Check store
        pending = store.list_pending()
        assert len(pending) == 0, "All suggestions should have been marked as sent"

        recent = store.list_recent()
        sent_count = sum(1 for r in recent if r["status"] == "sent")
        assert sent_count == 3, f"Expected 3 sent, got {sent_count}"


class TestHumanConfirmQueue:
    """Human-confirm queue parser."""

    def test_approve_next(self, bot_with_store):
        bot, store, actuator, cfg = bot_with_store
        result = bot.human_reply("1")
        assert result == ["approve_next"]

    def test_approve_custom(self, bot_with_store):
        bot, store, actuator, cfg = bot_with_store
        result = bot.human_reply("2 请稍等，我确认一下")
        assert result == ["approve_custom", "请稍等，我确认一下"]

    def test_skip_next(self, bot_with_store):
        bot, store, actuator, cfg = bot_with_store
        result = bot.human_reply("3")
        assert result == ["skip_next"]

    def test_list_pending(self, bot_with_store):
        bot, store, actuator, cfg = bot_with_store
        result = bot.human_reply("l")
        assert result[0] == "list"
        # Should contain contact names
        assert "张三" in result[1]

    def test_list_short(self, bot_with_store):
        bot, store, actuator, cfg = bot_with_store
        result = bot.human_reply("list")
        assert result[0] == "list"

    def test_no_pending(self):
        """list with empty store."""
        cfg = Config()
        store = SuggestionStore()
        store.init()
        bot = Bot(
            capture=None, vision=None, reader=None,
            reply_engine=ReplyEngine(llm=FakeLLM(), knowledge_base="", persona=""),
            store=store,
            actuator=RecordingActuator(),
            config=cfg,
        )
        result = bot.human_reply("l")
        assert result == ["no_pending"]

    def test_unknown_command(self, bot_with_store):
        bot, store, actuator, cfg = bot_with_store
        result = bot.human_reply("x")
        assert result == ["unknown", "x"]

    def test_approve_custom_no_text(self, bot_with_store):
        """'2' without text is unknown."""
        bot, store, actuator, cfg = bot_with_store
        result = bot.human_reply("2")
        assert result == ["unknown", "2"] or result[0] == "unknown"