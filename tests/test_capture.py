"""Tests for the capture engine. Geometry math runs offline; anything that needs
the real window is marked live."""

import pytest

from wechat_capture import Rect, WeixinCapture


def test_rect_dimensions():
    r = Rect(10, 20, 110, 220)
    assert r.width == 100
    assert r.height == 200


@pytest.mark.live
def test_find_and_capture_live():
    cap = WeixinCapture()
    assert cap.find_window(), "Weixin window not found (open it, not minimized)"
    img = cap.capture()
    assert img.size[0] > 300 and img.size[1] > 300
