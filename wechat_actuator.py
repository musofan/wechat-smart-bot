"""Actuator layer — mouse/keyboard actions for the Weixin PC client.

Defines the Actuator protocol that ``bot_core.Bot`` depends on:

- ``DryRunActuator`` — logs intended actions; never touches real input.
- ``LiveActuator`` — uses ``win32clipboard`` + ``ctypes.SendInput`` to send
  real keyboard/mouse input. **Guarded behind DRY_RUN flag.**
- ``new_actuator()`` factory — returns DryRunActuator when DRY_RUN is True.

All coordinate math is relative to the Weixin window rect obtained from
``WeixinCapture.get_rect()``.
"""

from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass
from typing import Protocol

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


class Actuator(Protocol):
    """Minimal protocol that ``bot_core.Bot`` depends on.

    Implementations must provide these three methods.  The protocol is
    intentionally minimal so it can be satisfied by simple recorders or
    full live actuators.
    """

    def open_conversation(self, y: int) -> None:
        """Click on a chat-list row at pixel *y* (absolute window Y)."""
        ...

    def focus_input(self) -> None:
        """Click into the message input box at the bottom of the chat area."""
        ...

    def send_text(self, text: str) -> None:
        """Type *text* into the input box and send it (typically Ctrl+Enter or paste
        then Enter)."""
        ...


# ---------------------------------------------------------------------------
# Dry-run (recording) actuator
# ---------------------------------------------------------------------------


@dataclass
class ActionRecord:
    method: str
    args: tuple
    ts: float


class DryRunActuator:
    """Logs intended actions; never touches the real mouse/keyboard.

    Useful for testing and dry-run verification.  Every call is recorded
    in ``self.actions`` as ``(method_name, args)`` tuples.
    """

    def __init__(self) -> None:
        self.actions: list[tuple[str, object]] = []

    def open_conversation(self, y: int) -> None:
        logger.info("[DRY] open_conversation y=%d", y)
        self.actions.append(("open", y))

    def focus_input(self) -> None:
        logger.info("[DRY] focus_input")
        self.actions.append(("focus_input", None))

    def send_text(self, text: str) -> None:
        logger.info("[DRY] send_text would send: %.60s", text)
        self.actions.append(("send", text))


# ---------------------------------------------------------------------------
# Live (real input) actuator — guarded
# ---------------------------------------------------------------------------

try:
    import ctypes
    import ctypes.wintypes

    import win32clipboard
    import win32con
    import win32gui
except ImportError:
    ctypes = None  # type: ignore[assignment]
    win32clipboard = None  # type: ignore[assignment]
    win32gui = None  # type: ignore[assignment]
    win32con = None  # type: ignore[assignment]

# Virtual-key codes used by SendInput
_VK_CONTROL = 0x11
_VK_V = 0x56
_VK_RETURN = 0x0D

# INPUT type constants
_INPUT_KEYBOARD = 1
_KEYEVENTF_KEYUP = 0x0002


def _log_normal_delay(mean_ms: float = 120, sigma: float = 0.4) -> float:
    """Sample a human-like delay from a log-normal distribution.

    Args:
        mean_ms: Mean delay in milliseconds.
        sigma: Shape parameter (~0.4 gives 1.5× spread).

    Returns:
        Delay in seconds.
    """
    return random.lognormvariate(mean_ms / 1000, sigma)


def _bezier_path(
    x0: int, y0: int, x1: int, y1: int, steps: int = 10,
) -> list[tuple[int, int]]:
    """Generate a simple quadratic bezier curve from (x0,y0) to (x1,y1).

    The control point is offset perpendicular to the line, giving a gentle
    arc that looks more human than a straight line.
    """
    cx = (x0 + x1) // 2 + random.randint(-10, 10)
    cy = (y0 + y1) // 2 - random.randint(20, 60)  # arc upward
    pts: list[tuple[int, int]] = []
    for t in range(steps + 1):
        u = t / steps
        # Quadratic: B(t) = (1-t)² P0 + 2(1-t)t P1 + t² P2
        x = int((1 - u) ** 2 * x0 + 2 * (1 - u) * u * cx + u ** 2 * x1)
        y = int((1 - u) ** 2 * y0 + 2 * (1 - u) * u * cy + u ** 2 * y1)
        pts.append((x, y))
    return pts


