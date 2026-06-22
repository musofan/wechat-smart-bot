"""Message routing engine - core logic for message processing."""

import time
from config import Config
from database import (
    save_message, save_conversation, get_conversation_history,
    add_to_confirm_queue, mark_message_processed,
    get_pending_confirmations, resolve_confirmation,
)
from llm_client import generate_reply, classify_message
from wechat_handler import WeChatHandler


class MessageRouter:
    """Routes incoming messages through the processing pipeline."""

    def __init__(self, handler: WeChatHandler):
        self.handler = handler

    def should_process(self, wxid: str, content: str, is_group: bool = False) -> bool:
        """Determine if a message should be processed."""
        # Skip self messages
        if self.handler._my_wxid and wxid == self.handler._my_wxid:
            return False

        # Skip empty content
        if not content or not content.strip():
            return False

        # Skip non-text content
        if content in ("[图片]", "[语音]", "[视频]", "[链接/卡片]", "[系统消息]"):
            return False

        # Skip messages from the monitor account (avoid loops)
        monitor_wxid = self.handler.get_monitor_wxid()
        if monitor_wxid and wxid == monitor_wxid:
            self._handle_monitor_reply(content)
            return False

        return True

    def _handle_monitor_reply(self, content: str):
        """Handle replies from the monitoring account for confirmation."""
        content = content.strip()

        items = get_pending_confirmations()
        if not items:
            return

        if content == "1":
            # Use AI suggested reply for oldest pending
            self._resolve_pending(items[0])
        elif content.startswith("2"):
            # Custom reply
            custom_reply = content[1:].strip()
            if custom_reply:
                self._resolve_pending(items[0], custom_reply)
        elif content == "3":
            # Skip
            self._resolve_pending(items[0], skip=True)

    def _resolve_pending(self, item: dict, custom_reply: str = "", skip: bool = False):
        """Resolve a pending confirmation."""
        queue_id = item["id"]
        wxid = item["wxid"]

        if skip:
            resolve_confirmation(queue_id, "skipped")
            self.handler.send_text(wxid, "好的，这条消息暂不回复。")
        elif custom_reply:
            resolve_confirmation(queue_id, "modified", custom_reply)
            self.handler.send_text(wxid, custom_reply)
        else:
            ai_reply = item["llm_reply"]
            resolve_confirmation(queue_id, "confirmed", ai_reply)
            self.handler.send_text(wxid, ai_reply)

    def process_incoming(self, wxid: str, nickname: str, content: str,
                          is_group: bool = False, group_name: str = "",
                          msg_id: str = "") -> None:
        """Main processing pipeline for incoming messages."""
        print(f"[RECV] {nickname}({wxid}): {content[:80]}...")

        # 1. Save to messages table
        save_message(msg_id, wxid, nickname, content, is_group=is_group,
                     group_name=group_name, direction="incoming")

        # 2. Check if should process
        if not self.should_process(wxid, content, is_group):
            return

        # 3. Classify: does this need human confirmation?
        history = get_conversation_history(wxid, limit=20)
        classification = classify_message(content, history)
        needs_confirmation = classification.get("needs_confirmation", False)
        reason = classification.get("reason", "")

        print(f"[CLASSIFY] needs_confirm={needs_confirmation} reason={reason}")

        # 4. Also check keyword-based rules
        if not needs_confirmation:
            for keyword in Config.CRITICAL_KEYWORDS:
                if keyword in content:
                    needs_confirmation = True
                    reason = f"命中关键词: {keyword}"
                    break

        # 5. Generate AI reply
        ai_reply = generate_reply(history, content)

        # 6. Save conversation context
        save_conversation(wxid, nickname, "user", content, msg_id)
        save_conversation(wxid, nickname, "assistant", ai_reply, msg_id)

        # 7. Route based on classification
        monitor_wxid = self.handler.get_monitor_wxid()

        if needs_confirmation:
            # Add to confirmation queue
            queue_id = add_to_confirm_queue(msg_id, wxid, nickname, content, ai_reply, reason)

            # Forward to monitoring account with confirmation request
            if monitor_wxid:
                forward_msg = self.handler.format_confirm_request(
                    nickname, content, ai_reply, reason
                )
                self.handler.send_text(monitor_wxid, forward_msg)

            print(f"[PENDING] Message from {nickname} needs confirmation (queue #{queue_id})")
        else:
            # Forward to monitoring account
            if monitor_wxid:
                forward_msg = self.handler.format_forward_message(
                    nickname, content, is_group, group_name, ai_reply
                )
                self.handler.send_text(monitor_wxid, forward_msg)

            # Auto-reply to sender
            self.handler.send_with_delay(wxid, ai_reply)
            mark_message_processed(msg_id)
            print(f"[REPLIED] Auto-replied to {nickname}: {ai_reply[:50]}...")
