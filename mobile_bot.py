"""WeChat Mobile Bot - ADB + uiautomator2 + Vision/OCR.

Uses phone screenshots + AI Vision model for reliable screen understanding.
Falls back to cnocr OCR when Vision API is not configured.
"""

import time
import io
import re
import base64
import numpy as np

# Load .env before importing other modules
from dotenv import load_dotenv
load_dotenv()

import uiautomator2 as u2
from llm_client import generate_reply
from database import init_db, save_conversation, get_conversation_history, save_message
from config import Config
from vision_client import VisionClient


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

        # Initialize Vision client (auto-detects provider)
        self.vision = VisionClient(provider="auto")
        print(f"[VISION] Provider: {self.vision.provider}")

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

        Uses Vision model if available, falls back to OCR.
        Returns list of dicts: {name, preview, time, y_position}
        """
        img = self.screenshot()

        if self.vision.provider != "none":
            # Use Vision model for reliable parsing
            conversations = self.vision.analyze_wechat_chat_list(img)
            # Add estimated Y positions (conversations are ~130px apart)
            for i, conv in enumerate(conversations):
                conv['y'] = 280 + i * 130  # Approximate positions
            return conversations[:5]

        # Fallback: OCR-based parsing (less reliable)
        return self._ocr_chat_list(img)

    def _ocr_chat_list(self, img):
        """OCR-based chat list parsing (fallback)."""
        from cnocr import CnOcr
        ocr = CnOcr()
        result = ocr.ocr(np.array(img))

        items = []
        for item in result:
            text = item.get('text', '')
            score = item.get('score', 0)
            pos = item.get('position', [])
            if score > 0.3 and len(text) > 1:
                y = (pos[0][1] + pos[2][1]) / 2 if len(pos) >= 2 else 0
                items.append((y, text, score))

        items.sort(key=lambda x: x[0])

        # Find time stamps and match names
        time_items = [(y, t) for y, t, s in items
                      if re.match(r'^\d{1,2}:\d{2}$', t) or re.match(r'^\d+月\d+日$', t)]

        skip_patterns = ['撤回', '移出', '邀请', '加入了', 'Windows',
                        '微信已登录', '折叠', '通讯录', '发现', '我']

        results = []
        for time_y, time_text in time_items:
            if time_text == re.match(r'^\d{1,2}:\d{2}$', time_text):
                continue  # Skip status bar time

            candidates = []
            for y, text, score in items:
                if abs(y - time_y) < 150 and score > 0.3:
                    if not any(skip in text for skip in skip_patterns):
                        if not re.match(r'^\d{1,2}:\d{2}$', text) and not re.match(r'^\d+月\d+日$', text):
                            if len(text) >= 2:
                                candidates.append((y, text))

            if candidates:
                candidates.sort(key=lambda x: abs(x[0] - time_y))
                name = candidates[0][1]
                preview = ' '.join([t for _, t in candidates[1:3]])
                results.append({
                    'name': name,
                    'preview': preview[:50],
                    'time': time_text,
                    'y': time_y,
                })

        return results[:5]

        # Smart parsing: find time/date stamps, then find the name above each
        import re
        # Identify time/date items (they mark conversation boundaries)
        time_items = []
        for y, text, score in items:
            if re.match(r'^\d{1,2}:\d{2}$', text) or re.match(r'^\d+月\d+日$', text):
                time_items.append((y, text))

        # For each time stamp, find the name that's closest ABOVE it
        results = []
        # Skip system messages like "你撤回了一条消息"
        skip_patterns = ['撤回', '移出', '邀请', '加入了', '加入了群聊',
                        'Windows', '微信已登录', '折叠置顶', '通讯录', '发现', '我']

        for time_y, time_text in time_items:
            # Find items NEAR this timestamp (±150px, since name may be above or below)
            candidates = []
            for y, text, score in items:
                if abs(y - time_y) < 150 and score > 0.4:
                    # Skip system messages, UI elements, and other timestamps
                    if not any(skip in text for skip in skip_patterns):
                        if not re.match(r'^\d{1,2}:\d{2}$', text) and not re.match(r'^\d+月\d+日$', text):
                            if len(text) >= 2:
                                candidates.append((y, text))

            # The name is typically the shortest text item near the timestamp
            # (names are shorter than previews)
            if candidates:
                # Pick the item closest to the timestamp Y position
                candidates.sort(key=lambda x: abs(x[0] - time_y))
                name = candidates[0][1]
                name_y = candidates[0][0]

                # Find preview (other text items near this timestamp)
                preview = ''
                for y, text in candidates:
                    if text != name:
                        preview += text + ' '

                results.append({
                    'name': name,
                    'preview': preview.strip()[:50],
                    'time': time_text,
                    'y': time_y,  # Use timestamp Y for clicking
                    'all_texts': [name, preview.strip(), time_text],
                })

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
        # Use ADB for more reliable tapping
        import subprocess
        adb = r'C:\Users\Tung\AppData\Local\Android\Sdk\platform-tools\adb.exe'
        x = 540  # Center of 1080px width
        y = int(y_position)
        subprocess.run([adb, 'shell', 'input', 'tap', str(x), str(y)])
        time.sleep(1.5)

    def read_chat_messages(self):
        """Read messages from the currently open chat.

        Uses Vision model if available, falls back to OCR.
        """
        img = self.screenshot()

        if self.vision.provider != "none":
            # Use Vision model
            msg_list = self.vision.analyze_wechat_messages(img)
            messages = []
            for msg in msg_list:
                if not msg.get('is_self', False):  # Only incoming messages
                    content = msg.get('content', '')
                    if content and len(content) > 1:
                        messages.append(content)
            return messages[-3:] if messages else []

        # Fallback: OCR
        from cnocr import CnOcr
        ocr = CnOcr()
        result = ocr.ocr(np.array(img))

        messages = []
        skip_ui = ['按住', '语音', '输入', '发送', '切换到', '键盘', '表情', '收藏', '转账', '截图']
        for item in result:
            text = item.get('text', '')
            score = item.get('score', 0)
            if score > 0.5 and len(text.strip()) > 1:
                if not any(skip in text for skip in skip_ui):
                    messages.append(text.strip())
        return messages[-3:] if messages else []

    def send_reply(self, text):
        """Type and send a reply in the current chat."""
        import subprocess
        adb = r'C:\Users\Tung\AppData\Local\Android\Sdk\platform-tools\adb.exe'

        # Tap input area (bottom center of chat)
        subprocess.run([adb, 'shell', 'input', 'tap', '400', '2150'])
        time.sleep(0.5)

        # Use ADB to input text (supports Chinese via clipboard)
        # Set clipboard text
        subprocess.run([adb, 'shell', 'am', 'broadcast',
                       '-a', 'clipper.set', '-e', 'text', text],
                      capture_output=True)
        time.sleep(0.2)

        # Try using uiautomator2 for text input (more reliable for Chinese)
        try:
            # Find input field
            input_field = self.d(className="android.widget.EditText")
            if input_field.exists:
                input_field.set_text(text)
            else:
                # Fallback: use ADB keyboard
                self.d.send_keys(text)
        except:
            self.d.send_keys(text)

        time.sleep(0.3)

        # Find and tap send button
        if self.d(text="发送").exists(timeout=2):
            self.d(text="发送").click()
        else:
            # Try coordinates for send button
            subprocess.run([adb, 'shell', 'input', 'tap', '1000', '2150'])
        time.sleep(0.5)

    def open_chat_by_name(self, name):
        """Open a chat by tapping search and typing name."""
        import subprocess
        adb = r'C:\Users\Tung\AppData\Local\Android\Sdk\platform-tools\adb.exe'

        # Tap search icon (top right area)
        subprocess.run([adb, 'shell', 'input', 'tap', '900', '140'])
        time.sleep(0.5)

        # Type name using ADB
        subprocess.run([adb, 'shell', 'input', 'text', name.replace(' ', '%s')])
        time.sleep(2)

        # Tap first result
        subprocess.run([adb, 'shell', 'input', 'tap', '540', '300'])
        time.sleep(1.5)

    def go_back(self):
        """Press back button."""
        self.d.press("back")
        time.sleep(0.5)

    def ensure_chat_list(self):
        """Ensure we're on the chat list view."""
        import subprocess
        adb = r'C:\Users\Tung\AppData\Local\Android\Sdk\platform-tools\adb.exe'

        # Always launch the main activity to ensure we're on chat list
        subprocess.run([adb, 'shell', 'am', 'start', '-n',
                      'com.tencent.mm/.ui.LauncherUI',
                      '-a', 'android.intent.action.MAIN',
                      '-c', 'android.intent.category.LAUNCHER'],
                     capture_output=True)
        time.sleep(1.5)

        # Verify we're in WeChat
        current = self.d.app_current()
        if current.get('package') != 'com.tencent.mm':
            # Try force starting
            self.d.app_start('com.tencent.mm')
            time.sleep(2)

    def should_skip(self, name):
        """Check if we should skip this conversation."""
        skip_list = [
            'ClawBot', '文件传输助手', '公众号', '订阅号',
            'Windows', '微信已登录', '手机通知',
        ]
        for skip in skip_list:
            if skip in name:
                return True
        # Skip group chats
        if '群' in name or '分享' in name or '交流' in name:
            return True
        # Skip system-like messages
        if '撤回' in name or '移出' in name:
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
                # Ensure WeChat is on chat list
                self.ensure_chat_list()

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
