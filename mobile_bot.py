"""WeChat Mobile Bot - ADB + uiautomator2 + OCR.

Uses phone screenshots + cnocr (larger text = better accuracy)
to monitor and auto-reply to WeChat messages.
"""

import time
import io
import re
import base64
import numpy as np
import uiautomator2 as u2
from cnocr import CnOcr
from llm_client import generate_reply
from database import init_db, save_conversation, get_conversation_history, save_message
from config import Config


class WeChatMobileBot:
    """Monitor and auto-reply to WeChat on Android phone."""

    # Human-like system prompt (no AI identity revealed)
    HUMAN_PROMPT = """你是一个真人在回复微信消息。请注意：
1. 绝对不要暴露你是 AI 或机器人
2. 不要说"作为AI助手"之类的话
3. 语气要自然，像朋友聊天
4. 回复简短，一般 1-2 句话
5. 可以用"哈哈"、"嗯嗯"等口语化表达
6. 不确定时说"我看看"、"稍等我查一下"""

    def __init__(self, device_id=None):
        # Connect to phone
        if device_id:
            self.d = u2.connect(device_id)
        else:
            self.d = u2.connect()

        self.ocr = CnOcr()
        self._processed = set()
        self._monitor_wxid = "musomuso"

        info = self.d.info
        print(f"[DEVICE] {info.get('productName', 'Unknown')}, "
              f"{info.get('displayWidth')}x{info.get('displayHeight')}, "
              f"Android {info.get('sdkInt')}")

    def screenshot(self):
        """Take a screenshot of the phone."""
        return self.d.screenshot()

    def screenshot_base64(self, img=None):
        """Convert screenshot to base64 for Vision API."""
        if img is None:
            img = self.screenshot()
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        return base64.b64encode(buf.getvalue()).decode()

    def ocr_screenshot(self, img=None):
        """OCR a screenshot and return text lines."""
        if img is None:
            img = self.screenshot()
        result = self.ocr.ocr(np.array(img))
        texts = []
        for item in result:
            text = item.get('text', '')
            score = item.get('score', 0)
            if score > 0.5 and len(text.strip()) > 1:
                texts.append(text.strip())
        return texts

    def get_chat_list(self):
        """Read the chat list from phone screen.

        Returns list of dicts: {name, preview, time, y_position}
        """
        img = self.screenshot()
        img_array = np.array(img)
        result = self.ocr.ocr(img_array)

        # Parse OCR results into conversations
        conversations = []
        items = []
        for item in result:
            text = item.get('text', '')
            score = item.get('score', 0)
            pos = item.get('position', [])
            if score > 0.4 and len(text) > 1:
                y = (pos[0][1] + pos[2][1]) / 2 if len(pos) >= 2 else 0
                items.append((y, text, score))

        items.sort(key=lambda x: x[0])

        # Group by Y position (conversations are ~150px apart on phone)
        current = {'y': 0, 'texts': []}
        for y, text, score in items:
            if y - current['y'] > 100:  # New conversation group
                if current['texts']:
                    conversations.append(current)
                current = {'y': y, 'texts': []}
            current['texts'].append(text)
            current['y'] = y
        if current['texts']:
            conversations.append(current)

        # Parse each conversation group
        results = []
        for conv in conversations:
            texts = conv['texts']
            name = texts[0] if texts else ''

            # Skip non-conversation items
            if any(skip in name for skip in ['微信', '搜索', '通讯录', '发现', '我', '折叠']):
                continue
            if len(name) < 2:
                continue

            # Skip if first text is just a time (e.g., "19:59")
            if re.match(r'^\d{1,2}:\d{2}$', name):
                continue
            # Skip if first text is a date
            if re.match(r'^\d+月\d+日$', name):
                continue

            # Find the actual name (first text that's not a time/date)
            actual_name = name
            for t in texts:
                if not re.match(r'^\d{1,2}:\d{2}$', t) and not re.match(r'^\d+月\d+日$', t) and len(t) >= 2:
                    actual_name = t
                    break

            # Extract time and preview
            preview = ' '.join(texts[1:3]) if len(texts) > 1 else ''
            time_str = ''
            for t in texts:
                if re.match(r'^\d{1,2}:\d{2}$', t):
                    time_str = t
                    break

            results.append({
                'name': actual_name,
                'preview': preview,
                'time': time_str,
                'y': conv['y'],
                'all_texts': texts,
            })

        return results

    def open_chat(self, y_position):
        """Tap on a chat at the given Y position (relative to screen)."""
        # WeChat chat list items are typically in the middle of screen width
        self.d.click(540, int(y_position))  # Center of 1080px width
        time.sleep(1.5)

    def read_chat_messages(self):
        """Read messages from the currently open chat."""
        img = self.screenshot()
        result = self.ocr.ocr(np.array(img))

        messages = []
        for item in result:
            text = item.get('text', '')
            score = item.get('score', 0)
            if score > 0.5 and len(text.strip()) > 1:
                # Skip UI elements
                if not any(skip in text for skip in [
                    '按住', '语音', '输入', '发送', '切换到',
                    '键盘', '表情', '收藏', '转账', '截图'
                ]):
                    messages.append(text.strip())
        return messages

    def send_reply(self, text):
        """Type and send a reply in the current chat."""
        # Find and tap input area (bottom of screen)
        self.d.click(400, 2200)  # Approximate input area position
        time.sleep(0.5)

        # Type text
        self.d.send_keys(text)
        time.sleep(0.3)

        # Tap send button
        # Try to find send button by text
        if self.d(text="发送").exists:
            self.d(text="发送").click()
        else:
            # Try clicking send button position
            self.d.click(980, 2200)
        time.sleep(0.5)

    def open_chat_by_name(self, name):
        """Open a chat by tapping search and typing name."""
        # Tap search icon
        self.d.click(900, 140)
        time.sleep(0.5)

        # Type name
        self.d.send_keys(name)
        time.sleep(2)

        # Tap first result
        self.d.click(540, 300)
        time.sleep(1.5)

    def go_back(self):
        """Press back button."""
        self.d.press("back")
        time.sleep(0.5)

    def should_skip(self, name):
        """Check if we should skip this conversation."""
        skip_list = ['ClawBot', '文件传输助手', '公众号', '订阅号']
        for skip in skip_list:
            if skip in name:
                return True
        if '群' in name or '分享' in name:
            return True
        return False

    def process_chat(self, chat_info):
        """Process a single conversation."""
        name = chat_info['name']
        y = chat_info['y']

        print(f"[OPEN] {name} (y={y:.0f})", flush=True)

        # Open the chat
        self.open_chat(y)

        # Read messages
        messages = self.read_chat_messages()
        print(f"[READ] {len(messages)} texts found", flush=True)

        if not messages:
            self.go_back()
            return

        # Get the latest message
        latest = messages[-1] if messages else ''
        if len(latest) < 3:
            latest = messages[-2] if len(messages) > 1 else ''

        if not latest:
            self.go_back()
            return

        # Check dedup
        msg_key = f"{name}:{latest}"
        if msg_key in self._processed:
            print(f"[DUP] Skip: {latest[:30]}", flush=True)
            self.go_back()
            return
        self._processed.add(msg_key)

        print(f"[RECV] {name}: {latest}", flush=True)

        # Generate reply
        history = get_conversation_history(name)
        reply = generate_reply(history, latest, system_prompt=self.HUMAN_PROMPT)
        print(f"[REPLY] {reply}", flush=True)

        # Send reply
        self.send_reply(reply)
        time.sleep(0.5)

        # Save conversation
        save_conversation(name, name, "user", latest)
        save_conversation(name, name, "assistant", reply)

        # Forward to monitoring account
        try:
            self.open_chat_by_name(self._monitor_wxid)
            time.sleep(0.5)
            forward = f"📨 来自: {name}\n⏰ {time.strftime('%H:%M')}\n📝 {latest}\n🤖 回复: {reply}"
            self.send_reply(forward)
            print(f"[FORWARD] Sent to {self._monitor_wxid}", flush=True)
            self.go_back()
        except Exception as e:
            print(f"[FORWARD ERROR] {e}", flush=True)

        # Go back to chat list
        self.go_back()

    def run(self, interval=5):
        """Main monitoring loop."""
        print("=" * 50)
        print("  WeChat Mobile Bot")
        print(f"  Scanning every {interval}s")
        print("=" * 50)

        init_db()
        print("[INFO] Database initialized.", flush=True)
        print(f"[INFO] Monitor: {self._monitor_wxid}", flush=True)
        print("[INFO] Press Ctrl+C to stop.\n", flush=True)

        # Go to WeChat chat list
        self.d.app_start('com.tencent.mm')
        time.sleep(1)

        while True:
            try:
                # Ensure WeChat is in foreground
                current = self.d.app_current()
                if current.get('package') != 'com.tencent.mm':
                    self.d.app_start('com.tencent.mm')
                    time.sleep(1)

                # Scan chat list
                chats = self.get_chat_list()

                if chats:
                    # Process top 3 non-skipped chats
                    processed_count = 0
                    for chat in chats[:5]:
                        if self.should_skip(chat['name']):
                            continue
                        if processed_count >= 2:  # Max 2 per cycle
                            break

                        self.process_chat(chat)
                        processed_count += 1
                        time.sleep(0.5)

                time.sleep(interval)

            except KeyboardInterrupt:
                print("\n[SHUTDOWN] Mobile bot stopped.", flush=True)
                break
            except Exception as e:
                print(f"[ERROR] {e}", flush=True)
                time.sleep(5)


if __name__ == "__main__":
    bot = WeChatMobileBot()
    bot.run(interval=5)
