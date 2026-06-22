"""Channel 1: iLink Bot - Official WeChat AI Customer Service Bot.

Uses weixin-bot-sdk to create an official AI customer service bot.
This bot:
- Clearly identifies as AI assistant
- Provides guided conversation with options
- Professional customer service style
- Forwards all messages to monitoring account
"""

import asyncio
import time
from weixin_bot import WeixinBot
from llm_client import generate_reply
from database import init_db, save_conversation, get_conversation_history, save_message

# System prompt for official bot (clearly AI)
OFFICIAL_BOT_PROMPT = """你是 NeXT SCENE 的 AI 智能客服助手。

核心规则：
1. 你的身份：你是 AI 智能助手，开场时主动表明身份
2. 回复风格：专业、高效、简洁，每次回复控制在 3 句以内
3. 引导对话：适当提供选项引导用户
4. 涉及价格/合同/投诉时，回复："这个问题我需要转接人工客服，请稍等"
5. 不确定的问题："让我为您查询一下..."
6. 用中文回复
7. 不要编造不确定的信息

开场白模板：
"你好！我是 NeXT SCENE 的 AI 客服助手，有什么可以帮您？您可以问我关于产品、服务、合作等方面的问题。"
"""

# Forward target
MONITOR_ACCOUNT = "musomuso"


async def handle_message(bot: WeixinBot, msg):
    """Handle incoming message from iLink Bot."""
    try:
        user_id = msg.user_id
        text = msg.text if hasattr(msg, 'text') else str(msg)
        nickname = getattr(msg, 'nickname', user_id)

        print(f"[RECV] {nickname}({user_id}): {text[:80]}...")

        # Save incoming message
        save_message(
            msg_id=str(time.time()),
            wxid=user_id,
            nickname=nickname,
            content=text,
            direction="incoming"
        )

        # Show typing indicator
        await bot.send_typing(user_id)

        # Generate reply
        history = get_conversation_history(user_id)
        reply = generate_reply(history, text, system_prompt=OFFICIAL_BOT_PROMPT)

        # Save conversation
        save_conversation(user_id, nickname, "user", text)
        save_conversation(user_id, nickname, "assistant", reply)

        # Send reply
        await bot.reply(msg, reply)
        print(f"[SENT] -> {nickname}: {reply[:80]}...")

        # Forward to monitoring account
        try:
            forward_msg = (
                f"📨 [通道1-AI客服]\n"
                f"👤 联系人: {nickname}\n"
                f"⏰ 时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"📝 内容: {text}\n"
                f"🤖 回复: {reply}"
            )
            # Note: Forwarding to monitoring account via iLink API
            # requires the bot to have context_token for that user
            # For now, save to database for later retrieval
            save_message(
                msg_id=f"fwd_{time.time()}",
                wxid=MONITOR_ACCOUNT,
                nickname="monitor",
                content=forward_msg,
                direction="forwarded"
            )
            print(f"[FORWARD] Saved to monitoring queue")
        except Exception as e:
            print(f"[FORWARD ERROR] {e}")

    except Exception as e:
        print(f"[ERROR] {e}")


def main():
    """Start the iLink Bot."""
    print("=" * 50)
    print("  Channel 1: iLink Bot (AI Customer Service)")
    print("=" * 50)

    # Initialize database
    init_db()
    print("[INFO] Database initialized.")

    # Create bot
    bot = WeixinBot()

    # Register message handler
    @bot.on_message
    async def on_msg(msg):
        await handle_message(bot, msg)

    # Login (will show QR code)
    print("[INFO] Please scan QR code to login...")
    bot.login()

    print("[INFO] Bot is running! Press Ctrl+C to stop.")

    # Run the bot
    bot.run()


if __name__ == "__main__":
    main()
