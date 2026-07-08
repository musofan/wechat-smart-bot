"""Review CLI helpers: load, summarize, format."""

import json

from review_suggestions import format_suggestion, load_suggestions, summarize


def _write(p, recs):
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in recs), encoding="utf-8")


def test_load_and_summarize(tmp_path):
    p = tmp_path / "s.jsonl"
    _write(p, [
        {"contact": "a", "incoming": "hi", "draft_reply": "yo", "needs_confirmation": False},
        {"contact": "b", "incoming": "报价多少", "draft_reply": "稍等确认",
         "needs_confirmation": True, "reason": "命中报价"},
    ])
    sug = load_suggestions(str(p))
    assert len(sug) == 2
    assert summarize(sug) == {"total": 2, "needs_confirmation": 1, "auto": 1}
    txt = format_suggestion(2, sug[1])
    assert "需确认" in txt and "命中报价" in txt


def test_load_missing_and_bad_lines(tmp_path):
    assert load_suggestions(str(tmp_path / "nope.jsonl")) == []
    p = tmp_path / "s.jsonl"
    p.write_text('{"contact":"a"}\nnot-json\n\n', encoding="utf-8")
    assert len(load_suggestions(str(p))) == 1  # bad/blank lines skipped
