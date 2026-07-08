"""Safety envelope gates: business hours, min gap, hourly cap, kill-switch."""

from safety import SafetyEnvelope


def _env(tmp_path, hour=12, **kw):
    state = {"t": 1000.0}
    env = SafetyEnvelope(
        clock=lambda: state["t"], hour_of=lambda ts: hour,
        stop_file=str(tmp_path / "STOP"), **kw,
    )
    return env, state


def test_allows_within_hours(tmp_path):
    env, _ = _env(tmp_path)
    ok, why = env.can_send()
    assert ok, why


def test_blocks_outside_hours(tmp_path):
    env, _ = _env(tmp_path, hour=3)
    ok, why = env.can_send()
    assert not ok and "business hours" in why


def test_min_gap(tmp_path):
    env, st = _env(tmp_path, min_gap_s=10)
    assert env.can_send()[0]
    env.record_send()
    st["t"] += 5
    assert not env.can_send()[0]
    st["t"] += 6
    assert env.can_send()[0]


def test_hourly_cap(tmp_path):
    env, _ = _env(tmp_path, per_hour_cap=2, min_gap_s=0)
    env.record_send()
    env.record_send()
    ok, why = env.can_send()
    assert not ok and "cap" in why


def test_kill_switch(tmp_path):
    env, _ = _env(tmp_path)
    (tmp_path / "STOP").write_text("stop", encoding="utf-8")
    ok, why = env.can_send()
    assert not ok and "kill-switch" in why
