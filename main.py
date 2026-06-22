"""WeChat Smart Bot - Main entry point.

Uses WeChat-Hook HTTP API (version.dll) for message handling.

Usage:
    1. Ensure WeChat (4.1.10.27) is running with version.dll loaded
    2. Run: python main.py
    3. The bot will poll for new messages and auto-reply via SenseNova LLM
"""

import sys
import time
import hashlib
from config import Config, validate_config
from database import init_db
from wechat_api import (
    check_login, get_self_profile, send_text,
    get_contacts, get_contact_name, get_recent_messages,
)
from wechat_handler import WeChatHandler
from message_router import MessageRouter


class WeChatBot:
    """Bot that polls for messages via HTTP API."""

    def __init__(self):
        self.handler = None
        self.router = None
        self._running = False
        self._last_msg_hash = set()

    def start(self):
        """Initialize and start the bot."""
        print("=" * 50)
        print("  WeChat Smart Bot Starting...")
        print("=" * 50)

        # 1. Validate config
        if not validate_config():
            print("[FATAL] Config validation failed. Check .env file.")
            sys.exit(1)

        print(f"[CONFIG] Bot name: {Config.BOT_NAME}")
        print(f"[CONFIG] Monitor account: {Config.MONITOR_ACCOUNT_NAME}")

        # 2. Initialize database
        init_db()
        print("[DB] Database initialized.")

        # 3. Check WeChat-Hook API
        print("[API] Checking WeChat-Hook HTTP API...")
        if not check_login():
            print("[FATAL] WeChat not logged in or HTTP API not available.")
            print("[FATAL] Make sure:")
            print("  1. WeChat 4.1.10.27 is running")
            print("  2. version.dll is in Weixin directory")
            print("  3. You are logged in")
            sys.exit(1)

        # 4. Get self profile
        profile = get_self_profile()
        my_nickname = profile.get("nickname", "Unknown")
        print(f"[INFO] Logged in as: {my_nickname}")

        # 5. Initialize handler and router (using HTTP API)
        self.handler = WeChatHandler(self, send_text_fn=send_text)
        self.router = MessageRouter(self.handler)

        # 6. Get monitor account wxid
        monitor_wxid = self.handler.get_monitor_wxid()
        if monitor_wxid:
            print(f"[MONITOR] Monitor account: {Config.MONITOR_ACCOUNT_NAME} -> {monitor_wxid}")

        self._running = True
        print("=" * 50)
        print("  Bot is running! Polling for new messages...")
        print("  Press Ctrl+C to stop.")
        print("=" * 50)

        # 7. Message polling loop
        self._poll_loop()

    def _poll_loop(self):
        """Poll for new messages periodically."""
        poll_interval = 2  # seconds

        while self._running:
            try:
                # Get recent messages
                messages = get_recent_messages(limit=10)

                for msg in messages:
                    # Create unique hash to avoid processing same message
                    msg_id = str(msg.get("localId", ""))
                    msg_hash = hashlib.md5(
                        f"{msg_id}:{msg.get('StrContent', '')}:{msg.get('StrTalker', '')}".encode()
                    ).hexdigest()

                    if msg_hash in self._last_msg_hash:
                        continue

                    self._last_msg_hash.add(msg_hash)

                    # Keep hash set manageable
                    if len(self._last_msg_hash) > 1000:
                        self._last_msg_hash = set(list(self._last_msg_hash)[-500:])

                    # Process the message
                    wxid = msg.get("StrTalker", "")
                    content = msg.get("StrContent", "")
                    is_self = msg.get("IsSender", 0) == 1

                    if not wxid or not content or is_self:
                        continue

                    # Get sender name
                    nickname = get_contact_name(wxid)

                    # Determine if group
                    is_group = "@chatroom" in wxid
                    group_name = wxid if is_group else ""

                    # Process through router
                    self.router.process_incoming(
                        wxid=wxid,
                        nickname=nickname,
                        content=content,
                        is_group=is_group,
                        group_name=group_name,
                        msg_id=msg_id,
                    )

                time.sleep(poll_interval)

            except KeyboardInterrupt:
                self.stop()
                break
            except Exception as e:
                print(f"[ERROR] Poll error: {e}")
                time.sleep(5)

    def stop(self):
        """Stop the bot."""
        self._running = False
        print("\n[SHUTDOWN] Bot stopped.")


def main():
    bot = WeChatBot()
    bot.start()


if __name__ == "__main__":
    main()
