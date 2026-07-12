"""LLM client using SenseNova API (OpenAI-compatible)."""

import json
from openai import OpenAI
from config import Config


def _get_client() -> OpenAI:
    """Get OpenAI-compatible client pointing to SenseNova."""
    return OpenAI(
        api_key=Config.SENSENOVA_API_KEY,
        base_url=Config.SENSENOVA_BASE_URL,
    )


def generate_reply(conversation_history: list[dict], current_message: str,
                    system_prompt: str = None) -> str:
    """Generate an auto-reply based on conversation context.

    Args:
        conversation_history: List of {"role": "user"/"assistant", "content": "..."}
        current_message: The latest incoming message text
        system_prompt: Optional custom system prompt (defaults to Config.SYSTEM_PROMPT)

    Returns:
        Generated reply text
    """
    client = _get_client()

    prompt = system_prompt or Config.SYSTEM_PROMPT
    messages = [{"role": "system", "content": prompt}]
    messages.extend(conversation_history)
    messages.append({"role": "user", "content": current_message})

    try:
        response = client.chat.completions.create(
            model=Config.SENSENOVA_MODEL,
            messages=messages,
            temperature=0.7,
            max_tokens=Config.LLM_MAX_TOKENS,
        )
        content = response.choices[0].message.content
        if not content:
            finish = response.choices[0].finish_reason
            print(f"[LLM WARN] empty content (finish={finish}); raise LLM_MAX_TOKENS if 'length'")
            return "抱歉，我稍后回复您。"
        reply = content.strip()
        # Remove potential quotes wrapping the reply
        if reply.startswith('"') and reply.endswith('"'):
            reply = reply[1:-1]
        return reply
    except Exception as e:
        print(f"[LLM ERROR] Failed to generate reply: {e}")
        return "抱歉，我稍后回复您。"


def classify_message(message: str, conversation_history: list[dict] = None) -> dict:
    """Classify whether a message needs human confirmation.

    Returns:
        {"needs_confirmation": bool, "reason": str, "confidence": float}
    """
    client = _get_client()

    context_str = ""
    if conversation_history:
        recent = conversation_history[-6:]  # Last 3 rounds
        context_str = "\n".join([f"{m['role']}: {m['content']}" for m in recent])

    prompt = f"""你是一个消息分类器。判断以下微信消息是否需要人工确认后才能回复。

判断标准（符合任一即需人工确认）：
1. 涉及金额、报价、合同、付款等财务敏感内容
2. 客户有明显投诉、愤怒、不满情绪
3. 客户提出超出业务范围的要求
4. 涉及法律、隐私、敏感话题
5. 第一次联系的陌生人提出的复杂问题

对话上下文：
{context_str if context_str else "无历史对话"}

当前消息：
{message}

请返回JSON格式：
{{"needs_confirmation": true/false, "reason": "原因说明", "confidence": 0.0-1.0}}"""

    try:
        response = client.chat.completions.create(
            model=Config.SENSENOVA_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=Config.LLM_MAX_TOKENS,
        )
        result_text = (response.choices[0].message.content or "").strip()
        # Try to parse JSON from the response
        # Handle cases where LLM wraps in markdown code blocks
        if "```" in result_text:
            result_text = result_text.split("```")[1]
            if result_text.startswith("json"):
                result_text = result_text[4:]
            result_text = result_text.strip()
        return json.loads(result_text)
    except Exception as e:
        print(f"[LLM ERROR] Classification failed: {e}")
        # Default: don't block, allow auto-reply
        return {"needs_confirmation": False, "reason": "分类失败，走自动回复", "confidence": 0.0}
