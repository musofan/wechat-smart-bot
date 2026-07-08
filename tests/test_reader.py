"""Tests for ConversationReader — uses synthetic bubble images + mocked OCR."""

import numpy as np
from PIL import Image

from wechat_reader import (
    ConversationReader,
    Message,
    Sender,
    _infer_kind,
    _is_timestamp_or_system,
)
from wechat_vision import LAYOUT, OcrLine, WeixinVision


# ── Unit tests ─────────────────────────────────────────────────────


def test_sender_enum_values():
    assert Sender.ME.value == "me"
    assert Sender.OTHER.value == "other"
    assert Sender.SYSTEM.value == "system"


def test_message_dataclass():
    m = Message(sender=Sender.OTHER, text="你好", kind="text")
    assert m.sender == Sender.OTHER
    assert m.text == "你好"
    assert m.kind == "text"


def test_infer_kind_text():
    assert _infer_kind("你好") == "text"


def test_infer_kind_image():
    assert _infer_kind("[图片]") == "图片"
    assert _infer_kind("[语音]") == "语音"


def test_is_timestamp_or_system_detects_time():
    assert _is_timestamp_or_system("14:33")
    assert _is_timestamp_or_system("上午 11:20")
    assert not _is_timestamp_or_system("你好今天天气不错")
    assert _is_timestamp_or_system("刚刚")


# ── Reader integration tests ───────────────────────────────────────


def test_read_open_conversation_discerns_sender(monkeypatch):
    """Right-aligned bubbles → ME, left-aligned → OTHER."""
    W, H = 705, 999
    arr = np.full((H, W, 3), 245, dtype=np.uint8)
    img = Image.fromarray(arr)
    mx, my, mw, mh = LAYOUT["messages"]
    crop_w = int(W * mw)

    mid = crop_w / 2.0
    lines = [
        OcrLine("在吗?", 0.9, cx=mid - 60, cy=120),   # left of mid → OTHER
        OcrLine("来了来了", 0.9, cx=mid + 60, cy=180),  # right of mid → ME
    ]
    vis = WeixinVision()
    monkeypatch.setattr(vis, "ocr", lambda img, min_score=0.5: lines)
    reader = ConversationReader(vision=vis)
    msgs = reader.read_open_conversation(img)

    assert len(msgs) == 2
    assert msgs[0].sender == Sender.OTHER
    assert msgs[0].text == "在吗?"
    assert msgs[1].sender == Sender.ME
    assert msgs[1].text == "来了来了"


def test_latest_inbound_returns_last_other(monkeypatch):
    W, H = 705, 999
    arr = np.full((H, W, 3), 245, dtype=np.uint8)
    img = Image.fromarray(arr)
    mx, my, mw, mh = LAYOUT["messages"]
    crop_w = int(W * mw)
    mid = crop_w / 2.0

    lines = [
        OcrLine("在吗?", 0.9, cx=mid - 60, cy=120),
        OcrLine("来了来了", 0.9, cx=mid + 60, cy=180),
        OcrLine("明天有空吗?", 0.9, cx=mid - 60, cy=240),
    ]
    vis = WeixinVision()
    monkeypatch.setattr(vis, "ocr", lambda img, min_score=0.5: lines)
    reader = ConversationReader(vision=vis)
    latest = reader.latest_inbound(img)
    assert latest is not None
    assert latest.sender == Sender.OTHER
    assert latest.text == "明天有空吗?"


def test_latest_inbound_returns_none_when_no_other(monkeypatch):
    W, H = 705, 999
    arr = np.full((H, W, 3), 245, dtype=np.uint8)
    img = Image.fromarray(arr)
    mx, my, mw, mh = LAYOUT["messages"]
    crop_w = int(W * mw)
    mid = crop_w / 2.0

    lines = [
        OcrLine("好的", 0.9, cx=mid + 60, cy=120),
    ]
    vis = WeixinVision()
    monkeypatch.setattr(vis, "ocr", lambda img, min_score=0.5: lines)
    reader = ConversationReader(vision=vis)
    assert reader.latest_inbound(img) is None


def test_timestamp_rows_are_dropped(monkeypatch):
    W, H = 705, 999
    arr = np.full((H, W, 3), 245, dtype=np.uint8)
    img = Image.fromarray(arr)
    mx, my, mw, mh = LAYOUT["messages"]
    crop_w = int(W * mw)
    mid = crop_w / 2.0

    lines = [
        OcrLine("14:33", 0.9, cx=mid - 60, cy=100),
        OcrLine("在吗?", 0.9, cx=mid - 60, cy=130),
        OcrLine("上午", 0.9, cx=mid - 60, cy=200),
    ]
    vis = WeixinVision()
    monkeypatch.setattr(vis, "ocr", lambda img, min_score=0.5: lines)
    reader = ConversationReader(vision=vis)
    msgs = reader.read_open_conversation(img)
    assert len(msgs) == 1
    assert msgs[0].text == "在吗?"
    assert msgs[0].sender == Sender.OTHER


def test_reader_inherits_default_vision():
    reader = ConversationReader()
    assert isinstance(reader.vision, WeixinVision)


def test_midpoint_divides_sender(monkeypatch):
    W, H = 400, 600
    arr = np.full((H, W, 3), 245, dtype=np.uint8)
    img = Image.fromarray(arr)
    mx, my, mw, mh = LAYOUT["messages"]
    crop_w = int(W * mw)
    mid = crop_w / 2.0

    lines = [
        OcrLine("左边", 0.9, cx=mid - 10, cy=150),
        OcrLine("右边", 0.9, cx=mid + 10, cy=200),
    ]
    vis = WeixinVision()
    monkeypatch.setattr(vis, "ocr", lambda img, min_score=0.5: lines)
    reader = ConversationReader(vision=vis)
    msgs = reader.read_open_conversation(img)
    assert len(msgs) == 2
    assert msgs[0].sender == Sender.OTHER
    assert msgs[1].sender == Sender.ME


def test_bubble_grouping_merges_lines(monkeypatch):
    """Consecutive lines close in y are grouped into one message."""
    W, H = 400, 600
    arr = np.full((H, W, 3), 245, dtype=np.uint8)
    img = Image.fromarray(arr)
    mx, my, mw, mh = LAYOUT["messages"]
    crop_w = int(W * mw)
    mid = crop_w / 2.0

    lines = [
        OcrLine("第一行", 0.9, cx=mid - 60, cy=100),
        OcrLine("第二行", 0.9, cx=mid - 60, cy=115),  # close → same bubble
        OcrLine("第三行", 0.9, cx=mid + 60, cy=200),
    ]
    vis = WeixinVision()
    monkeypatch.setattr(vis, "ocr", lambda img, min_score=0.5: lines)
    reader = ConversationReader(vision=vis)
    msgs = reader.read_open_conversation(img)
    assert len(msgs) == 2
    assert msgs[0].text == "第一行 第二行"