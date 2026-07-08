"""Tests for the vision reading layer — all offline (OCR mocked)."""

import numpy as np

from wechat_vision import LAYOUT, WeixinVision


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
