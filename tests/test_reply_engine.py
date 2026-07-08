"""ReplyEngine: persona+KB reach the prompt; sensitive keywords force confirm."""

from reply_engine import ReplyEngine


def test_draft_injects_persona_and_kb(fake_llm):
    eng = ReplyEngine(
        fake_llm,
        knowledge_base="营业时间9到22点",
        persona="像真人回复",
    )
    reply = eng.draft([], "几点营业")
    assert reply == fake_llm.reply
    sp = fake_llm.last_system_prompt
    assert sp is not None
    assert "像真人回复" in sp
    assert "营业时间9到22点" in sp


def test_draft_empty_parts_ok(fake_llm):
    """No persona or KB should still produce a prompt (empty string handled by LLM)."""
    eng = ReplyEngine(fake_llm)
    reply = eng.draft([], "你好")
    assert reply == fake_llm.reply


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
    assert ("classify", "你好呀") in fake_llm.calls


def test_classify_no_keyword_ok(fake_llm):
    fake_llm.needs_confirmation = False
    fake_llm.reason = ""
    eng = ReplyEngine(fake_llm)
    r = eng.classify("今天天气不错")
    assert r["needs_confirmation"] is False
    assert r["reason"] == ""


def test_kb_from_config_loader(fake_llm):
    """Verify load_knowledge_base returns a string (integration with config)."""
    from config import load_knowledge_base

    kb = load_knowledge_base()
    assert isinstance(kb, str)
    # Our knowledge_base.md has content now
    assert len(kb) > 0
    assert "营业时间" in kb or "Knowledge Base" in kb