"""SuggestionStore: insert, dedup, jsonl append (tmp_path)."""

import json
from store import SuggestionStore


def test_init_creates_table():
    store = SuggestionStore(db_path=":memory:")
    store.init()
    # table exists — list_recent should work without error
    assert store.list_recent() == []


def test_insert_and_list():
    store = SuggestionStore(db_path=":memory:")
    store.init()
    ok = store.save("张三", "你好", "您好！", needs_confirmation=False)
    assert ok is True
    recent = store.list_recent()
    assert len(recent) == 1
    r = recent[0]
    assert r["contact"] == "张三"
    assert r["incoming"] == "你好"
    assert r["draft_reply"] == "您好！"
    assert r["needs_confirmation"] == 0
    assert r["status"] == "suggested"
    assert isinstance(r["ts"], float)


def test_dedup_same_contact_and_message():
    store = SuggestionStore(db_path=":memory:")
    store.init()
    ok1 = store.save("张三", "你好", "您好！")
    assert ok1 is True
    ok2 = store.save("张三", "你好", "您好！")
    assert ok2 is False  # duplicate
    assert len(store.list_recent()) == 1


def test_dedup_different_contact_allowed():
    """Same incoming text, different contact — not a duplicate."""
    store = SuggestionStore(db_path=":memory:")
    store.init()
    assert store.save("张三", "你好", "您好！") is True
    assert store.save("李四", "你好", "你好呀！") is True
    assert len(store.list_recent()) == 2


def test_dedup_different_message_allowed():
    store = SuggestionStore(db_path=":memory:")
    store.init()
    assert store.save("张三", "你好", "您好！") is True
    assert store.save("张三", "在吗", "在的") is True
    assert len(store.list_recent()) == 2


def test_exists_check():
    store = SuggestionStore(db_path=":memory:")
    store.init()
    assert store.exists("张三", "你好") is False
    store.save("张三", "你好", "您好！")
    assert store.exists("张三", "你好") is True
    assert store.exists("张三", "在吗") is False


def test_jsonl_append(tmp_path):
    jsonl_file = tmp_path / "suggestions.jsonl"
    store = SuggestionStore(db_path=":memory:", jsonl_path=str(jsonl_file))
    store.init()
    store.save("张三", "你好", "您好！", needs_confirmation=False, reason="")
    store.save("李四", "报价多少", "我确认后回复您", needs_confirmation=True, reason="命中敏感词: 报价")

    lines = jsonl_file.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 2
    rec1 = json.loads(lines[0])
    assert rec1["contact"] == "张三"
    assert rec1["incoming"] == "你好"
    assert rec1["needs_confirmation"] is False
    rec2 = json.loads(lines[1])
    assert rec2["contact"] == "李四"
    assert rec2["needs_confirmation"] is True
    assert rec2["reason"] == "命中敏感词: 报价"


def test_jsonl_no_path_when_not_provided():
    """No jsonl path means no file is written."""
    store = SuggestionStore(db_path=":memory:")
    store.init()
    store.save("张三", "你好", "您好！")
    # no error — just means append is skipped


def test_list_recent_ordered_by_ts_desc():
    import time
    store = SuggestionStore(db_path=":memory:")
    store.init()
    store.save("A", "msg1", "r1")
    time.sleep(0.02)
    store.save("B", "msg2", "r2")
    time.sleep(0.02)
    store.save("C", "msg3", "r3")
    recent = store.list_recent()
    assert len(recent) == 3
    # Most recent first
    assert recent[0]["contact"] == "C"
    assert recent[-1]["contact"] == "A"


def test_save_flag_needs_confirmation():
    store = SuggestionStore(db_path=":memory:")
    store.init()
    store.save("张三", "投诉你", "抱歉我确认下", needs_confirmation=True, reason="投诉")
    recent = store.list_recent()
    assert recent[0]["needs_confirmation"] == 1
    assert recent[0]["reason"] == "投诉"