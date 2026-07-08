"""ReplyEngine: persona+KB reach the prompt; sensitive keywords force confirm."""

from reply_engine import ReplyEngine


def test_draft_injects_persona_and_kb(fake_llm):
    eng = ReplyEngine(fake_llm, knowledge_base="营业时间9到22点", persona="像真人回复")
    reply = eng.draft([], "几点营业")
    assert reply == fake_llm.reply
    sp = fake_llm.last_system_prompt
    assert "像真人回复" in sp and "营业时间9到22点" in sp


def test_classify_keyword_forces_confirmation(fake_llm):
    eng = ReplyEngine(fake_llm, sensitive_keywords=["报价", "投诉"])
    r = eng.classify("你们报价多少")
    assert r["needs_confirmation"] is True
    assert "报价" in r["reason"]
    # keyword short-circuits — the LLM classifier is not consulted
    assert all(c[0] != "classify" for c in fake_llm.calls)


def test_classify_defers_to_llm(fake_llm):
    fake_llm.needs_confirmation = True
    fake_llm.reason = "复杂问题"
    eng = ReplyEngine(fake_llm, sensitive_keywords=["报价"])
    r = eng.classify("你好呀")
    assert r["needs_confirmation"] is True
    assert r["reason"] == "复杂问题"
