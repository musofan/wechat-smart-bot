"""SUGGEST-mode entrypoint — loop skeleton that runs Bot.tick() in a loop.

Usage:
    python run_suggest.py                  # live loop (needs unlocked Weixin)
    python run_suggest.py --once           # single tick, then exit
    python run_suggest.py --frames data/   # replay saved images (no live window)
"""

from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path

from bot_core import Bot
from config import Config, load_knowledge_base, validate_config
from reply_engine import ReplyEngine
from store import SuggestionStore
from wechat_capture import WeixinCapture
from wechat_reader import ConversationReader
from wechat_vision import WeixinVision

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ---- stub actuator for dry-run ----

class _DryRunActuator:
    """Logs intended actions; never touches the real mouse/keyboard."""

    def __init__(self):
        self.actions = []

    def open_conversation(self, y):
        logger.info("[DRY] open_conversation y=%d", y)
        self.actions.append(("open", y))

    def send_text(self, text):
        logger.info("[DRY] send_text would send: %.60s", text)
        self.actions.append(("send", text))

    def focus_input(self):
        logger.info("[DRY] focus_input")
        self.actions.append(("focus_input", None))


# ---- stub LLM for dry-run (no API key needed) ----

class _StubLLM:
    """Returns a canned reply when no real LLM client is configured."""

    def __init__(self, reply: str = "您好，有什么可以帮您的？"):
        self.reply = reply

    def generate_reply(self, history, message, system_prompt=None):
        return self.reply

    def classify_message(self, message, history=None):
        return {"needs_confirmation": False, "reason": ""}


def build_bot(db_path: str | None = None) -> Bot:
    """Construct a Bot with all dependencies.

    If SENSENOVA_API_KEY is not set, uses a stub LLM (canned replies).
    The actuator is always dry-run (no real sending).

    Args:
        db_path: Override for the store DB path. Defaults to Config.DB_PATH.
    """
    cfg = Config()

    # Capture + Vision + Reader
    capture = WeixinCapture()
    vision = WeixinVision()
    reader = ConversationReader(vision=vision)

    # LLM — real or stub
    if cfg.SENSENOVA_API_KEY:
        from llm_client import LLMClient
        llm = LLMClient(
            api_key=cfg.SENSENOVA_API_KEY,
            base_url=cfg.SENSENOVA_BASE_URL,
            model=cfg.SENSENOVA_MODEL,
        )
    else:
        logger.warning("No SENSENOVA_API_KEY set — using stub LLM with canned replies")
        llm = _StubLLM()

    engine = ReplyEngine(
        llm=llm,
        knowledge_base=load_knowledge_base(),
        persona=cfg.PERSONA_PROMPT,
        sensitive_keywords=cfg.SENSITIVE_KEYWORDS,
    )

    # Store
    store = SuggestionStore(db_path=db_path or cfg.DB_PATH)
    store.init()

    # Actuator — always dry-run
    actuator = _DryRunActuator()

    return Bot(capture, vision, reader, engine, store, actuator, cfg)


def run_loop(
    bot: Bot,
    interval: int = 5,
    once: bool = False,
    frames_dir: str | None = None,
) -> int:
    """Run the bot loop.

    Args:
        bot: Bot instance.
        interval: Seconds between ticks.
        once: If True, run one tick and exit.
        frames_dir: If set, read .png files from this dir as input instead of live capture.

    Returns:
        Number of ticks executed.
    """
    logger.info(
        "Starting bot (mode=%s, dry_run=%s, interval=%ds, once=%s, frames=%s)",
        Config.MODE, Config.DRY_RUN, interval, once, frames_dir or "live",
    )

    frame_index = 0
    frame_paths: list[Path] = []
    if frames_dir:
        frame_paths = sorted(Path(frames_dir).glob("*.png"))
        if not frame_paths:
            logger.warning("No .png files found in %s", frames_dir)

    tick_count = 0
    while True:
        try:
            if frames_dir and frame_paths:
                if frame_index >= len(frame_paths):
                    if once:
                        break
                    logger.debug("Ran out of frames; sleeping before recycle")
                    time.sleep(interval)
                    continue
                from PIL import Image
                img = Image.open(frame_paths[frame_index])
                frame_index += 1
                results = bot.tick(full_img=img)
            else:
                results = bot.tick()

            tick_count += 1
            unsent = sum(1 for r in results if r.stored)
            total_suggestions = len(bot._store.list_recent())
            logger.info(
                "Tick #%d: %d unread, %d suggested (total %d suggestions)",
                tick_count, len(results), unsent, total_suggestions,
            )

            if once:
                break

            time.sleep(interval)

        except KeyboardInterrupt:
            logger.info("Bot interrupted by user")
            break
        except Exception:
            logger.exception("Unhandled error in tick loop — sleeping and retrying")
            time.sleep(interval * 2)

    return tick_count


def main():
    parser = argparse.ArgumentParser(description="WeChat Smart Bot (SUGGEST mode)")
    parser.add_argument("--once", action="store_true", help="Run one tick and exit")
    parser.add_argument(
        "--frames", type=str, default=None,
        help="Directory of saved .png screenshots to replay (instead of live capture)",
    )
    parser.add_argument(
        "--save-jsonl", type=str, default=None,
        help="Path to save suggestions JSONL (default: data/suggestions.jsonl)",
    )
    args = parser.parse_args()

    # Override JSONL path if requested
    if args.save_jsonl:
        jsonl_path = Path(args.save_jsonl)
    else:
        jsonl_path = Path("data") / "suggestions.jsonl"

    # Validate config
    errors = validate_config()
    if errors:
        for e in errors:
            logger.warning("Config note: %s", e)

    if not Config.DRY_RUN:
        logger.warning("DRY_RUN is False — will log but NOT send in this entrypoint")

    logger.info(
        "Config: MODE=%s DRY_RUN=%s DB=%s KB=%s",
        Config.MODE, Config.DRY_RUN, Config.DB_PATH, Config.KB_PATH,
    )

    # Build bot
    bot = build_bot()
    logger.info("Bot built — using stub reply: '您好，有什么可以帮您的？'")

    # Run loop (capture tick count from return value)
    tick_count = run_loop(
        bot,
        interval=Config.SCAN_INTERVAL,
        once=args.once,
        frames_dir=args.frames,
    )

    # Print summary & write report
    total = len(bot._store.list_recent())
    jsonl_exists = jsonl_path.exists()
    logger.info(
        "Done. %d suggestions in DB. JSONL at %s (exists=%s)",
        total, jsonl_path, jsonl_exists,
    )

    from observability import write_run_report
    write_run_report(
        report_path="data/run_report.md",
        tick_count=tick_count,
        total_scanned=total,
        get_counts_fn=bot._store.get_counts,
    )


if __name__ == "__main__":
    main()