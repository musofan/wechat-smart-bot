"""READ-ONLY dry-run of the vision engine. Captures the live Weixin window in the
background and prints what it perceives. Sends NOTHING, clicks NOTHING.

Run:  python dryrun_vision.py
"""

import os
import time

from wechat_capture import WeixinCapture
from wechat_vision import WeixinVision, LAYOUT


def main():
    cap = WeixinCapture()
    vis = WeixinVision()

    if not cap.find_window():
        print("[FATAL] Weixin window not found. Open Weixin (not minimized) and retry.")
        return

    rect = cap.get_rect()
    print(f"[WINDOW] hwnd={cap.hwnd} size={rect.width}x{rect.height} "
          f"minimized={cap.is_minimized()}")

    t0 = time.perf_counter()
    full = cap.capture()
    cap_ms = (time.perf_counter() - t0) * 1000
    os.makedirs("data", exist_ok=True)
    full.save("data/dryrun_full.png")
    print(f"[CAPTURE] {full.size} in {cap_ms:.1f}ms -> data/dryrun_full.png (background, no focus steal)")

    # Save region crops for inspection
    for key in ("chat_list", "header", "messages"):
        cap.capture_region(LAYOUT[key], img=full).save(f"data/dryrun_{key}.png")

    print(f"[BADGE] nav-rail unread badge present: {vis.has_nav_badge(full)}")
    unread_ys = vis.detect_unread_rows(full)
    print(f"[BADGE] chat-list rows with red badge at y(full)={unread_ys}")

    print("\n[OCR] Loading RapidOCR (first call downloads/loads models)...")
    t1 = time.perf_counter()
    convs = vis.read_chat_list(full)
    print(f"[OCR] chat list read in {(time.perf_counter()-t1)*1000:.0f}ms; "
          f"{len(convs)} conversations detected:\n")
    for i, c in enumerate(convs[:12]):
        flag = "🔴UNREAD" if c.has_unread else "       "
        snip = (c.snippet[:32] + "…") if len(c.snippet) > 32 else c.snippet
        print(f"  {flag} y={c.y_full:>4}  {c.name[:18]:<18} | {snip}")

    header = vis.read_header(full)
    msgs = vis.read_recent_messages(full)
    print(f"\n[OPEN CHAT] header/contact: {header!r}")
    print(f"[OPEN CHAT] recent messages (last {len(msgs)}):")
    for m in msgs:
        print(f"    · {m}")

    print("\n[DONE] Read-only. Nothing was sent or clicked. "
          "Inspect data/dryrun_*.png for the crops.")


if __name__ == "__main__":
    main()
