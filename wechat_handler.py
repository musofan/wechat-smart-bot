"""WeChat message handling via WeChat-Hook HTTP API."""

import time
import random
from config import Config
from wechat_api import get_contacts


class WeChatHandler:
    """Handles WeChat message sending via HTTP API."""

    def __init__(self, bot, send_text_fn):
        self.bot = bot
        self.send_text_fn = send_text_fn
        self._monitor_wxid: str | None = None

    def get_monitor_wxid(self) -> str:
        """Resolve the monitoring account's wxid from its display name."""
        if self._monitor_wxid:
            return self._monitor_wxid

        try:
            contacts = get_contacts()
            for c in contacts:
                name = c.get("NickName", "")
                remark = c.get("Remark", "")
                wxid = c.get("UserName", "")
                if Config.MONITOR_ACCOUNT_NAME in (name, remark):
                    self._monitor_wxid = wxid
                    print(f"[INFO] Found monitor account: {name} -> {wxid}")
                    return wxid
        except Exception as e:
            print(f"[ERROR] Failed to get contacts: {e}")

        print(f"[WARNING] Monitor account '{Config.MONITOR_ACCOUNT_NAME}' not found!")
        return ""

    def send_text(self, receiver: str, content: str) -> bool:
        """Send a text message."""
        try:
            result = self.send_text_fn(receiver, content)
            if result:
                print(f"[SENT] -> {receiver}: {content[:50]}...")
            return result
        except Exception as e:
            print(f"[ERROR] send_text exception: {e}")
            return False

    def send_with_delay(self, receiver: str, content: str) -> bool:
        """Send with random delay for human-like behavior."""
        delay = random.uniform(Config.REPLY_DELAY_MIN, Config.REPLY_DELAY_MAX)
        time.sleep(delay)
        return self.send_text(receiver, content)

    def format_forward_message(self, nickname: str, content: str,
                                is_group: bool = False, group_name: str = "",
                                ai_reply: str = "", is_pending: bool = False) -> str:
        """Format a message for forwarding to the monitoring account."""
        prefix = f"[群:{group_name}] " if is_group else ""
        status = "⏳ 待确认" if is_pending else "🤖 已自动回复"

        lines = [
            f"📨 {prefix}来自: {nickname}",
            f"⏰ 时间: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"📝 内容: {content}",
        ]

        if ai_reply:
            lines.append(f"💬 {status}: {ai_reply}")
        else:
            lines.append(f"📊 状态: {status}")

        return "\n".join(lines)

    def format_confirm_request(self, nickname: str, content: str,
                                llm_reply: str, reason: str) -> str:
        """Format a confirmation request for the monitoring account."""
        return (
            f"⚠️ 需要确认回复\n"
            f"━━━━━━━━━━━━━━\n"
            f"👤 来自: {nickname}\n"
            f"⏰ 时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"📝 内容: {content}\n"
            f"━━━━━━━━━━━━━━\n"
            f"🤖 AI建议回复: {llm_reply}\n"
            f"📋 需确认原因: {reason}\n"
            f"━━━━━━━━━━━━━━\n"
            f"💡 回复格式:\n"
            f"  回复数字 1 = 使用AI建议\n"
            f"  回复 2+内容 = 自定义回复\n"
            f"  回复 3 = 暂不回复此消息"
        )
