"""Configuration management for WeChat Smart Bot."""

import os
from pathlib import Path

# Load .env from project root if python-dotenv is available. Optional so the
# config (and the whole test suite) works in a lean environment without it.
PROJECT_ROOT = Path(__file__).parent
try:
    from dotenv import load_dotenv

    load_dotenv(PROJECT_ROOT / ".env")
except Exception:
    pass


class Config:
    """Central configuration loaded from .env file."""

    # WeChatFerry
    WECHAT_ACCOUNT_WXID: str = os.getenv("WECHAT_ACCOUNT_WXID", "")

    # Monitoring Account
    MONITOR_ACCOUNT_NAME: str = os.getenv("MONITOR_ACCOUNT_NAME", "")

    # SenseNova LLM
    SENSENOVA_API_KEY: str = os.getenv("SENSENOVA_API_KEY", "")
    SENSENOVA_BASE_URL: str = os.getenv("SENSENOVA_BASE_URL", "https://token.sensenova.cn/v1")
    SENSENOVA_MODEL: str = os.getenv("SENSENOVA_MODEL", "sense-chat")
    # Reasoning models (e.g. sensenova-6.7-flash-lite) spend ~1500+ tokens on hidden
    # reasoning before emitting content — the budget must be generous or content is None.
    LLM_MAX_TOKENS: int = int(os.getenv("LLM_MAX_TOKENS", "2048"))

    # Bot Settings
    BOT_NAME: str = os.getenv("BOT_NAME", "")
    MAX_CONTEXT_ROUNDS: int = int(os.getenv("MAX_CONTEXT_ROUNDS", "10"))
    REPLY_DELAY_MIN: float = float(os.getenv("REPLY_DELAY_MIN", "1"))
    REPLY_DELAY_MAX: float = float(os.getenv("REPLY_DELAY_MAX", "3"))

    # Critical Keywords
    CRITICAL_KEYWORDS: list[str] = [
        kw.strip()
        for kw in os.getenv("CRITICAL_KEYWORDS", "投诉,退款,赔偿,法律,律师").split(",")
        if kw.strip()
    ]

    # Database
    DB_PATH: str = str(PROJECT_ROOT / "data" / "bot.db")

    # System Prompt for LLM
    SYSTEM_PROMPT: str = """你是一个专业的微信客服助手。请根据以下规则回复：

1. 保持礼貌、专业、简洁
2. 如果涉及价格/报价问题，回复："这个我稍后为您确认，请稍等"
3. 如果不确定能否处理，回复："这个问题我需要确认后回复您"
4. 不要编造不确定的信息
5. 用中文回复，语气亲切自然
6. 不要暴露你是AI助手"""

    # ------------------------------------------------------------------
    # Vision-automation engine settings (personal-account bot on Weixin 4.x)
    # ------------------------------------------------------------------
    # Account the bot drives, and where it forwards everything for review.
    BOT_ACCOUNT: str = os.getenv("BOT_ACCOUNT", "NeXTSCENE小助手")
    MONITOR_ACCOUNT: str = os.getenv(
        "MONITOR_ACCOUNT", os.getenv("MONITOR_ACCOUNT_NAME", "musomuso")
    )

    # Conversations to never auto-handle (self, bots, official accounts).
    SKIP_NAMES: list[str] = [
        s.strip() for s in os.getenv(
            "SKIP_NAMES",
            "微信团队,文件传输助手,订阅号,服务号,公众号,微信支付,微信运动,NeXTSCENE小助手",
        ).split(",") if s.strip()
    ]
    # Heuristic markers that a conversation is a group (skip groups by default).
    GROUP_MARKERS: list[str] = [
        s.strip() for s in os.getenv("GROUP_MARKERS", "群,沙龙,交流,峰会,大会,社区").split(",")
        if s.strip()
    ]
    # Messages containing these route to human confirmation instead of auto-reply.
    SENSITIVE_KEYWORDS: list[str] = [
        s.strip() for s in os.getenv(
            "SENSITIVE_KEYWORDS",
            "投诉,退款,赔偿,法律,律师,合同,报价,价格,费用,多少钱,发票,付款,定金",
        ).split(",") if s.strip()
    ]

    BUSINESS_HOURS: tuple[int, int] = (
        int(os.getenv("BUSINESS_HOUR_START", "9")),
        int(os.getenv("BUSINESS_HOUR_END", "22")),
    )
    SCAN_INTERVAL: float = float(os.getenv("SCAN_INTERVAL", "5"))

    # SAFETY: dry-run by default. The bot NEVER sends unless this is explicitly
    # disabled AND MODE == 'SEND' AND the safety envelope allows it.
    DRY_RUN: bool = os.getenv("DRY_RUN", "true").lower() not in ("0", "false", "no")
    MODE: str = os.getenv("BOT_MODE", "SUGGEST")  # SUGGEST | SEND

    SUGGESTIONS_PATH: str = str(PROJECT_ROOT / "data" / "suggestions.jsonl")

    # Natural-person persona (channel 2). Never expose AI identity.
    PERSONA_PROMPT: str = os.getenv("PERSONA_PROMPT", """你是一个真人在回复微信消息。请注意：
1. 绝对不要暴露你是 AI 或机器人，不要说"作为AI助手"之类的话
2. 语气自然，像朋友聊天，简短（一般 1-2 句）
3. 可以用"嗯嗯""好的""哈哈"等口语
4. 不确定时说"我看看""稍等我确认下"，绝不编造信息
5. 不主动给选项菜单""")


def load_knowledge_base() -> str:
    """Load the business knowledge base (facts the bot may rely on). Empty if missing."""
    kb = PROJECT_ROOT / "knowledge_base.md"
    try:
        return kb.read_text(encoding="utf-8")
    except Exception:
        return ""


def validate_config() -> bool:
    """Validate that required config values are set."""
    errors = []
    if not Config.SENSENOVA_API_KEY:
        errors.append("SENSENOVA_API_KEY is not set in .env")
    if not Config.MONITOR_ACCOUNT_NAME:
        errors.append("MONITOR_ACCOUNT_NAME is not set in .env")
    if not Config.BOT_NAME:
        errors.append("BOT_NAME is not set in .env")

    if errors:
        for e in errors:
            print(f"[CONFIG ERROR] {e}")
        return False
    return True
