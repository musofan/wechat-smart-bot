"""Vision reading layer for Weixin 4.x: OCR + badge/change detection.

Reads what the background capture ([wechat_capture.WeixinCapture]) grabs — no
input, no sending. Uses RapidOCR (PP-OCR ONNX) for Chinese text and simple pixel
heuristics for unread badges and change detection.

Layout constants are relative (0..1) to the window and were calibrated against
Weixin 4.1.10.53. Adjust in LAYOUT if the window chrome changes.
"""

from __future__ import annotations

import hashlib
import re
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from PIL import Image

# Relative regions (x, y, w, h) in 0..1 of the full window, for Weixin 4.1.x.
# Calibrated on 705x999 Weixin 4.1.10.53: nav rail ~0..0.11, chat-list column
# ~0.11..0.44 (divider at x≈0.44), message pane ~0.44..0.98.
_DEFAULT_LAYOUT = {
    "nav_rail": (0.00, 0.08, 0.11, 0.90),      # left icon rail (chat icon + red badge)
    "chat_list_badges": (0.11, 0.085, 0.33, 0.90),  # full list column (for red-badge scan)
    "chat_list": (0.17, 0.085, 0.27, 0.90),    # list text only (skip avatar) → names+snippets
    "header": (0.455, 0.035, 0.34, 0.045),     # current conversation title (contact name)
    "messages": (0.455, 0.10, 0.52, 0.76),     # message bubbles area
    "input": (0.46, 0.885, 0.44, 0.08),        # text input box
}

# WeChat timestamp patterns (in-CN locale): time-only, yesterday+time, weekday+time
_TIMESTAMP_RE = re.compile(
    r"^(?:\d{1,2}:\d{2}|昨天\d{1,2}:\d{2}|星期一|星期二|星期三|星期四|星期五|星期六|星期日|"
    r"周一|周二|周三|周四|周五|周六|周日|上午|下午|刚刚|昨天|前天)\s*$"
)

# Media-type markers in chat snippets
_MEDIA_MARKERS = {
    "[图片]": "[图片]",
    "[语音]": "[语音]",
    "[文件]": "[文件]",
    "[链接]": "[链接]",
    "[动画表情]": "[动画表情]",
    "[视频]": "[视频]",
    "[位置]": "[位置]",
    "[名片]": "[名片]",
    "[红包]": "[红包]",
    "[转账]": "[转账]",
    "图片": "[图片]",
    "语音": "[语音]",
    "文件": "[文件]",
    "链接": "[链接]",
}

_UI_NOISE = (
    "按住", "语音输入", "输入文字", "发送", "Ctrl", "Win", "搜索",
    "微信电脑版", "折叠置顶聊天",
)


@dataclass
class OcrLine:
    text: str
    score: float
    # bounding box center in pixels relative to the CROPPED region
    cx: float
    cy: float


@dataclass
class Conversation:
    name: str
    snippet: str
    # y-center in FULL-window pixels (for later clicking)
    y_full: int
    has_unread: bool = False
    lines: list[str] = field(default_factory=list)


def _is_timestamp(text: str) -> bool:
    return bool(_TIMESTAMP_RE.match(text.strip()))


def _tag_media_type(text: str) -> str:
    """Replace known media substrings with bracketed tag form."""
    for marker, tag in _MEDIA_MARKERS.items():
        if marker in text:
            return tag
    return text


