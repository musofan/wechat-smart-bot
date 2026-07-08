"""Config defaults + env overrides. DRY_RUN must default True (safety)."""

import importlib


def test_safe_defaults():
    import config
    importlib.reload(config)
    assert config.Config.DRY_RUN is True, "DRY_RUN must default to True"
    assert config.Config.MODE == "SUGGEST"
    assert config.Config.MONITOR_ACCOUNT  # non-empty default
    assert config.Config.BOT_ACCOUNT
    assert len(config.Config.SENSITIVE_KEYWORDS) > 0
    assert isinstance(config.Config.BUSINESS_HOURS, tuple)


def test_env_override(monkeypatch):
    monkeypatch.setenv("DRY_RUN", "false")
    monkeypatch.setenv("BOT_MODE", "SEND")
    import config
    importlib.reload(config)
    try:
        assert config.Config.DRY_RUN is False
        assert config.Config.MODE == "SEND"
    finally:
        monkeypatch.undo()
        importlib.reload(config)  # restore module state for other tests


def test_load_knowledge_base_returns_str():
    import config
    importlib.reload(config)
    kb = config.load_knowledge_base()
    assert isinstance(kb, str)
