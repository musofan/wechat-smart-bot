"""WeChat Real-time Monitor Bot.

Monitors WeChat chat list for unread messages, reads them via screenshot+OCR,
generates replies via LLM, sends replies, and forwards to monitoring account.
"""

import ctypes
import time
import pyautogui
import pyperclip
import numpy as np
from PIL import Image
from llm_client import generate_reply, classify_message
from database import init_db, save_conversation, get_conversation_history, save_message
from config import Config


class WeChatMonitor:
    """Monitor WeChat for new messages and auto-reply."""

    # UI Layout constants (relative to window)
    NAV_BAR_WIDTH = 50       # Left navigation icons
    CHAT_LIST_WIDTH = 0.32   # Chat list takes ~32% of window width
    UNREAD_BADGE_REGION = (0, 0, 160, 825)  # Relative region to scan for badges

    def __init__(self):
        self._hwnd = None
        self._window_rect = None
        self._last_replied = set()  # Track replied message hashes
        self._monitor_wxid = "musomuso"  # Forward target

    def find_wechat(self):
        """Find WeChat window."""
        user32 = ctypes.windll.user32
        hwnd = user32.FindWindowW('Qt51514QWindowIcon', None)
        if not hwnd:
            hwnd = user32.FindWindowW('WeChatMainWndForPC', None)
        if hwnd:
            self._hwnd = hwnd
            self._update_rect()
            return True
        return False

    def _update_rect(self):
        """Update window rectangle cache."""
        user32 = ctypes.windll.user32
        rect = ctypes.wintypes.RECT()
        user32.GetWindowRect(self._hwnd, ctypes.byref(rect))
        self._window_rect = (rect.left, rect.top, rect.right, rect.bottom)

    def bring_to_front(self):
        """Bring WeChat to foreground."""
        if self._hwnd:
            user32 = ctypes.windll.user32
            user32.ShowWindow(self._hwnd, 9)
            user32.SetForegroundWindow(self._hwnd)
            time.sleep(0.3)

    def capture_full(self):
        """Capture full WeChat window."""
        self._update_rect()
        left, top, right, bottom = self._window_rect
        return pyautogui.screenshot(region=(left, top, right - left, bottom - top))

    def capture_region(self, rel_x, rel_y, rel_w, rel_h):
        """Capture a region relative to window (0-1 range)."""
        left, top, right, bottom = self._window_rect
        w, h = right - left, bottom - top
        x = left + int(w * rel_x)
        y = top + int(h * rel_y)
        pw = int(w * rel_w)
        ph = int(h * rel_h)
        return pyautogui.screenshot(region=(x, y, pw, ph))

    def find_unread_conversations(self):
        """Scan chat list for conversations with unread badges.

        Returns list of y_positions for items with unread badges.
        WeChat badge color: RGB(226, 71, 71) - bright red circle.
        """
        # Capture chat list area
        chat_list = self.capture_region(0.07, 0.09, 0.25, 0.85)
        img = np.array(chat_list)

        # WeChat unread badge is bright red: RGB ~(226, 71, 71)
        # Use a range that catches the badge color
        r, g, b = img[:, :, 0], img[:, :, 1], img[:, :, 2]
        badge_mask = (r > 200) & (r < 250) & (g > 50) & (g < 100) & (b > 50) & (b < 100)

        # Find rows with badge pixels
        rows_with_badge = np.where(badge_mask.any(axis=1))[0]

        if len(rows_with_badge) == 0:
            return []

        # Cluster into individual badges
        clusters = []
        current_cluster = [rows_with_badge[0]]
        for i in range(1, len(rows_with_badge)):
            if rows_with_badge[i] - rows_with_badge[i-1] <= 3:
                current_cluster.append(rows_with_badge[i])
            else:
                clusters.append(current_cluster)
                current_cluster = [rows_with_badge[i]]
        clusters.append(current_cluster)

        # Filter: real badges are ~15-40px tall circles
        conversations = []
        left, top, right, bottom = self._window_rect
        w, h = right - left, bottom - top
        chat_list_h = chat_list.height

        for cluster in clusters:
            height = max(cluster) - min(cluster) + 1
            # Also check column span
            cluster_rows = badge_mask[min(cluster):max(cluster)+1, :]
            cols = np.where(cluster_rows.any(axis=0))[0]
            width = len(cols) if len(cols) > 0 else 0

            # Badge filter: roughly square, 10-45px
            if 10 <= height <= 45 and width >= 10:
                badge_y_relative = (min(cluster) + max(cluster)) / 2
                badge_y = top + int(h * 0.09) + int(h * 0.85 * badge_y_relative / chat_list_h)
                conversations.append(badge_y)

        return conversations

    def click_conversation_at_y(self, y):
        """Click on a conversation at the given Y position."""
        left, top, right, bottom = self._window_rect
        w = right - left
        click_x = left + int(w * 0.18)  # Center of chat list item
        pyautogui.click(click_x, y)
        time.sleep(1.5)

    def get_chat_messages_ocr(self):
        """Read messages from the currently open chat using screenshot."""
        # Capture the chat message area (right side, top 75%)
        chat_area = self.capture_region(0.35, 0.12, 0.60, 0.70)

        # Save for debugging
        chat_area.save(r'C:\Users\Tung\wechat-smart-bot\data\last_chat.png')

        # Use cnocr to read text (lightweight Chinese OCR)
        try:
            from cnocr import CnOcr
            ocr = CnOcr()
            result = ocr.ocr(np.array(chat_area))

            messages = []
            for item in result:
                text = item.get('text', '')
                score = item.get('score', 0)
                if score > 0.3 and len(text.strip()) > 1:
                    messages.append(text.strip())
            return messages
        except Exception as e:
            print(f"[OCR ERROR] {e}")
            return []

    def send_reply(self, text):
        """Type and send a reply in the current chat."""
        left, top, right, bottom = self._window_rect
        w, h = right - left, bottom - top

        # Click input area
        input_x = left + int(w * 0.62)
        input_y = top + int(h * 0.93)
        pyautogui.click(input_x, input_y)
        time.sleep(0.3)

        # Paste text via clipboard
        pyperclip.copy(text)
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(0.3)

        # Press Enter to send
        pyautogui.press('enter')
        time.sleep(0.5)

    def open_chat_by_search(self, name):
        """Open a chat by searching for the contact name."""
        left, top, right, bottom = self._window_rect
        w, h = right - left, bottom - top

        # Click search box
        search_x = left + int(w * 0.18)
        search_y = top + 30
        pyautogui.click(search_x, search_y)
        time.sleep(0.5)

        # Type name
        pyperclip.copy(name)
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(1.5)

        # Click first result
        result_x = left + int(w * 0.18)
        result_y = top + 80
        pyautogui.click(result_x, result_y)
        time.sleep(1.5)

    def forward_to_monitor(self, sender, content, reply):
        """Forward a message to the monitoring account (musomuso)."""
        # Open chat with musomuso
        self.open_chat_by_search(self._monitor_wxid)
        time.sleep(0.5)

        # Compose forward message
        forward_msg = (
            f"📨 来自: {sender}\n"
            f"⏰ 时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"📝 内容: {content}\n"
            f"🤖 AI回复: {reply}"
        )

        # Send
        self.send_reply(forward_msg)
        time.sleep(0.5)

    def scan_and_reply(self):
        """Main scan cycle: check for unread, process, reply, forward."""
        if not self.find_wechat():
            print("[ERROR] WeChat not found!")
            return

        self.bring_to_front()
        time.sleep(0.3)

        # Find conversations with unread badges
        unread_y_positions = self.find_unread_conversations()

        if not unread_y_positions:
            return

        print(f"[SCAN] Found {len(unread_y_positions)} conversations with unread messages")

        for y_pos in unread_y_positions:
            try:
                # Click on the conversation
                self.click_conversation_at_y(y_pos)
                time.sleep(0.5)

                # Read the chat header to get sender name
                header = self.capture_region(0.35, 0.0, 0.60, 0.10)
                header.save(r'C:\Users\Tung\wechat-smart-bot\data\last_header.png')

                # OCR the header to get sender name
                try:
                    from cnocr import CnOcr
                    ocr = CnOcr()
                    header_result = ocr.ocr(np.array(header))
                    sender_name = header_result[0]['text'] if header_result else "Unknown"
                except:
                    sender_name = "Unknown"

                # Read messages in the chat
                messages = self.get_chat_messages_ocr()
                if not messages:
                    print(f"[SKIP] No messages readable from {sender_name}")
                    continue

                # Get the latest message (last non-empty line)
                latest_msg = ""
                for msg in reversed(messages):
                    if len(msg) > 2 and not msg.startswith("按住"):
                        latest_msg = msg
                        break

                if not latest_msg:
                    continue

                # Create hash to avoid re-processing
                msg_hash = f"{sender_name}:{latest_msg}"
                if msg_hash in self._last_replied:
                    continue
                self._last_replied.add(msg_hash)

                print(f"[RECV] {sender_name}: {latest_msg}")

                # Check if we should reply (skip our own, bots, and known non-contacts)
                skip_names = [
                    Config.BOT_NAME, "NeXT SCENE", "NeXTSCENE", "NEXTSCENE",
                    "微信ClawBot", "ClawBot", "文件传输助手",
                ]
                if any(skip in sender_name for skip in skip_names):
                    continue
                # Skip group chats (contain special characters or end with 群)
                if "群" in sender_name or "分享" in sender_name:
                    continue

                # Classify message
                history = get_conversation_history(sender_name)
                classification = classify_message(latest_msg, history)
                needs_confirm = classification.get("needs_confirmation", False)
                reason = classification.get("reason", "")

                # Generate reply
                ai_reply = generate_reply(history, latest_msg)
                print(f"[REPLY] {ai_reply}")

                # Send reply
                self.send_reply(ai_reply)
                time.sleep(0.5)

                # Save conversation
                save_conversation(sender_name, sender_name, "user", latest_msg)
                save_conversation(sender_name, sender_name, "assistant", ai_reply)

                # Forward to monitoring account
                try:
                    self.forward_to_monitor(sender_name, latest_msg, ai_reply)
                    print(f"[FORWARD] Sent to {self._monitor_wxid}")
                except Exception as e:
                    print(f"[FORWARD ERROR] {e}")

                # Go back to chat list
                self.bring_to_front()
                time.sleep(0.3)

            except Exception as e:
                print(f"[ERROR] Processing conversation: {e}")
                self.bring_to_front()
                time.sleep(0.3)

    def run(self, interval=5):
        """Main monitoring loop."""
        print("=" * 50)
        print("  WeChat Real-time Monitor Bot")
        print("  Scanning every", interval, "seconds")
        print("=" * 50)

        if not self.find_wechat():
            print("[FATAL] WeChat not found! Please open WeChat.")
            return

        init_db()
        print("[INFO] Database initialized.")
        print(f"[INFO] Monitor account: {self._monitor_wxid}")
        print("[INFO] Press Ctrl+C to stop.\n")

        while True:
            try:
                self.scan_and_reply()
                time.sleep(interval)
            except KeyboardInterrupt:
                print("\n[SHUTDOWN] Monitor stopped.")
                break
            except Exception as e:
                print(f"[ERROR] {e}")
                time.sleep(5)


if __name__ == "__main__":
    bot = WeChatMonitor()
    bot.run(interval=5)
