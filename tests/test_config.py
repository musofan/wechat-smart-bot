"""Tests for config surface — typed settings, env overrides, defaults."""

from config import Config, _bool_from_env, _parse_business_hours, validate_config


class TestCoreDefaults:
    """Default values when .env is not set (only OS env vars)."""

    def test_dry_run_defaults_true(self):
        # DRY_RUN should default to True
        assert Config.DRY_RUN is True

    def test_mode_defaults_suggest(self):
        assert Config.MODE == "SUGGEST"

    def test_monitor_account_default(self):
        assert Config.MONITOR_ACCOUNT == "musomuso"

    def test_bot_account_default(self):
        assert Config.BOT_ACCOUNT == "NeXTSCENE小助手"

    def test_scan_interval_default(self):
        assert Config.SCAN_INTERVAL == 5

    def test_persona_prompt_not_empty(self):
        assert len(Config.PERSONA_PROMPT) > 20

    def test_skip_names_has_known_entries(self):
        assert "文件传输助手" in Config.SKIP_NAMES
        assert "微信团队" in Config.SKIP_NAMES

    def test_sensitive_keywords_has_core_terms(self):
        assert "投诉" in Config.SENSITIVE_KEYWORDS
        assert "退款" in Config.SENSITIVE_KEYWORDS
        assert "合同" in Config.SENSITIVE_KEYWORDS

    def test_business_hours_default(self):
        assert Config.BUSINESS_HOURS == (540, 1320)  # 09:00-22:00

    def test_critical_keywords_alias(self):
        assert Config.CRITICAL_KEYWORDS is Config.SENSITIVE_KEYWORDS


class TestBoolFromEnv:
    def test_true_values(self, monkeypatch):
        for v in ("1", "true", "TRUE", "yes", "on"):
            monkeypatch.setenv("_TEST_BOOL", v)
            assert _bool_from_env("_TEST_BOOL", False) is True

    def test_false_values(self, monkeypatch):
        for v in ("0", "false", "no", "off", ""):
            monkeypatch.setenv("_TEST_BOOL", v)
            assert _bool_from_env("_TEST_BOOL", True) is False

    def test_default_when_unset(self):
        # No env var — should return the passed default
        assert _bool_from_env("_THIS_VAR_DOES_NOT_EXIST_12345", True) is True
        assert _bool_from_env("_THIS_VAR_DOES_NOT_EXIST_12345", False) is False


class TestParseBusinessHours:
    def test_standard(self):
        assert _parse_business_hours("09:00-22:00") == (540, 1320)

    def test_midnight(self):
        assert _parse_business_hours("00:00-23:59") == (0, 1439)

    def test_invalid_falls_back(self):
        assert _parse_business_hours("") == (540, 1320)
        assert _parse_business_hours("garbage") == (540, 1320)


class TestValidateConfig:
    def test_validate_mode_invalid(self, monkeypatch):
        monkeypatch.setattr(Config, "MODE", "INVALID")
        errors = validate_config()
        assert any("MODE" in e for e in errors)

    def test_validate_scan_interval_too_small(self, monkeypatch):
        monkeypatch.setattr(Config, "SCAN_INTERVAL", 0)
        errors = validate_config()
        assert any("SCAN_INTERVAL" in e for e in errors)

    def test_validate_dry_run_stays_true_on_invalid_mode(self, monkeypatch):
        monkeypatch.setattr(Config, "MODE", "INVALID")
        errors = validate_config()
        assert len(errors) > 0
        # DRY_RUN itself has no validation; it should remain True as default
        assert Config.DRY_RUN is True
