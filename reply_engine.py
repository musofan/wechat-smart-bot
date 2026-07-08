"""Draft a natural-person reply and classify sensitivity. The LLM is injected so
this is fully unit-testable offline (see tests/conftest.py FakeLLM)."""

from __future__ import annotations


class ReplyEngine:
    """Composes persona + knowledge base into the system prompt and returns a reply.

    Args:
        llm: Injected LLM client (must have .generate_reply and .classify_message).
        knowledge_base: Raw text from knowledge_base.md (or empty string).
        persona: Persona prompt describing the bot's character (or empty string).
        sensitive_keywords: List of keywords that force needs_confirmation.
    """

    def __init__(
        self,
        llm,
        knowledge_base: str = "",
        persona: str = "",
        sensitive_keywords=(),
    ):
        self.llm = llm
        self.kb = knowledge_base or ""
        self.persona = persona or ""
        self.sensitive_keywords = list(sensitive_keywords or [])

    def _build_system_prompt(self) -> str:
        """Build the system prompt from persona + knowledge base."""
        parts = []
        if self.persona.strip():
            parts.append(self.persona.strip())
        if self.kb.strip():
            parts.append(
                "以下是可依据的事实信息（不要编造未提及的内容）：\n"
                + self.kb.strip()
            )
        return "\n\n".join(parts)

    def draft(self, history: list, incoming: str) -> str:
        """Draft a reply for the given incoming message.

        Args:
            history: Conversation history (list of dicts with role/content).
            incoming: The latest incoming message text.

        Returns:
            Draft reply text.
        """
        return self.llm.generate_reply(
            history, incoming, system_prompt=self._build_system_prompt()
        )

    def classify(self, incoming: str, history=None) -> dict:
        """Classify whether the message needs human confirmation.

        Keyword gate first — cheap and deterministic; never auto-reply on these.
        Falls through to LLM classification if no keyword hit.

        Returns:
            {"needs_confirmation": bool, "reason": str}
        """
        # Keyword gate — first pass, no LLM needed.
        for kw in self.sensitive_keywords:
            if kw and kw in incoming:
                return {"needs_confirmation": True, "reason": f"命中敏感词: {kw}"}

        # Defer to LLM classifier.
        result = self.llm.classify_message(incoming, history) or {}
        return {
            "needs_confirmation": bool(result.get("needs_confirmation")),
            "reason": result.get("reason", ""),
        }