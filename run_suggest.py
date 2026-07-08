"""Suggest-only entrypoint. Reads conversations and writes drafted (un-sent)
replies for review. Sends NOTHING and clicks NOTHING.

Usage:
  python run_suggest.py --once                 # handle the currently-open chat once (live)
  python run_suggest.py --frames data/frames   # replay saved .png frames (offline, safe)
"""

from __future__ import annotations

import argparse
import glob
import os

from PIL import Image


def run_frames(bot, frames_dir: str, log=print) -> int:
    """Replay saved PNG frames through the bot. Returns number of suggestions made."""
    n = 0
    for path in sorted(glob.glob(os.path.join(frames_dir, "*.png"))):
        img = Image.open(path).convert("RGB")
        sug = bot.handle_open_conversation(img)
        if sug:
            n += 1
            flag = "  ⚠需确认" if sug.needs_confirmation else ""
            log(f"[SUGGEST] {sug.contact}: {sug.incoming!r} -> {sug.draft_reply!r}{flag}")
    return n


def build_live_bot():
    """Wire the real components for live suggest-mode (no sending)."""
    from types import SimpleNamespace

    import llm_client
    from bot_core import Bot
    from config import Config, load_knowledge_base
    from database import get_conversation_history, init_db
    from reply_engine import ReplyEngine
    from store import SuggestionStore
    from wechat_reader import WeixinReader
    from wechat_vision import WeixinVision

    init_db()
    vision = WeixinVision()
    reader = WeixinReader(vision)
    llm = SimpleNamespace(
        generate_reply=llm_client.generate_reply,
        classify_message=llm_client.classify_message,
    )
    engine = ReplyEngine(
        llm, knowledge_base=load_knowledge_base(),
        persona=Config.PERSONA_PROMPT, sensitive_keywords=Config.SENSITIVE_KEYWORDS,
    )
    store = SuggestionStore(Config.DB_PATH, Config.SUGGESTIONS_PATH)
    return Bot(vision, reader, engine, store, Config,
               history_fn=lambda c: get_conversation_history(c))


def run_once_live(log=print) -> int:
    """Capture the current window and handle the OPEN conversation once (no clicks)."""
    from wechat_capture import WeixinCapture
    bot = build_live_bot()
    cap = WeixinCapture()
    if not cap.find_window():
        log("[FATAL] Weixin window not found (open it, not minimized).")
        return 0
    full = cap.capture()
    unread = bot.scan_unread(full)
    log(f"[SCAN] unread (non-skipped) conversations: {[c.name for c in unread]}")
    sug = bot.handle_open_conversation(full)
    if sug:
        log(f"[SUGGEST] {sug.contact}: {sug.incoming!r} -> {sug.draft_reply!r}"
            f"{'  ⚠需确认' if sug.needs_confirmation else ''}")
        return 1
    log("[INFO] No fresh inbound in the open conversation.")
    return 0


def main():
    ap = argparse.ArgumentParser(description="WeChat suggest-only bot (no sending)")
    ap.add_argument("--frames", help="replay .png frames from this dir (offline)")
    ap.add_argument("--once", action="store_true", help="handle the open chat once (live)")
    args = ap.parse_args()

    if args.frames:
        bot = build_live_bot()
        n = run_frames(bot, args.frames)
        print(f"[DONE] {n} suggestion(s) from frames in {args.frames}. Sent nothing.")
    elif args.once:
        run_once_live()
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
