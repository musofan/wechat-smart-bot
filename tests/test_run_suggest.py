"""run_suggest.run_frames drives a bot over saved frames — offline, no window."""

from PIL import Image

from bot_core import Suggestion
from run_suggest import run_frames


class FakeBot:
    def __init__(self):
        self.calls = 0

    def handle_open_conversation(self, img):
        self.calls += 1
        return Suggestion("蒋智华", "hi", "你好", False, "")


def test_run_frames_processes_each_png(tmp_path):
    for i in range(3):
        Image.new("RGB", (705, 999), (245, 245, 245)).save(tmp_path / f"frame{i}.png")
    bot = FakeBot()
    n = run_frames(bot, str(tmp_path), log=lambda *a, **k: None)
    assert n == 3 and bot.calls == 3


def test_run_frames_empty_dir(tmp_path):
    assert run_frames(FakeBot(), str(tmp_path), log=lambda *a, **k: None) == 0
