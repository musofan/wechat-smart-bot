"""Action layer. DryRunActuator (default) records intended actions and touches
nothing; LiveActuator performs real foreground clicks/keystrokes via win32.

The LiveActuator is NEVER exercised in tests or during the overnight build — it is
only constructed when DRY_RUN is explicitly False and a human is present.
"""

from __future__ import annotations

import time


class DryRunActuator:
    """Records intended actions. Default everywhere; sends nothing."""

    def __init__(self):
        self.actions: list[tuple] = []

    def open_conversation(self, y):
        self.actions.append(("open", y))

    def focus_input(self):
        self.actions.append(("focus_input", None))

    def send_text(self, text):
        self.actions.append(("send", text))


class LiveActuator:
    """Real input against the desktop client: foreground the window, click by
    absolute coordinate, paste Chinese via clipboard, press Enter — with
    human-like randomized pauses. Uses win32 lazily so importing this module (and
    the DryRun path) needs no live environment. NOT covered by automated tests."""

    def __init__(self, capture, jitter: bool = True, rng=None):
        import random
        self.capture = capture
        self.jitter = jitter
        self.rng = rng or random.Random()

    def _pause(self, base: float):
        d = self.rng.lognormvariate(0, 0.35) * base if self.jitter else base
        time.sleep(max(0.05, d))

    def _foreground(self):
        import win32con
        import win32gui
        hwnd = self.capture.ensure_window()
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(hwnd)
        self._pause(0.3)

    def _click(self, x: int, y: int):
        import win32api
        import win32con
        win32api.SetCursorPos((int(x), int(y)))
        self._pause(0.12)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        self._pause(0.2)

    def open_conversation(self, y):
        self._foreground()
        r = self.capture.get_rect()
        self._click(r.left + int(r.width * 0.25), r.top + int(y))
        self._pause(0.6)

    def focus_input(self):
        self._foreground()
        r = self.capture.get_rect()
        self._click(r.left + int(r.width * 0.62), r.top + int(r.height * 0.93))
        self._pause(0.2)

    def send_text(self, text: str):
        import win32api
        import win32clipboard
        import win32con
        self.focus_input()
        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, text)
        win32clipboard.CloseClipboard()
        self._pause(0.2)
        # Ctrl+V
        win32api.keybd_event(0x11, 0, 0, 0)
        win32api.keybd_event(0x56, 0, 0, 0)
        win32api.keybd_event(0x56, 0, win32con.KEYEVENTF_KEYUP, 0)
        win32api.keybd_event(0x11, 0, win32con.KEYEVENTF_KEYUP, 0)
        self._pause(0.4)
        # Enter
        win32api.keybd_event(0x0D, 0, 0, 0)
        win32api.keybd_event(0x0D, 0, win32con.KEYEVENTF_KEYUP, 0)
        self._pause(0.3)


def make_actuator(dry_run: bool, capture=None):
    """DryRun unless explicitly told otherwise. Safety default: dry_run=True."""
    return DryRunActuator() if dry_run else LiveActuator(capture)
