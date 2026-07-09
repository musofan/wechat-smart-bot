"""Robustness utilities — blank-frame detection, window fallback helpers.

Used by the orchestrator to gracefully handle edge cases without crashing.
"""

from __future__ import annotations

import logging

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

# Thresholds for blank-frame detection
_BLANK_STDDEV_THRESHOLD = 5.0   # StdDev below this → blank
_BLANK_MEAN_THRESHOLD = 240.0   # Mean pixel value above this → near-white (minimized/blank)
_BLANK_DIM_THRESHOLD = 15.0     # Mean pixel value below this → near-black

# Maximum area fraction allowed for a single color dominating
_MAX_SOLID_FRACTION = 0.98


def is_blank_frame(img: Image.Image) -> bool:
    """Detect if a captured frame is blank (all-black, all-white, or a solid color).

    Returns:
        True if the frame appears blank/unusable.
    """
    if img is None or img.size[0] < 2 or img.size[1] < 2:
        return True

    arr = np.asarray(img.convert("L"), dtype=np.float32)

    mean_val = float(arr.mean())
    std_val = float(arr.std())

    # Near-black (window minimized / hidden)
    if mean_val < _BLANK_DIM_THRESHOLD and std_val < _BLANK_STDDEV_THRESHOLD:
        logger.debug("blank-frame: near-black (mean=%.1f, std=%.1f)", mean_val, std_val)
        return True

    # Near-white (window minimized to white / empty)
    if mean_val > _BLANK_MEAN_THRESHOLD and std_val < _BLANK_STDDEV_THRESHOLD:
        logger.debug("blank-frame: near-white (mean=%.1f, std=%.1f)", mean_val, std_val)
        return True

    # Solid color (single color dominating the frame)
    hist = np.histogram(arr, bins=256, range=(0, 255))[0]
    max_bin = float(hist.max())
    total_pixels = float(hist.sum())
    if total_pixels > 0 and (max_bin / total_pixels) > _MAX_SOLID_FRACTION:
        logger.debug(
            "blank-frame: solid color (%.1f%% pixels in one bin)",
            max_bin / total_pixels * 100,
        )
        return True

    return False


def capture_with_retry(capture_fn, max_retries: int = 2) -> tuple[Image.Image | None, str | None]:
    """Attempt to capture, retrying on blank frames.

    Args:
        capture_fn: Zero-arg callable returning a PIL Image.
        max_retries: Number of retries on blank frames.

    Returns:
        (image, None) on success; (None, error_message) on failure.
    """
    for attempt in range(1 + max_retries):
        try:
            img = capture_fn()
        except Exception as exc:
            if attempt < max_retries:
                logger.warning("capture attempt %d failed: %s; retrying", attempt + 1, exc)
                continue
            return None, str(exc)

        if not is_blank_frame(img):
            return img, None

        if attempt < max_retries:
            logger.warning("capture attempt %d returned blank frame; retrying", attempt + 1)
            continue

    return None, "All capture attempts returned blank frames"


def ensure_window(capture) -> str | None:
    """Ensure the Weixin window is available and not minimized.

    Returns:
        None if OK; an error string if the window cannot be used.
    """
    try:
        hwnd = capture.ensure_window()
        if capture.is_minimized():
            # Try to restore
            try:
                capture.capture(restore_if_minimized=True)
            except Exception as exc:
                return f"Window is minimized and cannot be restored: {exc}"
        return None
    except Exception as exc:
        return f"Window not found: {exc}"