"""WeChat Computer Use Bot - Screen Capture + OCR + Keyboard Simulation.

Uses pyautogui for screen capture, PaddleOCR for text recognition,
and keyboard simulation for sending messages. Works with Weixin 4.x.
"""

import time
import ctypes
import pyautogui
import pyperclip
import psutil
from llm_client import generate_reply
from database import init_db, save_conversation, get_conversation_history, save_message


class WeChatComputerUseBot:
    """Bot that reads screen and simulates keyboard to interact with WeChat."""

    def __init__(self):
        # Try EasyOCR first, fall back to other OCR engines
        try:
            import easyocr
            self.ocr_reader = easyocr.Reader(['ch_sim', 'en'], gpu=False)
            self.ocr_engine = 'easyocr'
            print("[OCR] Using EasyOCR")
        except ImportError:
            print("[OCR] EasyOCR not available, trying PaddleOCR...")
            try:
                from paddleocr import PaddleOCR
                self.ocr_reader = PaddleOCR(use_textline_orientation=True, lang='ch')
                self.ocr_engine = 'paddleocr'
                print("[OCR] Using PaddleOCR")
            except Exception:
                self.ocr_reader = None
                self.ocr_engine = None
                print("[OCR] WARNING: No OCR engine available!")

        self._my_wxid = "self"
        self._last_messages = set()
        self._hwnd = None

    def find_wechat_window(self):
        """Find WeChat window handle."""
        user32 = ctypes.windll.user32

        # Try WeChat 4.x class name
        hwnd = user32.FindWindowW('Qt51514QWindowIcon', None)
        if hwnd:
            print(f"[INFO] Found WeChat 4.x window: HWND={hwnd}")
            self._hwnd = hwnd
            return True

        # Try WeChat 3.x class name
        hwnd = user32.FindWindowW('WeChatMainWndForPC', None)
        if hwnd:
            print(f"[INFO] Found WeChat 3.x window: HWND={hwnd}")
            self._hwnd = hwnd
            return True

        return False

    def bring_to_front(self):
        """Bring WeChat window to foreground."""
        if self._hwnd:
            user32 = ctypes.windll.user32
            user32.ShowWindow(self._hwnd, 9)  # SW_RESTORE
            user32.SetForegroundWindow(self._hwnd)
            time.sleep(0.5)

    def get_window_rect(self):
        """Get WeChat window rectangle."""
        if not self._hwnd:
            return None
        rect = ctypes.wintypes.RECT()
        ctypes.windll.user32.GetWindowRect(self._hwnd, ctypes.byref(rect))
        return (rect.left, rect.top, rect.right, rect.bottom)

    def capture_chat_area(self):
        """Capture the chat message area of WeChat."""
        rect = self.get_window_rect()
        if not rect:
            return None

        left, top, right, bottom = rect
        width = right - left
        height = bottom - top

        # Chat area is roughly the right 60% of the window, bottom 70%
        chat_left = left + int(width * 0.35)
        chat_top = top + int(height * 0.15)
        chat_width = int(width * 0.60)
        chat_height = int(height * 0.75)

        screenshot = pyautogui.screenshot(region=(chat_left, chat_top, chat_width, chat_height))
        return screenshot

    def capture_input_area(self):
        """Capture the input area of WeChat."""
        rect = self.get_window_rect()
        if not rect:
            return None

        left, top, right, bottom = rect
        width = right - left
        height = bottom - top

        # Input area is roughly the right 60%, bottom 25%
        input_left = left + int(width * 0.35)
        input_top = top + int(height * 0.85)
        input_width = int(width * 0.60)
        input_height = int(height * 0.12)

        return (input_left, input_top, input_width, input_height)

    def ocr_screenshot(self, screenshot):
        """Run OCR on a screenshot and return text lines."""
        import io
        import numpy as np

        # Convert PIL image to numpy array
        img_array = np.array(screenshot)

        # Run OCR
        result = self.ocr.ocr(img_array, cls=True)

        lines = []
        if result and result[0]:
            for line in result[0]:
                text = line[1][0]
                confidence = line[1][1]
                if confidence > 0.5:
                    lines.append(text)

        return lines

    def get_latest_messages(self, num_lines=5):
        """Get the latest messages from the chat area."""
        screenshot = self.capture_chat_area()
        if screenshot is None:
            return []

        lines = self.ocr_screenshot(screenshot)
        return lines[-num_lines:] if len(lines) > num_lines else lines

    def send_message(self, text):
        """Send a message by typing it into the input area."""
        rect = self.get_window_rect()
        if not rect:
            return False

        left, top, right, bottom = rect
        width = right - left
        height = bottom - top

        # Click on input area
        input_x = left + int(width * 0.55)
        input_y = top + int(height * 0.92)
        pyautogui.click(input_x, input_y)
        time.sleep(0.3)

        # Use clipboard to paste (more reliable for Chinese)
        pyperclip.copy(text)
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(0.2)

        # Press Enter to send
        pyautogui.press('enter')
        time.sleep(0.5)
        return True

    def monitor_and_reply(self, interval=3):
        """Main monitoring loop."""
        print("=" * 50)
        print("  WeChat Computer Use Bot")
        print("  Monitoring via Screen Capture + OCR")
        print("=" * 50)

        if not self.find_wechat_window():
            print("[ERROR] WeChat window not found! Please open WeChat.")
            return

        init_db()
        print("[INFO] Database initialized.")
        print(f"[INFO] Monitoring interval: {interval}s")
        print("[INFO] Press Ctrl+C to stop.")
        print()

        while True:
            try:
                self.bring_to_front()
                time.sleep(0.3)

                messages = self.get_latest_messages()
                if messages:
                    # Get the latest message (last line)
                    latest = messages[-1].strip()
                    if latest and latest not in self._last_messages and len(latest) > 2:
                        self._last_messages.add(latest)

                        # Keep set manageable
                        if len(self._last_messages) > 100:
                            self._last_messages = set(list(self._last_messages)[-50:])

                        print(f"[RECV] {latest}")

                        # Generate AI reply
                        history = get_conversation_history(self._my_wxid)
                        reply = generate_reply(history, latest)
                        print(f"[REPLY] {reply}")

                        # Send reply
                        if self.send_message(reply):
                            print("[SENT] Reply sent!")
                            save_conversation(self._my_wxid, "contact", "user", latest)
                            save_conversation(self._my_wxid, "contact", "assistant", reply)

                time.sleep(interval)

            except KeyboardInterrupt:
                print("\n[SHUTDOWN] Bot stopped.")
                break
            except Exception as e:
                print(f"[ERROR] {e}")
                time.sleep(5)


if __name__ == "__main__":
    bot = WeChatComputerUseBot()
    bot.monitor_and_reply()
