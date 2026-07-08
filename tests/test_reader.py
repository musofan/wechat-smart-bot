"""Reader: own-vs-other bubble discrimination + latest_inbound. OCR mocked."""

from PIL import Image

from wechat_reader import WeixinReader
from wechat_vision import OcrLine, WeixinVision


def test_sender_discrimination_and_latest_inbound(monkeypatch):
    vis = WeixinVision()
    full = Image.new("RGB", (705, 999), (245, 245, 245))
    width = vis._crop(full, "messages").size[0]
    fake = [
        OcrLine("你好在吗", 0.9, cx=width * 0.20, cy=20),   # other (left)
        OcrLine("在的你说", 0.9, cx=width * 0.82, cy=60),   # me (right)
        OcrLine("想问下合作", 0.9, cx=width * 0.18, cy=100),  # other (left)
    ]
    monkeypatch.setattr(vis, "ocr", lambda img, min_score=0.5: fake)

    reader = WeixinReader(vis)
    msgs = reader.read_open_conversation(full)
    assert [m.sender for m in msgs] == ["other", "me", "other"]

    latest = reader.latest_inbound(msgs)
    assert latest is not None and latest.text == "想问下合作"


def test_timestamp_line_tagged_system(monkeypatch):
    vis = WeixinVision()
    full = Image.new("RGB", (705, 999), (245, 245, 245))
    width = vis._crop(full, "messages").size[0]
    fake = [
        OcrLine("昨天22:53", 0.9, cx=width * 0.5, cy=10),
        OcrLine("在吗", 0.9, cx=width * 0.2, cy=40),
    ]
    monkeypatch.setattr(vis, "ocr", lambda img, min_score=0.5: fake)
    msgs = WeixinReader(vis).read_open_conversation(full)
    assert msgs[0].kind == "system"
    assert msgs[1].sender == "other"
