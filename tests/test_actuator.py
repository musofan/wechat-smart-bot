"""Actuator: DryRun records the intended sequence; Live is never executed."""

import pytest

from wechat_actuator import DryRunActuator, make_actuator


def test_dryrun_records_send_sequence():
    a = DryRunActuator()
    a.open_conversation(300)
    a.focus_input()
    a.send_text("你好")
    assert a.actions == [("open", 300), ("focus_input", None), ("send", "你好")]


def test_make_actuator_defaults_to_dryrun():
    assert isinstance(make_actuator(True), DryRunActuator)
    # dry_run False would build a LiveActuator; don't construct/execute it here.


@pytest.mark.live
def test_live_actuator_constructs():
    from wechat_actuator import LiveActuator
    LiveActuator(capture=None)  # construction only; no methods called
