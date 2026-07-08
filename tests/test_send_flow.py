"""Guarded SEND path: nothing goes out under safe defaults; the gates all hold."""

from types import SimpleNamespace

from bot_core import Bot, Suggestion


class RecActuator:
    def __init__(self):
        self.actions = []

    def focus_input(self):
        self.actions.append(("focus_input", None))

    def send_text(self, t):
        self.actions.append(("send", t))


class AllowSafety:
    def can_send(self):
        return True, "ok"

    def record_send(self):
        pass


class BlockSafety:
    def can_send(self):
        return False, "outside business hours"

    def record_send(self):
        pass


def _bot(mode, dry, actuator):
    cfg = SimpleNamespace(MODE=mode, DRY_RUN=dry, SKIP_NAMES=[], GROUP_MARKERS=[])
    return Bot(None, None, None, None, cfg, actuator=actuator)


def _sug(needs=False):
    return Suggestion("客户", "在吗", "你好", needs, "命中报价" if needs else "")


def test_no_send_when_dry_run():
    a = RecActuator()
    sent, why = _bot("SEND", True, a).send_reply(_sug(), AllowSafety())
    assert sent is False and "DRY_RUN" in why
    assert a.actions == []


def test_no_send_in_suggest_mode():
    a = RecActuator()
    sent, _ = _bot("SUGGEST", False, a).send_reply(_sug(), AllowSafety())
    assert sent is False and a.actions == []


def test_sends_when_enabled_and_safe():
    a = RecActuator()
    sent, _ = _bot("SEND", False, a).send_reply(_sug(), AllowSafety())
    assert sent is True and ("send", "你好") in a.actions


def test_blocks_when_needs_confirmation():
    a = RecActuator()
    sent, why = _bot("SEND", False, a).send_reply(_sug(needs=True), AllowSafety())
    assert sent is False and "confirm" in why and a.actions == []


def test_blocks_when_safety_denies():
    a = RecActuator()
    sent, _ = _bot("SEND", False, a).send_reply(_sug(), BlockSafety())
    assert sent is False and a.actions == []


def test_parse_monitor_command():
    assert Bot.parse_monitor_command("1") == {"action": "approve"}
    assert Bot.parse_monitor_command("2 换个说法") == {"action": "custom", "text": "换个说法"}
    assert Bot.parse_monitor_command("3") == {"action": "skip"}
    assert Bot.parse_monitor_command("hi") == {"action": "none"}
