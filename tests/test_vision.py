"""Tests for the vision reading layer — all offline (OCR mocked)."""

import numpy as np

from wechat_vision import LAYOUT, WeixinVision, _is_timestamp, _tag_media_type


def test_layout_has_all_regions():
    for key in ("nav_rail", "chat_list", "chat_list_badges", "header", "messages", "input"):
        assert key in LAYOUT, f"missing region {key}"
        assert len(LAYOUT[key]) == 4


def test_red_mask_flags_badge_red():
    arr = np.zeros((8, 8, 3), dtype=np.uint8)
    arr[:, :] = (250, 70, 70)
    assert WeixinVision._red_mask(arr).all()


def test_red_mask_ignores_grey():
    arr = np.full((8, 8, 3), 200, dtype=np.uint8)
    assert not WeixinVision._red_mask(arr).any()


def test_detect_unread_rows_finds_badge(synth_full):
    ys = WeixinVision().detect_unread_rows(synth_full)
    assert any(200 < y < 240 for y in ys), f"expected a badge near y=220, got {ys}"


def test_read_chat_list_groups_by_row(synth_full, fake_ocr_lines, monkeypatch):
    vis = WeixinVision()
    monkeypatch.setattr(vis, "ocr", lambda img, min_score=0.4: fake_ocr_lines)
    convs = vis.read_chat_list(synth_full)
    assert len(convs) == 2
    assert convs[0].name == "蒋智华"
    assert "您视频卡住了" in convs[0].snippet
    assert convs[1].name == "HICOOL峰会"


def test_region_hash_is_stable_and_position_sensitive(synth_full):
    vis = WeixinVision()
    h1 = vis.region_hash(synth_full, "chat_list")
    h2 = vis.region_hash(synth_full, "chat_list")
    assert h1 == h2
    assert isinstance(h1, str) and len(h1) == 32


# ── T2: Timestamp cleanup ──────────────────────────────────────────

def test_is_timestamp_matches_time_only():
    assert _is_timestamp("14:33")
    assert _is_timestamp("00:00")
    assert _is_timestamp("  9:05 ")


def test_is_timestamp_matches_yesterday():
    assert _is_timestamp("昨天22:53")
    assert _is_timestamp("昨天0:01")


def test_is_timestamp_matches_weekday():
    assert _is_timestamp("星期一")
    assert _is_timestamp("周二")
    assert _is_timestamp("星期日")


def test_is_timestamp_rejects_normal_name():
    assert not _is_timestamp("张三")
    assert not _is_timestamp("HICOOL峰会")
    assert not _is_timestamp("NeXT SCENE")


def test_timestamp_removed_from_snippet(synth_full, monkeypatch):
    """OCR lines with timestamps should not appear in the name or snippet."""
    from wechat_vision import OcrLine

    # A row: name + timestamp + snippet
    lines = [
        OcrLine("李四", 0.9, cx=40, cy=20),
        OcrLine("14:33", 0.9, cx=60, cy=38),
        OcrLine("好的收到", 0.9, cx=60, cy=56),
    ]
    vis = WeixinVision()
    monkeypatch.setattr(vis, "ocr", lambda img, min_score=0.4: lines)
    monkeypatch.setattr(vis, "detect_unread_rows", lambda img: [])
    convs = vis.read_chat_list(synth_full)
    assert len(convs) == 1
    assert convs[0].name == "李四"
    assert "14:33" not in convs[0].snippet
    assert "好的收到" in convs[0].snippet


def test_weekday_not_polluting_name(synth_full, monkeypatch):
    """A weekday timestamp should not override a contact name."""
    from wechat_vision import OcrLine

    lines = [
        OcrLine("星期一", 0.9, cx=60, cy=20),
        OcrLine("张三", 0.9, cx=40, cy=40),
        OcrLine("在吗?", 0.9, cx=60, cy=58),
    ]
    vis = WeixinVision()
    monkeypatch.setattr(vis, "ocr", lambda img, min_score=0.4: lines)
    monkeypatch.setattr(vis, "detect_unread_rows", lambda img: [])
    convs = vis.read_chat_list(synth_full)
    assert len(convs) == 1
    assert convs[0].name == "张三"
    assert "星期一" not in convs[0].snippet


def test_media_type_tagging(synth_full, monkeypatch):
    """Snippets containing '[图片]' / '[语音]' / '[文件]' / '[链接]' are preserved."""
    from wechat_vision import OcrLine

    lines = [
        OcrLine("王五", 0.9, cx=40, cy=20),
        OcrLine("[图片]", 0.9, cx=60, cy=42),
    ]
    vis = WeixinVision()
    monkeypatch.setattr(vis, "ocr", lambda img, min_score=0.4: lines)
    monkeypatch.setattr(vis, "detect_unread_rows", lambda img: [])
    convs = vis.read_chat_list(synth_full)
    assert len(convs) == 1
    assert convs[0].name == "王五"
    assert "[图片]" in convs[0].snippet


def test_lone_snippet_not_name(synth_full, monkeypatch):
    """When only a snippet line appears (no preceding name),
    it should not become the contact name."""
    from wechat_vision import OcrLine

    lines = [
        OcrLine("在吗?", 0.9, cx=60, cy=20),
    ]
    vis = WeixinVision()
    monkeypatch.setattr(vis, "ocr", lambda img, min_score=0.4: lines)
    monkeypatch.setattr(vis, "detect_unread_rows", lambda img: [])
    convs = vis.read_chat_list(synth_full)
    assert len(convs) == 1
    assert convs[0].name == "(未知)"
    assert "在吗?" in convs[0].snippet


def test_layout_overridable():
    """LAYOUT can be overridden via constructor argument."""
    custom_layout = {"chat_list": (0.1, 0.1, 0.3, 0.8)}
    vis = WeixinVision(layout=custom_layout)
    assert vis.LAYOUT["chat_list"] == (0.1, 0.1, 0.3, 0.8)
    # Other keys should still have defaults
    assert vis.LAYOUT["header"] == LAYOUT["header"]


def test_tag_media_type_known():
    assert _tag_media_type("图片") == "[图片]"
    assert _tag_media_type("[图片]") == "[图片]"
    assert _tag_media_type("语音") == "[语音]"
    assert _tag_media_type("这是一条文件消息") == "[文件]"


def test_tag_media_type_unknown_preserves():
    assert _tag_media_type("你好") == "你好"
    assert _tag_media_type("收到") == "收到"