"""Tests for robustness utilities — blank-frame detection, retry, isolation."""

from __future__ import annotations

import numpy as np
from PIL import Image

from robustness import is_blank_frame, capture_with_retry, ensure_window


class FakeCapture:
    """Minimal capture mock for testing retry logic."""

    def __init__(self, images, fail_indices=None):
        self.images = images  # list of (Image | callable-returning-Image | exc)
        self.fail_indices = set(fail_indices or [])
        self.call_count = 0

    def __call__(self):
        idx = self.call_count
        self.call_count += 1
        if idx in self.fail_indices:
            raise RuntimeError(f"capture fail #{idx}")
        val = self.images[idx] if idx < len(self.images) else self.images[-1]
        return val() if callable(val) else val


def _blank_black():
    return Image.new("RGB", (100, 50), (0, 0, 0))


def _blank_white():
    return Image.new("RGB", (100, 50), (255, 255, 255))


def _normal_img():
    arr = np.random.randint(0, 255, (100, 50, 3), dtype=np.uint8)
    return Image.fromarray(arr, "RGB")


class TestIsBlankFrame:
    """is_blank_frame edge cases."""

    def test_normal_image_not_blank(self):
        assert not is_blank_frame(_normal_img())

    def test_all_black_is_blank(self):
        assert is_blank_frame(_blank_black())

    def test_all_white_is_blank(self):
        assert is_blank_frame(_blank_white())

    def test_solid_color_is_blank(self):
        solid = Image.new("RGB", (100, 50), (128, 128, 128))
        assert is_blank_frame(solid)

    def test_none_is_blank(self):
        assert is_blank_frame(None)

    def test_tiny_image_is_blank(self):
        tiny = Image.new("RGB", (1, 1), (100, 100, 100))
        assert is_blank_frame(tiny)

    def test_near_black_is_blank(self):
        """Very dark low-variance image should be detected as blank."""
        arr = np.full((100, 50, 3), 2, dtype=np.uint8) + np.random.randint(0, 2, (100, 50, 3), dtype=np.uint8)
        dark = Image.fromarray(arr, "RGB")
        assert is_blank_frame(dark)

    def test_near_white_is_blank(self):
        arr = np.full((100, 50, 3), 250, dtype=np.uint8) + np.random.randint(0, 3, (100, 50, 3), dtype=np.uint8)
        light = Image.fromarray(arr, "RGB")
        assert is_blank_frame(light)


class TestCaptureWithRetry:
    """capture_with_retry retry strategies."""

    def test_first_attempt_succeeds(self):
        cap = FakeCapture([_normal_img()])
        img, err = capture_with_retry(cap)
        assert img is not None
        assert err is None

    def test_blank_retry_then_succeeds(self):
        cap = FakeCapture([_blank_black(), _normal_img()])
        img, err = capture_with_retry(cap)
        assert img is not None
        assert err is None
        assert cap.call_count == 2

    def test_all_blank_fails(self):
        cap = FakeCapture([_blank_black(), _blank_white(), _blank_black()])
        img, err = capture_with_retry(cap)
        assert img is None
        assert err is not None
        assert "blank" in err.lower()

    def test_exception_then_succeeds(self):
        cap = FakeCapture([_normal_img()], fail_indices={0})
        img, err = capture_with_retry(cap, max_retries=2)
        assert img is not None
        assert err is None
        assert cap.call_count == 2

    def test_all_exceptions_fails(self):
        cap = FakeCapture([_normal_img()], fail_indices={0, 1, 2})
        img, err = capture_with_retry(cap, max_retries=2)
        assert img is None
        assert err is not None


class FakeWindowCapture:
    """Mock capture object for ensure_window tests."""

    def __init__(self, hwnd=12345, minimized=False, restore_ok=True):
        self._hwnd = hwnd
        self._minimized = minimized
        self._restore_ok = restore_ok
        self.restore_called = False

    def ensure_window(self):
        if self._hwnd is None:
            raise RuntimeError("Window not found")
        return self._hwnd

    def is_minimized(self):
        return self._minimized

    def capture(self, restore_if_minimized=True):
        self.restore_called = True
        if not self._restore_ok:
            raise RuntimeError("Cannot restore")


class TestEnsureWindow:
    """ensure_window window availability checks."""

    def test_window_ok(self):
        cap = FakeWindowCapture()
        assert ensure_window(cap) is None

    def test_window_minimized_restores(self):
        cap = FakeWindowCapture(minimized=True)
        err = ensure_window(cap)
        assert err is None
        assert cap.restore_called

    def test_window_minimized_fail(self):
        cap = FakeWindowCapture(minimized=True, restore_ok=False)
        err = ensure_window(cap)
        assert err is not None
        assert "cannot be restored" in err.lower()

    def test_window_not_found(self):
        cap = FakeWindowCapture(hwnd=None)
        err = ensure_window(cap)
        assert err is not None
        assert "not found" in err.lower()


class TestExceptionIsolation:
    """Bot tick() exception isolation — one bad candidate doesn't crash the loop."""

    def test_empty_candidates_returns_empty(self):
        """No unread conversations returns empty results gracefully."""
        from bot_core import Bot
        from config import Config
        from reply_engine import ReplyEngine
        from store import SuggestionStore
        from tests.conftest import FakeLLM, RecordingActuator

        cfg = Config()
        cfg.MODE = "SUGGEST"
        cfg.DRY_RUN = True

        llm = FakeLLM(reply="好的，我确认一下。")
        engine = ReplyEngine(llm=llm, knowledge_base="", persona="你是客服小助手")

        store = SuggestionStore()
        store.init()

        actuator = RecordingActuator()

        from unittest.mock import MagicMock
        mock_vision = MagicMock()
        mock_vision.read_chat_list.return_value = []
        mock_vision.detect_unread_rows.return_value = set()

        bot = Bot(
            capture=None, vision=mock_vision, reader=None,
            reply_engine=engine,
            store=store,
            actuator=actuator,
            config=cfg,
        )

        results = bot.tick(full_img=_normal_img())
        assert results == [], "No candidates -> empty results"

    def test_is_blank_frame_imported(self):
        """Module imports cleanly."""
        assert callable(is_blank_frame)