class LiveActuator:
    """Real input actuator using ``win32clipboard`` + ``ctypes.SendInput``.

    Requires an active Weixin window (obtained via ``WeixinCapture``).

    **Humanisation features:**
    - Log-normal delays between sub-actions.
    - Optional bezier mouse path for clicks (controlled by ``bezier`` flag).
    - Text is pasted via Ctrl+V (supports arbitrary-length Unicode) and sent
      with a programmatic Enter key-down/up pair.

    Args:
        window_rect: ``(left, top, right, bottom)`` of the Weixin window
            (obtainable from ``WeixinCapture.get_rect()``).
        bezier: If True, mouse moves follow a bezier arc. Default True.
    """

    def __init__(
        self,
        window_rect: tuple[int, int, int, int],
        bezier: bool = True,
    ) -> None:
        if ctypes is None or win32clipboard is None:
            raise RuntimeError(
                "LiveActuator requires pywin32 (win32clipboard) and ctypes. "
                "Install with: pip install pywin32"
            )
        self._rect = window_rect
        self._bezier = bezier
        self._left, self._top, self._right, self._bottom = window_rect

    # ---- internal helpers ----

    def _screen_xy(self, rel_x: float, rel_y: float) -> tuple[int, int]:
        """Convert relative (0..1) coords inside the client area to screen pixels."""
        w = self._right - self._left
        h = self._bottom - self._top
        return self._left + int(w * rel_x), self._top + int(h * rel_y)

    def _click_at(self, screen_x: int, screen_y: int) -> None:
        """Move the cursor to (screen_x, screen_y) and click left button.

        The mouse path uses either a bezier arc (if ``self._bezier``) or a
        straight line. Each movement step is paced with a log-normal delay.
        """
        old_pos = ctypes.wintypes.POINT()
        ctypes.windll.user32.GetCursorPos(ctypes.byref(old_pos))

        if self._bezier:
            path = _bezier_path(old_pos.x, old_pos.y, screen_x, screen_y)
        else:
            path = [(screen_x, screen_y)]

        for px, py in path:
            ctypes.windll.user32.SetCursorPos(px, py)
            time.sleep(_log_normal_delay(40))

        # Mouse down + up
        ctypes.windll.user32.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        time.sleep(_log_normal_delay(30, 0.3))
        ctypes.windll.user32.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        time.sleep(_log_normal_delay(80))

    def _send_key(self, vk_code: int) -> None:
        """Press and release a single virtual key via SendInput."""
        extra = ctypes.c_ulong(0)
        for flags in (0, _KEYEVENTF_KEYUP):
            inp = ctypes.wintypes.INPUT()
            inp.type = _INPUT_KEYBOARD
            inp.ki.wVk = vk_code
            inp.ki.dwFlags = flags
            ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))
            time.sleep(_log_normal_delay(30, 0.3))

    # ---- public API ----

    def open_conversation(self, y: int) -> None:
        """Click on a chat-list row at pixel *y* (absolute window Y)."""
        # Estimate X center of the chat list (roughly left 30 % of window width)
        w = self._right - self._left
        x = self._left + int(w * 0.15)
        screen_y = self._top + y
        logger.info(
            "[LIVE] open_conversation y=%d -> screen=(%d, %d)",
            y, x, screen_y,
        )
        self._click_at(x, screen_y)

    def focus_input(self) -> None:
        """Click into the message input box (bottom ~15 % of window)."""
        h = self._bottom - self._top
        w = self._right - self._left
        # Input box is roughly in the lower third, left half
        x = self._left + int(w * 0.25)
        screen_y = self._top + int(h * 0.85)
        logger.info("[LIVE] focus_input -> screen=(%d, %d)", x, screen_y)
        self._click_at(x, screen_y)

    def send_text(self, text: str) -> None:
        """Paste *text* into the input box and press Enter to send.

        Steps:
        1. Copy *text* to the clipboard.
        2. Send Ctrl+V.
        3. Send Enter.
        """
        # 1. Clipboard
        win32clipboard.OpenClipboard()
        try:
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardText(text, win32clipboard.CF_UNICODETEXT)
        finally:
            win32clipboard.CloseClipboard()

        time.sleep(_log_normal_delay(60))

        logger.info("[LIVE] send_text: %.80s", text)

        # 2. Ctrl+V
        ctypes.windll.user32.keybd_event(_VK_CONTROL, 0, 0, 0)
        ctypes.windll.user32.keybd_event(_VK_V, 0, 0, 0)
        time.sleep(_log_normal_delay(40))
        ctypes.windll.user32.keybd_event(_VK_V, 0, _KEYEVENTF_KEYUP, 0)
        ctypes.windll.user32.keybd_event(_VK_CONTROL, 0, _KEYEVENTF_KEYUP, 0)

        time.sleep(_log_normal_delay(100))

        # 3. Enter to send
        self._send_key(_VK_RETURN)
        time.sleep(_log_normal_delay(200))


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def new_actuator(dry_run: bool = True, **kwargs) -> Actuator:
    """Return a DryRunActuator or LiveActuator based on *dry_run*.

    When *dry_run* is True (the default), returns a ``DryRunActuator``.
    When False, attempts to create a ``LiveActuator`` — you must provide
    the ``window_rect`` keyword argument.

    Args:
        dry_run: If True (default), return a dry-run recorder.
        **kwargs: Forwarded to ``LiveActuator`` when *dry_run* is False.

    Returns:
        An Actuator-compatible instance.

    Raises:
        ValueError: If *dry_run* is False but no ``window_rect`` is provided.
    """
    if dry_run:
        return DryRunActuator()

    window_rect = kwargs.get("window_rect")
    if window_rect is None:
        raise ValueError(
            "LiveActuator requires window_rect=(left, top, right, bottom). "
            "Pass it as e.g. new_actuator(dry_run=False, window_rect=rect)."
        )
    return LiveActuator(
        window_rect=window_rect,
        bezier=kwargs.get("bezier", True),
    )