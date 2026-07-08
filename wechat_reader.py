"""High-level conversation reader: turns a full-window capture into structured
messages, discriminating own vs. other bubbles. Read-only (no input/sending)."""

from __future__ import annotations

from dataclasses import dataclass

from PIL import Image

from wechat_vision import _TS_RE, _UI_NOISE, WeixinVision

# Fraction of the message-pane width past which a text line is treated as an
# own (right-aligned, green) bubble rather than the contact's (left-aligned).
_OWN_BUBBLE_X_FRAC = 0.55


@dataclass
class Message:
    sender: str  # 'me' | 'other' | 'system'
    text: str
    kind: str = "text"  # 'text' | 'system'


class WeixinReader:
    def __init__(self, vision: WeixinVision):
        self.vision = vision

    def read_contact_name(self, full: Image.Image) -> str:
        return self.vision.read_header(full).strip()

    def read_open_conversation(self, full: Image.Image) -> list[Message]:
        """Structured messages of the currently-open conversation, top→bottom."""
        crop = self.vision._crop(full, "messages")
        width = max(crop.size[0], 1)
        lines = self.vision.ocr(crop, min_score=0.5)
        lines.sort(key=lambda ln: ln.cy)

        msgs: list[Message] = []
        for ln in lines:
            text = ln.text.strip()
            if not text:
                continue
            if any(k in text for k in _UI_NOISE):
                continue
            if _TS_RE.match(text):
                msgs.append(Message("system", text, "system"))
                continue
            sender = "me" if (ln.cx / width) > _OWN_BUBBLE_X_FRAC else "other"
            msgs.append(Message(sender, text, "text"))
        return msgs

    @staticmethod
    def latest_inbound(msgs: list[Message]) -> Message | None:
        """The most recent message from the contact (not us, not system)."""
        for m in reversed(msgs):
            if m.sender == "other" and m.kind == "text":
                return m
        return None
