"""Configuration management for WeChat Smart Bot."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from project root
PROJECT_ROOT = Path(__file__).parent
load_dotenv(PROJECT_ROOT / ".env")


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
