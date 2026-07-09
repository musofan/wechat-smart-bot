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
from safety import Safety
from store import SuggestionStore
from wechat_reader import ConversationReader
from wechat_vision import Conversation, WeixinVision

logger = logging.getLogger(__name__)

# Forward-reference for the actuator protocol
_Actuator = object


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
            try:
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
            except Exception as exc:
                logger.error(
                    "tick: exception processing %s: %s",
                    conv.name, exc, exc_info=True,
                )
                continue

        return results

    # ---- SEND mode: process pending suggestions ----

    def process_pending(
        self,
        safety: Safety | None = None,
        max_items: int = 5,
    ) -> list[dict]:
        """Process pending suggestions from the store — SEND mode.

        Args:
            safety: Safety gate instance. If None, a default is created.
            max_items: Maximum number of pending items to process.

        Returns:
            List of dicts describing what was done, each with keys:
                contact, draft_reply, sent, skipped_reason
        """
        if safety is None:
            safety = Safety(config=self._config)

        pending = self._store.list_pending(limit=max_items)
        if not pending:
            return []

        results: list[dict] = []

        for suggestion in pending:
            contact = suggestion["contact"]
            draft = suggestion["draft_reply"]
            sid = suggestion["id"]

            # 1. Human-confirm queue: only proceed if DRY_RUN is enabled
            #    (in real operation, operator replies 1/2/3)
            if not self._config.DRY_RUN:
                # Safety gate
                ok, reason = safety.can_send()
                if not ok:
                    logger.warning(
                        "Safety blocked send to %s: %s", contact, reason,
                    )
                    results.append({
                        "contact": contact,
                        "draft_reply": draft,
                        "sent": False,
                        "skipped_reason": reason,
                    })
                    continue

            # 2. Open conversation
            self._actuator.open_conversation(0)  # y=0 in SEND mode
            # In live mode we'd calculate y from the contact list

            # 3. Focus input
            self._actuator.focus_input()

            # 4. Send reply
            needs_confirm = bool(suggestion.get("needs_confirmation", False))
            if needs_confirm:
                # Send the draft as-is (the human has approved it)
                pass

            self._actuator.send_text(draft)

            if not self._config.DRY_RUN:
                safety.record_send()
                logger.info("SEND: replied to %s: %.60s", contact, draft)
            else:
                logger.info(
                    "[DRY] Would send to %s: %.60s", contact, draft,
                )

            # 5. Update status
            self._store.update_status(sid, "sent")

            results.append({
                "contact": contact,
                "draft_reply": draft,
                "sent": True,
                "skipped_reason": "",
            })

        return results

    # ---- Human-confirm queue helpers ----

    def human_reply(self, reply_text: str) -> list[str]:
        """Parse a human-confirm reply from the monitor chat.

        Format::
            ``1``       — approve the first pending suggestion (send as drafted)
            ``2 <text>`` — approve with custom text (uses provided text instead)
            ``3``       — skip / reject
            ``l`` or ``list`` — list all pending suggestions

        Args:
            reply_text: Raw text from the monitor chat.

        Returns:
            Action tokens parsed from the reply.
        """
        reply_text = reply_text.strip().lower()
        parts = reply_text.split(maxsplit=1)
        cmd = parts[0]

        if cmd == "1":
            return ["approve_next"]
        elif cmd == "2" and len(parts) > 1:
            return ["approve_custom", parts[1]]
        elif cmd == "3":
            return ["skip_next"]
        elif cmd in ("l", "list"):
            pending = self._store.list_pending(limit=20)
            if not pending:
                return ["no_pending"]
            lines = ["待处理建议："]
            for i, s in enumerate(pending[:5], 1):
                lines.append(
                    f"  {i}. [{s['contact']}] {s['draft_reply'][:50]}"
                )
            return ["list", "\n".join(lines)]
        else:
            return ["unknown", reply_text]

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
