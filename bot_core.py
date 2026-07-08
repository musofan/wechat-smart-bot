"""Orchestrator. In SUGGEST mode (default) it reads → drafts → classifies →
stores a suggestion and builds a monitor-forward record. It NEVER sends: the
actuator is only ever used by the (separate, gated) SEND path."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Suggestion:
    contact: str
    incoming: str
    draft_reply: str
    needs_confirmation: bool
    reason: str


class Bot:
    def __init__(self, vision, reader, reply_engine, store, config,
                 actuator=None, history_fn=None):
        self.vision = vision
        self.reader = reader
        self.reply = reply_engine
        self.store = store
        self.config = config
        self.actuator = actuator  # only used by the SEND path (gated); never in SUGGEST
        self.history_fn = history_fn or (lambda contact: [])

    # ---- filtering ----
    def should_skip(self, name: str) -> bool:
        if not name:
            return True
        for s in getattr(self.config, "SKIP_NAMES", []):
            if s and s in name:
                return True
        for g in getattr(self.config, "GROUP_MARKERS", []):
            if g and g in name:
                return True
        return False

    def scan_unread(self, full):
        """Chat-list conversations that have an unread badge and aren't skipped."""
        convs = self.vision.read_chat_list(full)
        return [c for c in convs if c.has_unread and not self.should_skip(c.name)]

    # ---- suggest-only handling of the currently-open conversation ----
    def handle_open_conversation(self, full):
        """Read the open conversation; if there's a fresh inbound, draft + classify
        + store a suggestion. Returns a new Suggestion, or None (skip/dupe/empty).
        Sends nothing."""
        contact = self.reader.read_contact_name(full)
        if self.should_skip(contact):
            return None
        msgs = self.reader.read_open_conversation(full)
        latest = self.reader.latest_inbound(msgs)
        if latest is None:
            return None

        history = self.history_fn(contact)
        draft = self.reply.draft(history, latest.text)
        cls = self.reply.classify(latest.text, history)
        sug = Suggestion(
            contact=contact, incoming=latest.text, draft_reply=draft,
            needs_confirmation=bool(cls.get("needs_confirmation")),
            reason=cls.get("reason", ""),
        )
        inserted = self.store.add(
            sug.contact, sug.incoming, sug.draft_reply,
            sug.needs_confirmation, sug.reason,
        )
        return sug if inserted else None

    # ---- gated SEND path (never fires under the safe defaults) ----
    def send_reply(self, sug: Suggestion, safety) -> tuple[bool, str]:
        """Send a reply ONLY when every gate passes: MODE=='SEND', not DRY_RUN,
        the message doesn't need human confirmation, and the safety envelope
        allows it. Returns (sent, reason). Under default config nothing is sent."""
        if getattr(self.config, "MODE", "SUGGEST") != "SEND":
            return False, "MODE != SEND (suggest-only)"
        if getattr(self.config, "DRY_RUN", True):
            return False, "DRY_RUN active"
        if sug.needs_confirmation:
            return False, "needs human confirmation"
        ok, why = safety.can_send()
        if not ok:
            return False, why
        self.actuator.send_text(sug.draft_reply)
        safety.record_send()
        return True, "sent"

    @staticmethod
    def parse_monitor_command(text: str) -> dict:
        """Parse a monitor-account confirmation reply: '1'=approve AI draft,
        '2 <text>'=custom reply, '3'=skip."""
        t = (text or "").strip()
        if t == "1":
            return {"action": "approve"}
        if t.startswith("2"):
            return {"action": "custom", "text": t[1:].strip()}
        if t == "3":
            return {"action": "skip"}
        return {"action": "none"}

    @staticmethod
    def forward_record(sug: Suggestion) -> str:
        status = "待人工确认" if sug.needs_confirmation else "已生成建议(未发送)"
        return (
            f"📨 来自: {sug.contact}\n"
            f"📝 内容: {sug.incoming}\n"
            f"🤖 建议回复: {sug.draft_reply}\n"
            f"📊 状态: {status}" + (f"  ({sug.reason})" if sug.reason else "")
        )