class WeixinVision:
    """Vision layer with overridable layout; pass `layout` to customise.

    Example:
        vis = WeixinVision(layout={"chat_list": (0.1, 0.1, 0.3, 0.8)})
    """

    def __init__(self, layout: Optional[dict] = None) -> None:
        base = deepcopy(_DEFAULT_LAYOUT)
        if layout:
            base.update(layout)
        self._layout = base
        self._ocr = None

    @property
    def LAYOUT(self) -> dict:
        return self._layout

    def _engine(self):
        if self._ocr is None:
            from rapidocr_onnxruntime import RapidOCR
            self._ocr = RapidOCR()
        return self._ocr

    # ---- OCR ----
    def ocr(self, img: Image.Image, min_score: float = 0.4) -> list[OcrLine]:
        arr = np.array(img.convert("RGB"))[:, :, ::-1]  # RGB -> BGR for cv2/RapidOCR
        result, _ = self._engine()(arr)
        lines: list[OcrLine] = []
        if not result:
            return lines
        for box, text, score in result:
            score = float(score)
            if score < min_score or not text or not text.strip():
                continue
            ys = [p[1] for p in box]
            xs = [p[0] for p in box]
            lines.append(OcrLine(text.strip(), score,
                                 cx=sum(xs) / 4.0, cy=sum(ys) / 4.0))
        return lines

    # ---- unread badge detection ----
    @staticmethod
    def _red_mask(arr: np.ndarray) -> np.ndarray:
        r, g, b = arr[:, :, 0].astype(int), arr[:, :, 1].astype(int), arr[:, :, 2].astype(int)
        # WeChat unread badge red ≈ (250, 80, 80)-ish; be tolerant.
        return (r > 180) & (g < 100) & (b < 100)

    def detect_unread_rows(self, full: Image.Image) -> list[int]:
        """Return FULL-window y-pixels of chat-list rows that show a red badge."""
        W, H = full.size
        x, y, w, h = self._layout["chat_list_badges"]
        crop = full.crop((int(W * x), int(H * y), int(W * (x + w)), int(H * (y + h))))
        arr = np.array(crop.convert("RGB"))
        mask = self._red_mask(arr)
        rows = np.where(mask.sum(axis=1) > 3)[0]  # rows with enough red pixels
        # cluster nearby rows into badges
        ys_full: list[int] = []
        if len(rows):
            start = prev = rows[0]
            for cur in rows[1:]:
                if cur - prev > 12:
                    ys_full.append(int(H * y) + (start + prev) // 2)
                    start = cur
                prev = cur
            ys_full.append(int(H * y) + (start + prev) // 2)
        return ys_full

    def has_nav_badge(self, full: Image.Image) -> bool:
        """True if the nav-rail chat icon shows a red unread badge."""
        W, H = full.size
        x, y, w, h = self._layout["nav_rail"]
        crop = full.crop((int(W * x), int(H * y), int(W * (x + w)), int(H * (y + h))))
        return int(self._red_mask(np.array(crop.convert("RGB"))).sum()) > 8

    # ---- change detection ----
    def region_hash(self, full: Image.Image, region_key: str) -> str:
        W, H = full.size
        x, y, w, h = self._layout[region_key]
        crop = full.crop((int(W * x), int(H * y), int(W * (x + w)), int(H * (y + h))))
        small = crop.resize((64, 64)).convert("L")
        return hashlib.md5(small.tobytes()).hexdigest()

    # ---- structured reads ----
    def read_chat_list(self, full: Image.Image) -> list[Conversation]:
        """OCR the chat list and group lines into conversations by y-position.

        Cleans timestamps from names and snippets, tags media types in snippets,
        and prevents a lone snippet (without a preceding name) from becoming the name.
        """
        W, H = full.size
        x, y, w, h = self._layout["chat_list"]
        crop_top = int(H * y)
        crop = full.crop((int(W * x), crop_top, int(W * (x + w)), int(H * (y + h))))
        lines = self.ocr(crop, min_score=0.4)
        lines.sort(key=lambda l: l.cy)

        unread_ys = self.detect_unread_rows(full)

        convs: list[Conversation] = []
        group: list[OcrLine] = []

        def flush(g: list[OcrLine]):
            if not g:
                return
            y_full = crop_top + int(sum(l.cy for l in g) / len(g))
            # Filter out timestamp-only lines
            non_ts = [l for l in g if not _is_timestamp(l.text)]
            if not non_ts:
                return  # skip groups that are all timestamps
            texts = [l.text for l in non_ts]

            # Detect media-type markers before grouping
            snippet_texts = texts[1:] if len(texts) > 1 else []
            tagged_snippets = [_tag_media_type(s) for s in snippet_texts]

            # Name: first non-timestamp line
            if len(non_ts) == 1 and not _is_timestamp(texts[0]):
                # Single line — ambiguous; it's likely a snippet, not a name
                name = "(未知)"
                snippet_str = _tag_media_type(texts[0])
            else:
                name = texts[0]
                if _is_timestamp(name) and len(non_ts) > 1:
                    name = non_ts[1].text if not _is_timestamp(non_ts[1].text) else texts[0]
                snippet_str = " ".join(tagged_snippets) if tagged_snippets else ""

            has_unread = any(abs(u - y_full) < 26 for u in unread_ys)
            convs.append(Conversation(
                name=name,
                snippet=snippet_str,
                y_full=y_full,
                has_unread=has_unread,
                lines=texts,
            ))

        for l in lines:
            if group and l.cy - group[-1].cy > 26:  # new row cluster
                flush(group)
                group = []
            group.append(l)
        flush(group)
        return convs

    def read_header(self, full: Image.Image) -> str:
        crop = self._crop(full, "header")
        lines = self.ocr(crop, min_score=0.5)
        return lines[0].text if lines else ""

    def read_recent_messages(self, full: Image.Image, n: int = 5) -> list[str]:
        crop = self._crop(full, "messages")
        lines = self.ocr(crop, min_score=0.5)
        out = [l.text for l in lines
               if len(l.text) > 1 and not any(k in l.text for k in _UI_NOISE)]
        return out[-n:]

    def _crop(self, full: Image.Image, key: str) -> Image.Image:
        W, H = full.size
        x, y, w, h = self._layout[key]
        return full.crop((int(W * x), int(H * y), int(W * (x + w)), int(H * (y + h))))


# Module-level alias for backward compatibility
LAYOUT = _DEFAULT_LAYOUT