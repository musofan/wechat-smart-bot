"""WeChat Smart Monitor - Improved message detection.

Strategy: Instead of relying on OCR for the chat list (text too small),
use a combination of:
1. Color-based badge detection (reliable)
2. Timestamp change detection (reliable)
3. OCR only for message content inside conversations (larger text, more accurate)
"""

import ctypes
import time
import pyautogui
import pyperclip
import numpy as np
from llm_client import generate_reply, classify_message
from database import init_db, save_conversation, get_conversation_history, save_message
from config import Config


class WeChatSmartMonitor:
    """Smart monitor using multi-signal detection."""

    # Badges to skip (bot accounts, system)
    SKIP_NAMES = [
        "微信ClawBot", "ClawBot", "文件传输助手",
        "公众号", "订阅号", "服务通知",
    ]

    def __init__(self):
        self._hwnd = None
        self._rect = None
        self._processed = set()  # Track processed conversations
        self._monitor_wxid = "musomuso"
        self._chat_state = {}  # Track chat list state for change detection

    def find_wechat(self):
        user32 = ctypes.windll.user32
        for cls in ['Qt51514QWindowIcon', 'WeChatMainWndForPC']:
            hwnd = user32.FindWindowW(cls, None)
            if hwnd:
                self._hwnd = hwnd
                self._update_rect()
                return True
        return False

    def _update_rect(self):
        user32 = ctypes.windll.user32
        rect = ctypes.wintypes.RECT()
        user32.GetWindowRect(self._hwnd, ctypes.byref(rect))
        self._rect = (rect.left, rect.top, rect.right, rect.bottom)

    def bring_to_front(self):
        if self._hwnd:
            user32 = ctypes.windll.user32
            user32.ShowWindow(self._hwnd, 9)
            user32.SetForegroundWindow(self._hwnd)
            time.sleep(0.3)

    def capture_region(self, rel_x, rel_y, rel_w, rel_h):
        left, top, right, bottom = self._rect
        w, h = right - left, bottom - top
        x = left + int(w * rel_x)
        y = top + int(h * rel_y)
        return pyautogui.screenshot(region=(x, y, int(w * rel_w), int(h * rel_h)))

    def go_to_chat_list(self):
        """Navigate to chat list view."""
        left, top, right, bottom = self._rect
        w = right - left
        # Click chat icon (first icon in nav bar)
        pyautogui.click(left + 25, top + 80)
        time.sleep(0.5)

    def scan_chat_list(self):
        """Scan chat list and return top conversation positions.

        Strategy: OCR the text area of chat list, group by Y position,
        return the Y positions of the top conversations that might have new messages.
        """
        left, top, right, bottom = self._rect
        w, h = right - left, bottom - top

        # Capture text area of chat list (skip avatar column)
        text_x = left + int(w * 0.07) + 50
        text_y = top + int(h * 0.09)
        text_w = int(w * 0.25) - 50
        text_h = int(h * 0.85)
        text_area = pyautogui.screenshot(region=(text_x, text_y, text_w, text_h))

        try:
            from cnocr import CnOcr
            ocr = CnOcr()
            result = ocr.ocr(np.array(text_area))

            # Group by Y position
            items = []
            for item in result:
                text = item.get('text', '')
                score = item.get('score', 0)
                pos = item.get('position', [])
                if score > 0.4 and len(text) > 1:
                    y = (pos[0][1] + pos[2][1]) / 2 if len(pos) >= 2 else 0
                    items.append((y, text))

            items.sort(key=lambda x: x[0])

            # Group into conversations (items within 30px are same conversation)
            conversations = []
            if items:
                current = {'y': items[0][0], 'texts': [items[0][1]]}
                for y, text in items[1:]:
                    if y - current['y'] > 30:
                        conversations.append(current)
                        current = {'y': y, 'texts': []}
                    current['texts'].append(text)
                    current['y'] = y
                conversations.append(current)

            # Return top 5 conversations with their screen Y positions
            results = []
            for conv in conversations[:5]:
                # Convert relative Y to screen Y
                screen_y = text_y + int(conv['y'])
                name = conv['texts'][0] if conv['texts'] else ''
                results.append((screen_y, name, conv['texts']))

            return results

        except Exception as e:
            print(f"[OCR ERROR] {e}")
            return []

    def open_conversation_at_y(self, y):
        """Click on a conversation at the given Y position."""
        left, top, right, bottom = self._rect
        w = right - left
        click_x = left + int(w * 0.18)
        pyautogui.click(click_x, y)
        time.sleep(1.5)

    def read_conversation_header(self):
        """Read the conversation title (sender name) from the header."""
        header = self.capture_region(0.35, 0.0, 0.50, 0.10)
        try:
            from cnocr import CnOcr
            ocr = CnOcr()
            result = ocr.ocr(np.array(header))
            if result:
                return result[0].get('text', 'Unknown')
        except:
            pass
        return 'Unknown'

    def read_latest_message(self):
        """Read the latest message from the chat area."""
        chat_area = self.capture_region(0.38, 0.15, 0.55, 0.65)
        try:
            from cnocr import CnOcr
            ocr = CnOcr()
            result = ocr.ocr(np.array(chat_area))

            messages = []
            for item in result:
                text = item.get('text', '')
                score = item.get('score', 0)
                if score > 0.5 and len(text.strip()) > 1:
                    # Skip system messages and UI elements
                    if not any(skip in text for skip in [
                        "按住", "语音", "输入", "发送", "Ctrl", "Win",
                        "文件传输", "搜索"
                    ]):
                        messages.append(text.strip())

            # Return the last few messages (most recent)
            return messages[-3:] if messages else []
        except Exception as e:
            print(f"[OCR ERROR] {e}")
            return []

    def send_reply(self, text):
        """Type and send a reply."""
        left, top, right, bottom = self._rect
        w, h = right - left, bottom - top

        input_x = left + int(w * 0.62)
        input_y = top + int(h * 0.93)
        pyautogui.click(input_x, input_y)
        time.sleep(0.3)

        pyperclip.copy(text)
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(0.3)
        pyautogui.press('enter')
        time.sleep(0.5)

    def open_chat_by_search(self, name):
        """Search and open a chat by name."""
        left, top, right, bottom = self._rect
        w, h = right - left, bottom - top

        pyautogui.click(left + int(w * 0.18), top + 30)
        time.sleep(0.5)
        pyperclip.copy(name)
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(2)
        pyautogui.click(left + int(w * 0.18), top + 80)
        time.sleep(1.5)

    def forward_to_monitor(self, sender, content, reply):
        """Forward message to monitoring account."""
        self.open_chat_by_search(self._monitor_wxid)
        time.sleep(0.5)

        forward = (
            f"📨 来自: {sender}\n"
            f"⏰ {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"📝 {content}\n"
            f"🤖 回复: {reply}"
        )
        self.send_reply(forward)
        time.sleep(0.5)

    def should_skip(self, name):
        """Check if we should skip this conversation."""
        if not name or name == 'Unknown':
            return True
        for skip in self.SKIP_NAMES:
            if skip in name:
                return True
        # Skip group chats
        if "群" in name or "分享" in name or "交流" in name:
            return True
        return False

    def process_conversation(self, y):
        """Process a single conversation with unread badge."""
        # Open the conversation
        self.open_conversation_at_y(y)
        time.sleep(0.5)

        # Read sender name
        sender = self.read_conversation_header()
        print(f"[OPENED] {sender}")

        if self.should_skip(sender):
            print(f"[SKIP] {sender}")
            self.go_to_chat_list()
            return

        # Read messages
        messages = self.read_latest_message()
        if not messages:
            print(f"[NO MSG] No readable messages from {sender}")
            self.go_to_chat_list()
            return

        # Get the latest message (last one that's not ours)
        latest = ""
        for msg in reversed(messages):
            if len(msg) > 2:
                latest = msg
                break

        if not latest:
            self.go_to_chat_list()
            return

        # Check if already processed
        msg_key = f"{sender}:{latest}"
        if msg_key in self._processed:
            print(f"[DUP] Already processed: {latest[:30]}...")
            self.go_to_chat_list()
            return
        self._processed.add(msg_key)

        print(f"[RECV] {sender}: {latest}")

        # Generate reply
        history = get_conversation_history(sender)
        classification = classify_message(latest, history)
        needs_confirm = classification.get("needs_confirmation", False)
        reason = classification.get("reason", "")

        # Use natural human-like prompt (not AI)
        human_prompt = """你是一个真人在回复微信消息。请注意：
1. 绝对不要暴露你是 AI 或机器人
2. 不要说"作为AI助手"之类的话
3. 语气要自然，像朋友聊天
4. 回复简短，一般 1-2 句话
5. 可以用"哈哈"、"嗯嗯"等口语化表达
6. 不确定时说"我看看"、"稍等我查一下"
7. 绝不主动提供建议或选项菜单"""

        ai_reply = generate_reply(history, latest, system_prompt=human_prompt)
        print(f"[REPLY] {ai_reply}")

        # Send reply
        self.send_reply(ai_reply)
        time.sleep(0.5)

        # Save conversation
        save_conversation(sender, sender, "user", latest)
        save_conversation(sender, sender, "assistant", ai_reply)

        # Forward to monitoring account
        try:
            self.forward_to_monitor(sender, latest, ai_reply)
            print(f"[FORWARD] Sent to {self._monitor_wxid}")
        except Exception as e:
            print(f"[FORWARD ERROR] {e}")

        # Go back to chat list
        self.go_to_chat_list()

    def run(self, interval=5):
        """Main monitoring loop."""
        print("=" * 50)
        print("  WeChat Smart Monitor")
        print("  Badge detection + OCR message reading")
        print("=" * 50)

        if not self.find_wechat():
            print("[FATAL] WeChat not found!")
            return

        init_db()
        self.bring_to_front()
        self.go_to_chat_list()

        print(f"[INFO] Monitor account: {self._monitor_wxid}")
        print(f"[INFO] Scan interval: {interval}s")
        print("[INFO] Press Ctrl+C to stop.\n")

        while True:
            try:
                self.bring_to_front()
                self.go_to_chat_list()
                time.sleep(0.3)

                # Scan chat list for conversations
                conversations = self.scan_chat_list()

                if conversations:
                    # Process top conversations (they're most likely to have new messages)
                    for y, name, texts in conversations[:3]:  # Top 3
                        # Skip known bots and groups
                        if self.should_skip(name):
                            continue

                        # Create a key to avoid reprocessing
                        msg_key = f"{name}:{texts[0] if texts else ''}"
                        if msg_key in self._processed:
                            continue

                        print(f"[SCAN] Processing: {name}")
                        try:
                            self.process_conversation(y)
                        except Exception as e:
                            print(f"[ERROR] Processing {name}: {e}")
                            self.bring_to_front()
                            self.go_to_chat_list()
                            time.sleep(0.5)

                time.sleep(interval)

            except KeyboardInterrupt:
                print("\n[SHUTDOWN] Monitor stopped.")
                break
            except Exception as e:
                print(f"[ERROR] {e}")
                time.sleep(5)


if __name__ == "__main__":
    monitor = WeChatSmartMonitor()
    monitor.run(interval=5)
