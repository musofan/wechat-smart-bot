"""Robustness: blank-frame detection + per-frame failure isolation."""

from PIL import Image

from bot_core import Suggestion
from run_suggest import run_frames
from wechat_capture import WeixinCapture


def test_is_blank_detects_black():
    assert WeixinCapture.is_blank(Image.new("RGB", (80, 80), (0, 0, 0))) is True
    assert WeixinCapture.is_blank(Image.new("RGB", (80, 80), (240, 240, 240))) is False


class FlakyBot:
    def __init__(self):
        self.calls = 0

    def handle_open_conversation(self, img):
        self.calls += 1
        if self.calls == 2:
            raise RuntimeError("boom")  # simulate one bad frame
        return Suggestion("c", "hi", "yo", False, "")


def test_run_frames_isolates_one_failure(tmp_path):
    for i in range(3):
        Image.new("RGB", (705, 999), (245, 245, 245)).save(tmp_path / f"f{i}.png")
    bot = FlakyBot()
    n = run_frames(bot, str(tmp_path), log=lambda *a, **k: None)
    assert bot.calls == 3   # all frames attempted despite the middle one failing
    assert n == 2           # two suggestions produced
