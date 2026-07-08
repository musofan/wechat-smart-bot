"""Background capture engine for Weixin 4.x (Qt+CEF+D3D window).

Verified on Weixin 4.1.10.53: PrintWindow(PW_RENDERFULLCONTENT) captures the full
UI even when the window is unfocused or occluded by other windows — no focus
stealing required. Only fails when the window is minimized.

This replaces the old `pyautogui.screenshot(region=...) + bring_to_front()` loop.
"""

from __future__ import annotations

import ctypes
from dataclasses import dataclass

import win32con
import win32gui
import win32ui
from PIL import Image

# Make this process DPI-aware so GetWindowRect / capture sizes are physical pixels
# and match the coordinates we later use for input. Safe to call once at import.
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

PW_RENDERFULLCONTENT = 0x00000002

# Weixin 4.x main window; keep 3.x class as a fallback for older installs.
_WEIXIN_CLASSES = ("Qt51514QWindowIcon", "WeChatMainWndForPC")
_WEIXIN_TITLES = ("微信",)


@dataclass
class Rect:
    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top


class CaptureError(RuntimeError):
    pass


class WeixinCapture:
    """Locates the Weixin main window and captures it in the background."""

    def __init__(self) -> None:
        self._hwnd: int | None = None

    # ---- window location ----
    def find_window(self) -> int | None:
        """Find the Weixin main window handle. Returns hwnd or None."""
        matches: list[int] = []

        def _cb(hwnd, _):
            if not win32gui.IsWindowVisible(hwnd):
                return True
            cls = win32gui.GetClassName(hwnd)
            title = win32gui.GetWindowText(hwnd)
            # main window: Qt class + title 微信 (avoid child/utility windows)
            if cls in _WEIXIN_CLASSES and title in _WEIXIN_TITLES:
                matches.append(hwnd)
            return True

        win32gui.EnumWindows(_cb, None)
        self._hwnd = matches[0] if matches else None
        return self._hwnd

    @property
    def hwnd(self) -> int | None:
        return self._hwnd

    def ensure_window(self) -> int:
        hwnd = self._hwnd or self.find_window()
        if not hwnd:
            raise CaptureError("Weixin main window not found. Is Weixin open and logged in?")
        return hwnd

    def is_minimized(self) -> bool:
        hwnd = self.ensure_window()
        return bool(win32gui.IsIconic(hwnd))

    def get_rect(self) -> Rect:
        hwnd = self.ensure_window()
        l, t, r, b = win32gui.GetWindowRect(hwnd)
        return Rect(l, t, r, b)

    # ---- capture ----
    def capture(self, restore_if_minimized: bool = True) -> Image.Image:
        """Capture the whole Weixin window as a PIL RGB image (background-safe)."""
        hwnd = self.ensure_window()

        if win32gui.IsIconic(hwnd):
            if not restore_if_minimized:
                raise CaptureError("Weixin is minimized; cannot capture client area.")
            # Restore without activating/stealing focus.
            win32gui.ShowWindow(hwnd, win32con.SW_SHOWNOACTIVATE)

        l, t, r, b = win32gui.GetWindowRect(hwnd)
        w, h = r - l, b - t
        if w <= 0 or h <= 0:
            raise CaptureError(f"Weixin window has no client area (size {w}x{h}).")

        hwnd_dc = win32gui.GetWindowDC(hwnd)
        mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
        save_dc = mfc_dc.CreateCompatibleDC()
        bmp = win32ui.CreateBitmap()
        try:
            bmp.CreateCompatibleBitmap(mfc_dc, w, h)
            save_dc.SelectObject(bmp)
            ok = ctypes.windll.user32.PrintWindow(
                hwnd, save_dc.GetSafeHdc(), PW_RENDERFULLCONTENT
            )
            info = bmp.GetInfo()
            bits = bmp.GetBitmapBits(True)
            img = Image.frombuffer(
                "RGB", (info["bmWidth"], info["bmHeight"]), bits, "raw", "BGRX", 0, 1
            )
            if not ok:
                # PrintWindow returned 0 — image may be blank; caller can check.
                pass
            return img
        finally:
            win32gui.DeleteObject(bmp.GetHandle())
            save_dc.DeleteDC()
            mfc_dc.DeleteDC()
            win32gui.ReleaseDC(hwnd, hwnd_dc)

    def capture_region(self, rel: tuple[float, float, float, float],
                       img: Image.Image | None = None) -> Image.Image:
        """Crop a relative (x, y, w, h) box (0..1) from a full-window capture."""
        base = img if img is not None else self.capture()
        W, H = base.size
        x, y, w, h = rel
        box = (int(W * x), int(H * y), int(W * (x + w)), int(H * (y + h)))
        return base.crop(box)

    @staticmethod
    def is_blank(img: Image.Image, mean_threshold: float = 8.0) -> bool:
        """True if a capture looks blank/black. PrintWindow can occasionally return
        a black frame on some GPU compositions; callers should retry when blank."""
        import numpy as np
        return float(np.asarray(img.convert("L")).mean()) < mean_threshold


if __name__ == "__main__":
    import sys
    cap = WeixinCapture()
    if not cap.find_window():
        print("Weixin window not found."); sys.exit(1)
    rect = cap.get_rect()
    print(f"Found Weixin hwnd={cap.hwnd} rect={rect} size={rect.width}x{rect.height} "
          f"minimized={cap.is_minimized()}")
    img = cap.capture()
    out = "data/capture_test.png"
    import os
    os.makedirs("data", exist_ok=True)
    img.save(out)
    print(f"Captured {img.size} -> {out}")
