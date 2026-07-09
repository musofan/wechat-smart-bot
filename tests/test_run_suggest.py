"""run_suggest.py entrypoint — tests for dry-run components and loop logic."""

from __future__ import annotations

import tempfile
from pathlib import Path

from PIL import Image

from bot_core import Bot
from wechat_reader import Sender
from wechat_vision import Conversation


# ---- Test _DryRunActuator ----

class TestDryRunActuator:
    def test_logs_actions(self):
        from run_suggest import _DryRunActuator
        act = _DryRunActuator()
        assert act.actions == []
        act.open_conversation(220)
        act.send_text("hello")
        act.focus_input()
        assert len(act.actions) == 3
        assert act.actions[0] == ("open", 220)
        assert act.actions[1][0] == "send"
        assert act.actions[2] == ("focus_input", None)


# ---- Test _StubLLM ----

class TestStubLLM:
    def test_canned_reply(self):
        from run_suggest import _StubLLM
        llm = _StubLLM(reply="好的")
        assert llm.generate_reply([], "你好") == "好的"
        assert llm.classify_message("投诉") == {
            "needs_confirmation": False,
            "reason": "",
        }


# ---- Test build_bot returns correct types ----

def test_build_bot_default():
    from run_suggest import build_bot
    bot = build_bot(db_path=":memory:")
    assert isinstance(bot, Bot)
    # The store should be initialised and empty
    assert bot._store.list_recent() == []


# ---- Test run_loop with fake frames (no capture needed) ----

def _make_test_frame(text: str = "test", size=(705, 999)) -> Path:
    """Create a temporary PNG frame with optional text label (written as metadata)."""
    import numpy as np
    arr = np.full((999, 705, 3), 255, dtype=np.uint8)
    img = Image.fromarray(arr)
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    img.save(tmp.name)
    return Path(tmp.name)


def test_run_loop_frames_once():
    """run_loop with --frames and --once should execute one tick and exit."""
    import tempfile
    from run_suggest import build_bot, run_loop

    bot = build_bot()
    # Override the vision with a fake that returns a synthetic conversation
    class _FakeVision:
        def read_chat_list(self, full):
            return [Conversation(name="张三", snippet="你好", y_full=220, has_unread=True)]

        def detect_unread_rows(self, full):
            return [220]

    class _FakeReader:
        def latest_inbound(self, full):
            from wechat_reader import Message
            return Message(sender=Sender.OTHER, text="在吗？")

        @property
        def vision(self):
            return _FakeVision()

    bot._vision = _FakeVision()
    bot._reader = _FakeReader()

    # Create a temp directory with one frame
    with tempfile.TemporaryDirectory() as tmpdir:
        frame_path = _make_test_frame()
        # Copy frame into temp dir
        import shutil
        dst = Path(tmpdir) / "frame000.png"
        shutil.copy(str(frame_path), str(dst))
        frame_path.unlink()  # cleanup original

        run_loop(bot, interval=1, once=True, frames_dir=tmpdir)

    # Bot should have processed the frame and stored a suggestion
    stored = bot._store.list_recent()
    assert len(stored) == 1
    assert stored[0]["contact"] == "张三"
    assert stored[0]["incoming"] == "在吗？"