"""Orchestrator (SUGGEST mode) — detect unread, draft, classify, and store.

The Bot wires capture → vision → reader → reply_engine → store → actuator.
``tick()`` runs a single scan cycle: locate unread rows, skip filtered contacts,
read the latest inbound message, draft a reply, classify sensitivity, and persist
the suggestion. **No real sending ever happens** — the actuator only records.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from PIL import Image

from config import Config
from reply_engine import ReplyEngine
from store import SuggestionStore
from wechat_reader import ConversationReader
from wechat_vision import Conversation, WeixinVision

logger = logging.getLogger(__name__)


# Forward-reference for the actuator protocol (any object with open_conversation,
# send_text, focus_input — see RecordingActuator in tests/)
_Actuator = object  # will be typed properly when wechat_actuator.py is created


@dataclass
class TickResult:
    """Result of processing one unread conversation during tick()."""
    contact: str
    incoming: str
    draft_reply: str
    needs_confirmation: bool
    reason: str
    stored: bool  # True if saved to store


class Bot:
    """Bot orchestrator for SUGGEST mode.

    All dependencies are injected, making the orchestrator fully testable offline.
    """

    def __init__(
        self,
        capture,
        vision: WeixinVision,
        reader: ConversationReader,
        reply_engine: ReplyEngine,
        store: SuggestionStore,
        actuator,
        config: Config,
    ):
        self._capture = capture
        self._vision = vision
        self._reader = reader
        self._reply_engine = reply_engine
        self._store = store
        self._actuator = actuator
        self._config = config

        # Pre-computed skip set for fast lookups
        self._skip_names = frozenset(
            n.strip() for n in [
                config.BOT_NAME,
                *config.SKIP_NAMES,
            ] if n.strip()
        )
        self._group_markers = config.GROUP_MARKERS
        self._sensitive_keywords = config.SENSITIVE_KEYWORDS

    # ---- public API ----

    def tick(self, full_img: Optional[Image.Image] = None) -> list[TickResult]:
        """Run one scan cycle.

        Args:
            full_img: Optional pre-captured screenshot. When omitted, captures live.

        Returns:
            List of TickResult, one per unread conversation processed.
        """
        if full_img is None:
            full_img = self._capture.capture()

        # 1. Detect unread rows + build chat-list index
        convs = self._vision.read_chat_list(full_img)
        unread_ys = set(self._vision.detect_unread_rows(full_img))

        # Pick only unread conversations from the list
        candidates = [c for c in convs if c.has_unread or c.y_full in unread_ys]
        if not candidates:
            logger.debug("tick: no unread conversations")
            return []

        results: list[TickResult] = []

        for conv in candidates:
            if self._should_skip(conv):
                logger.debug("tick: skip %s", conv.name)
                continue

            # 2. "Open" the conversation (record-only in dry-run)
            self._actuator.open_conversation(conv.y_full)

            # 3. Read latest inbound message
            msg = self._reader.latest_inbound(full_img)
            if msg is None or msg.text in ("", "[图片]", "[语音]", "[文件]"):
                logger.debug("tick: %s — no usable inbound message", conv.name)
                continue

            # 4. Draft reply
            draft = self._reply_engine.draft([], msg.text)

            # 5. Classify
            classification = self._reply_engine.classify(msg.text)

            # 6. Store suggestion
            stored = self._store.save(
                contact=conv.name,
                incoming=msg.text,
                draft_reply=draft,
                needs_confirmation=classification.get("needs_confirmation", False),
                reason=classification.get("reason", ""),
            )

            logger.info(
                "tick: %s — inbound=%r draft=%r confirm=%s stored=%s",
                conv.name, msg.text[:40], draft[:40],
                classification.get("needs_confirmation"),
                stored,
            )

            results.append(TickResult(
                contact=conv.name,
                incoming=msg.text,
                draft_reply=draft,
                needs_confirmation=classification.get("needs_confirmation", False),
                reason=classification.get("reason", ""),
                stored=stored,
            ))

        return results

    # ---- helpers ----

    def _should_skip(self, conv: Conversation) -> bool:
        """Check if a conversation should be skipped (self, bots, groups)."""
        name = conv.name.strip()

        # Self / bot accounts
        if name in self._skip_names:
            return True

        # Group chats (markers in name)
        for marker in self._group_markers:
            if marker and marker in name:
                return True

        return False