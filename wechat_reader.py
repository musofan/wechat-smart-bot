"""Reader layer: extract structured Messages from the open conversation area.

Uses the vision module's OCR + header reading, then assigns sender role by
bubble position/colour.  Only works on the *open* conversation's message region.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from PIL import Image

from wechat_vision import WeixinVision

_UI_NOISE_TEXT = frozenset({
    "按住", "语音输入", "输入文字", "发送", "Ctrl", "Win", "搜索",
})
_TIMESTAMP_MARKERS = frozenset({
    "上午", "下午", "昨天", "前天", "刚刚",
})


class Sender(Enum):
    ME = "me"
    OTHER = "other"
    SYSTEM = "system"


@dataclass
class Message:
    sender: Sender
    text: str
    kind: str = "text"      # text | image | voice | file | link | system
    raw: str = ""           # original line before any cleanup


def _infer_kind(text: str) -> str:
    t = text.strip()
    if t in ("[图片]", "[语音]", "[文件]", "[链接]", "[动画表情]", "[视频]",
             "[位置]", "[名片]", "[红包]", "[转账]",
             "[Sticker]", "[Photo]", "[Voice]", "[File]", "[Link]"):
        return t.strip("[]").lower()
    return "text"


def _is_timestamp_or_system(text: str) -> bool:
    """Heuristic: short text matching common timestamp/system patterns."""
    t = text.strip()
    if not t:
        return True
    if any(t.startswith(m) for m in _TIMESTAMP_MARKERS):
        return True
    if t in _UI_NOISE_TEXT:
        return True
    # Time patterns: HH:MM, HH:MM:SS
    if len(t) <= 8 and ":" in t:
        parts = t.split(":")
        if len(parts) <= 3 and all(p.isdigit() for p in parts if p):
            return True
    return False


class ConversationReader:
    """Reads the open conversation area of a full WeChat screenshot.

    Args:
        vision: WeixinVision instance (or anything with read_header + ocr).
    """

    def __init__(self, vision: Optional[WeixinVision] = None) -> None:
        self._vision = vision or WeixinVision()

    @property
    def vision(self) -> WeixinVision:
        return self._vision

    def read_header(self, full: Image.Image) -> str:
        """Return the contact name from the top header area."""
        return self._vision.read_header(full)

    def read_open_conversation(self, full: Image.Image) -> list[Message]:
        """OCR the **messages** region and return structured Messages.

        Sender discrimination:
        - Lines that are right-aligned (high x centroid) → Sender.ME
        - Lines that are left-aligned (low x centroid) → Sender.OTHER
        - System messages / timestamps → Sender.SYSTEM (dropped by default)
        """
        W, H = full.size
        mx, my, mw, mh = self._vision.LAYOUT["messages"]
        left = int(W * mx)
        top = int(H * my)
        right = int(W * (mx + mw))
        bottom = int(H * (my + mh))

        crop = full.crop((left, top, right, bottom))
        lines = self._vision.ocr(crop, min_score=0.5)
        lines.sort(key=lambda l: l.cy)

        # Midpoint x in the cropped region — lines to the right are "me", left are "other"
        mid_x = (right - left) / 2.0

        # The first bubble in a WeChat message area is at y offset ~some px; we
        # group consecutive lines by proximity into bubbles.
        messages: list[Message] = []
        bubble_group: list = []  # lines in current bubble

        def is_timestamp_row(g: list) -> bool:
            return len(g) == 1 and _is_timestamp_or_system(g[0].text)

        def flush(g: list):
            if not g or is_timestamp_row(g):
                return
            # Determine sender: average x of all lines in the bubble
            avg_cx = sum(l.cx for l in g) / len(g)
            if avg_cx > mid_x:
                sender = Sender.ME
            else:
                sender = Sender.OTHER
            raw_text = " ".join(l.text for l in g)
            text = raw_text.strip()
            kind = _infer_kind(text)
            messages.append(Message(sender=sender, text=text, kind=kind, raw=raw_text))

        for l in lines:
            if bubble_group and l.cy - bubble_group[-1].cy > 20:  # new bubble
                flush(bubble_group)
                bubble_group = []
            bubble_group.append(l)
        flush(bubble_group)

        return messages

    def latest_inbound(self, full: Image.Image) -> Optional[Message]:
        """Return the most recent inbound (OTHER) Message, or None."""
        msgs = self.read_open_conversation(full)
        for m in reversed(msgs):
            if m.sender == Sender.OTHER:
                return m
        return None