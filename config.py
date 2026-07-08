"""Configuration management for WeChat Smart Bot.

Typed settings loaded from .env with sensible defaults.
All new features are gated behind DRY_RUN=True and MODE=SUGGEST.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from project root
PROJECT_ROOT = Path(__file__).parent
load_dotenv(PROJECT_ROOT / ".env")


def _bool_from_env(key: str, default: bool) -> bool:
    val = os.getenv(key, str(default)).strip().lower()
    return val in ("1", "true", "yes", "on")


def _parse_business_hours(raw: str) -> tuple[int, int]:
    """Parse 'HH:MM-HH:MM' into (start_minutes, end_minutes).
    Returns (540, 1320) = 09:00-22:00 on failure."""
    try:
        parts = raw.split("-")
        start_h, start_m = parts[0].strip().split(":")
        end_h, end_m = parts[1].strip().split(":")
        return int(start_h) * 60 + int(start_m), int(end_h) * 60 + int(end_m)
    except (ValueError, IndexError):
        return 540, 1320


class Config:
    """Central configuration — extend with new typed fields here.
    All values fall back to .env, then to sensible defaults.
    """

    # ---- Identity ----
    BOT_ACCOUNT: str = os.getenv("BOT_ACCOUNT", "NeXTSCENE小助手")
    BOT_NAME: str = os.getenv("BOT_NAME", BOT_ACCOUNT)
    MONITOR_ACCOUNT: str = os.getenv("MONITOR_ACCOUNT", "musomuso")

    # ---- SenseNova LLM ----
    SENSENOVA_API_KEY: str = os.getenv("SENSENOVA_API_KEY", "")
    SENSENOVA_BASE_URL: str = os.getenv("SENSENOVA_BASE_URL", "https://token.sensenova.cn/v1")
    SENSENOVA_MODEL: str = os.getenv("SENSENOVA_MODEL", "sense-chat")

    # ---- Bot behaviour ----
    MODE: str = os.getenv("MODE", "SUGGEST")  # SUGGEST | SEND
    DRY_RUN: bool = _bool_from_env("DRY_RUN", True)
    SCAN_INTERVAL: int = int(os.getenv("SCAN_INTERVAL", "5"))
    MAX_CONTEXT_ROUNDS: int = int(os.getenv("MAX_CONTEXT_ROUNDS", "10"))

    # ---- Persona ----
    PERSONA_PROMPT: str = os.getenv(
        "PERSONA_PROMPT",
        "你是 NeXT SCENE 的小助手，一个真人客服。回复简短自然（1-2句），语气亲切，"
        "可用'嗯嗯/好的/哈哈'。不暴露 AI 身份。不确定就说'我看看'/'稍等我确认下'。"
        "不主动给选项菜单。涉及报价/合同/投诉/退款/赔偿/律师就说'这个我确认后回复您'并转人工。",
    )

    # ---- Skip / filter ----
    SKIP_NAMES: list[str] = [
        n.strip() for n in os.getenv("SKIP_NAMES", "").split(",") if n.strip()
    ] or ["文件传输助手", "微信团队", "腾讯公司", "服务通知", "订阅号消息"]
    GROUP_MARKERS: list[str] = [
        n.strip() for n in os.getenv("GROUP_MARKERS", "群聊,群,Group,").split(",") if n.strip()
    ]

    # ---- Sensitivity ----
    SENSITIVE_KEYWORDS: list[str] = [
        kw.strip()
        for kw in os.getenv(
            "SENSITIVE_KEYWORDS",
            "投诉,退款,赔偿,合同,报价,法律,律师,付款,发票,金额,收费,价格,终止,解约,"
            "解除,严重问题,投诉电话,12315,起诉,诉讼,负面,差评",
        ).split(",")
        if kw.strip()
    ]
    # Backward-compat alias
    CRITICAL_KEYWORDS: list[str] = SENSITIVE_KEYWORDS

    # ---- Business hours (HH:MM-HH:MM) ----
    _BUSINESS_HOURS_RAW: str = os.getenv("BUSINESS_HOURS", "09:00-22:00")
    BUSINESS_HOURS: tuple[int, int] = _parse_business_hours(_BUSINESS_HOURS_RAW)

    # ---- Database ----
    DB_PATH: str = str(PROJECT_ROOT / "data" / "bot.db")

    # ---- Knowledge base ----
    KB_PATH: str = str(PROJECT_ROOT / "knowledge_base.md")

    # ---- System Prompt (legacy, kept for compat) ----
    SYSTEM_PROMPT: str = """你是一个专业的微信客服助手。请根据以下规则回复：

1. 保持礼貌、专业、简洁
2. 如果涉及价格/报价问题，回复："这个我稍后为您确认，请稍等"
3. 如果不确定能否处理，回复："这个问题我需要确认后回复您"
4. 不要编造不确定的信息
5. 用中文回复，语气亲切自然
6. 不要暴露你是AI助手"""


def load_knowledge_base() -> str:
    """Load the business knowledge base (facts the bot may rely on). Empty if missing."""
    path = Path(Config.KB_PATH)
    try:
        return path.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return ""


def validate_config() -> list[str]:
    """Validate config and return a list of error messages (empty = valid)."""
    errors: list[str] = []
    if not Config.SENSENOVA_API_KEY:
        errors.append("SENSENOVA_API_KEY is not set in .env")
    if not Config.MONITOR_ACCOUNT:
        errors.append("MONITOR_ACCOUNT is not set in .env")
    if Config.MODE not in ("SUGGEST", "SEND"):
        errors.append(f"MODE must be SUGGEST or SEND, got {Config.MODE!r}")
    if Config.SCAN_INTERVAL < 1:
        errors.append(f"SCAN_INTERVAL must be >= 1, got {Config.SCAN_INTERVAL}")
    return errors