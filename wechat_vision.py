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
from dataclasses import dataclass, field

import numpy as np
from PIL import Image

# Relative regions (x, y, w, h) in 0..1 of the full window, for Weixin 4.1.x.
# Calibrated on 705x999 Weixin 4.1.10.53: nav rail ~0..0.11, chat-list column
# ~0.11..0.44 (divider at x≈0.44), message pane ~0.44..0.98.
LAYOUT = {
    "nav_rail": (0.00, 0.08, 0.11, 0.90),      # left icon rail (chat icon + red badge)
    "chat_list_badges": (0.11, 0.085, 0.33, 0.90),  # full list column (for red-badge scan)
    "chat_list": (0.17, 0.085, 0.27, 0.90),    # list text only (skip avatar) → names+snippets
    "header": (0.455, 0.035, 0.34, 0.045),     # current conversation title (contact name)
    "messages": (0.455, 0.10, 0.52, 0.76),     # message bubbles area
    "input": (0.46, 0.885, 0.44, 0.08),        # text input box
}

_UI_NOISE = (
    "按住", "语音输入", "输入文字", "发送", "Ctrl", "Win", "搜索",
    "微信电脑版", "折叠置顶聊天",
)

# A chat-list row's time column, e.g. "14:33", "昨天22:53", "星期一", "昨天", "2025/1/1".
_TS_RE = re.compile(
    r"^(?:昨天|前天|上午|下午|凌晨|早上|中午|晚上)?\s*\d{1,2}:\d{2}$"
    r"|^(?:昨天|前天|星期[一二三四五六日天]|周[一二三四五六日天])$"
    r"|^\d{2,4}[-/]\d{1,2}[-/]\d{1,2}$"
)
# Media/snippet placeholders → a normalized kind.
_MEDIA = {
    "[图片]": "image", "[视频]": "video", "[语音]": "voice", "[文件]": "file",
    "[链接]": "link", "[位置]": "location", "[动画表情]": "sticker", "[表情]": "sticker",
    "[名片]": "card", "[转账]": "transfer", "[红包]": "redpacket",
}


def parse_list_row(texts: list[str]) -> tuple[str, str, str, str]:
    """Split a chat-list row's OCR lines into (name, timestamp, snippet, kind).

    The timestamp column is pulled out wherever it landed; the first remaining
    line is the contact/group name and the rest is the message preview. A leading
    unread-count marker like ``[3条]`` is stripped from the preview.
    """
    ts = ""
    kept: list[str] = []
    for t in texts:
        s = t.strip()
        if not s:
            continue
        if _TS_RE.match(s):
            ts = s
        else:
            kept.append(s)
    name = kept[0] if kept else ""
    snippet = " ".join(kept[1:]) if len(kept) > 1 else ""
    snippet = re.sub(r"^\[\d+条\]", "", snippet).strip()
    joined = " ".join(texts)
    kind = "text"
    for tag, k in _MEDIA.items():
        if tag in joined:
            kind = k
            break
    return name, ts, snippet, kind


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
    timestamp: str = ""
    snippet_kind: str = "text"  # text|image|voice|file|link|...
    lines: list[str] = field(default_factory=list)


class WeixinVision:
    def __init__(self, layout: dict | None = None) -> None:
        self._ocr = None
        # per-instance layout override (falls back to module defaults)
        self.layout = dict(LAYOUT)
        if layout:
            self.layout.update(layout)

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
        x, y, w, h = self.layout["chat_list_badges"]
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
        x, y, w, h = self.layout["nav_rail"]
        crop = full.crop((int(W * x), int(H * y), int(W * (x + w)), int(H * (y + h))))
        return int(self._red_mask(np.array(crop.convert("RGB"))).sum()) > 8

    # ---- change detection ----
    @staticmethod
    def region_hash(full: Image.Image, region_key: str) -> str:
        W, H = full.size
        x, y, w, h = LAYOUT[region_key]
        crop = full.crop((int(W * x), int(H * y), int(W * (x + w)), int(H * (y + h))))
        small = crop.resize((64, 64)).convert("L")
        return hashlib.md5(small.tobytes()).hexdigest()

    # ---- structured reads ----
    def read_chat_list(self, full: Image.Image) -> list[Conversation]:
        """OCR the chat list and group lines into conversations by y-position."""
        W, H = full.size
        x, y, w, h = self.layout["chat_list"]
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
            texts = [l.text for l in g]
            name, ts, snippet, kind = parse_list_row(texts)
            has_unread = any(abs(u - y_full) < 26 for u in unread_ys)
            convs.append(Conversation(
                name=name, snippet=snippet, y_full=y_full, has_unread=has_unread,
                timestamp=ts, snippet_kind=kind, lines=texts,
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
        x, y, w, h = self.layout[key]
        return full.crop((int(W * x), int(H * y), int(W * (x + w)), int(H * (y + h))))
