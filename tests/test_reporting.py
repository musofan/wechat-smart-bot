"""RunReport accumulation + markdown output."""

from PIL import Image

from reporting import RunReport
from run_suggest import run_frames


class OkBot:
    def handle_open_conversation(self, img):
        from bot_core import Suggestion
        return Suggestion("c", "hi", "yo", True, "命中报价")


def test_report_counts_and_markdown(tmp_path):
    for i in range(2):
        Image.new("RGB", (705, 999), (245, 245, 245)).save(tmp_path / f"f{i}.png")
    rep = RunReport()
    run_frames(OkBot(), str(tmp_path), log=lambda *a, **k: None, report=rep)
    assert rep.scanned == 2 and rep.suggested == 2 and rep.needs_confirm == 2

    out = tmp_path / "report.md"
    rep.write(str(out))
    md = out.read_text(encoding="utf-8")
    assert "suggested: 2" in md and "needs_confirm: 2" in md
