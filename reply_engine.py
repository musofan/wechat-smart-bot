"""Draft a natural-person reply and classify sensitivity. The LLM is injected so
this is fully unit-testable offline (see tests/conftest.py FakeLLM)."""

from __future__ import annotations


class ReplyEngine:
    def __init__(self, llm, knowledge_base: str = "", persona: str = "",
                 sensitive_keywords=()):
        self.llm = llm
        self.kb = knowledge_base or ""
        self.persona = persona or ""
        self.sensitive_keywords = list(sensitive_keywords or ())

    def _system_prompt(self) -> str:
        parts = []
        if self.persona.strip():
            parts.append(self.persona.strip())
        if self.kb.strip():
            parts.append("以下是可依据的事实信息（不要编造未提及的内容）：\n" + self.kb.strip())
        return "\n\n".join(parts)

    def draft(self, history, incoming: str) -> str:
        return self.llm.generate_reply(history, incoming, system_prompt=self._system_prompt())

    def classify(self, incoming: str, history=None) -> dict:
        # Keyword gate first — cheap and deterministic; never auto-reply on these.
        for kw in self.sensitive_keywords:
            if kw and kw in incoming:
                return {"needs_confirmation": True, "reason": f"命中敏感词: {kw}"}
        res = self.llm.classify_message(incoming, history) or {}
        return {
            "needs_confirmation": bool(res.get("needs_confirmation")),
            "reason": res.get("reason", ""),
        }
