"""SuggestionStore: insert, dedup by (contact, incoming), jsonl mirror."""

from store import SuggestionStore


def test_add_dedup_and_jsonl(tmp_path):
    s = SuggestionStore(tmp_path / "bot.db", tmp_path / "sug.jsonl", clock=lambda: 100.0)
    assert s.add("蒋智华", "你好", "嗨") is True
    assert s.add("蒋智华", "你好", "嗨(again)") is False   # dup on (contact, incoming)
    assert s.add("别人", "你好", "嗨") is True               # different contact → new
    assert s.add("蒋智华", "另一句", "回复") is True          # same contact, new text → new
    assert s.count() == 3

    lines = (tmp_path / "sug.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 3  # duplicates are NOT mirrored to jsonl


def test_needs_confirmation_persisted(tmp_path):
    s = SuggestionStore(tmp_path / "b.db", tmp_path / "s.jsonl")
    assert s.add("客户", "报价多少", "稍等确认", needs_confirmation=True, reason="命中敏感词") is True
    import json
    rec = json.loads((tmp_path / "s.jsonl").read_text(encoding="utf-8").strip())
    assert rec["needs_confirmation"] is True and rec["reason"] == "命中敏感词"
