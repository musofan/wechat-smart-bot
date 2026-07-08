"""Bot orchestrator (SUGGEST mode): verify tick() produces suggestions and does NOT send."""

from bot_core import Bot, TickResult
from reply_engine import ReplyEngine
from store import SuggestionStore
from wechat_reader import Message, Sender
from wechat_vision import Conversation


# ---------- fakes ----------

class _FakeCapture:
    def capture(self):
        from PIL import Image
        import numpy as np
        arr = np.full((999, 705, 3), 245, dtype=np.uint8)
        return Image.fromarray(arr)


class _FakeVision:
    def __init__(self, conversations=None):
        self.conversations = conversations or [
            Conversation(name="张三", snippet="你好", y_full=220, has_unread=True),
            Conversation(name="李四", snippet="在吗", y_full=320, has_unread=True),
            Conversation(name="文件传输助手", snippet="test", y_full=100, has_unread=True),
        ]

    def read_chat_list(self, full):
        return self.conversations

    def detect_unread_rows(self, full):
        return [c.y_full for c in self.conversations if c.has_unread]


class _FakeReader:
    def __init__(self, inbound_text="你好呀"):
        self._inbound_text = inbound_text

    def latest_inbound(self, full):
        return Message(sender=Sender.OTHER, text=self._inbound_text)

    @property
    def vision(self):
        return _FakeVision()


class _FakeActuator:
    def __init__(self):
        self.actions = []

    def open_conversation(self, y):
        self.actions.append(("open", y))

    def send_text(self, text):
        self.actions.append(("send", text))

    def focus_input(self):
        self.actions.append(("focus_input", None))


class _FakeLLM:
    def __init__(self, reply="您好！", needs_confirmation=False, reason=""):
        self.reply = reply
        self.needs_confirmation = needs_confirmation
        self.reason = reason

    def generate_reply(self, history, message, system_prompt=None):
        return self.reply

    def classify_message(self, message, history=None):
        return {"needs_confirmation": self.needs_confirmation, "reason": self.reason}


# ---------- dummy config ----------

class _TestConfig:
    BOT_NAME = "NeXTSCENE小助手"
    BOT_ACCOUNT = "NeXTSCENE小助手"
    SKIP_NAMES = ["文件传输助手", "微信团队"]
    GROUP_MARKERS = ["群聊", "群", "Group"]
    SCAN_INTERVAL = 5
    SENSITIVE_KEYWORDS = ["投诉", "退款", "合同", "报价", "法律", "律师", "付款", "发票"]


# ---------- tests ----------

def _make_bot(llm_reply="您好！", need_confirm=False, confirm_reason="",
              inbound_text="你好呀", conversations=None):
    capture = _FakeCapture()
    vision = _FakeVision(conversations=conversations)
    reader = _FakeReader(inbound_text=inbound_text)
    llm = _FakeLLM(reply=llm_reply, needs_confirmation=need_confirm, reason=confirm_reason)
    engine = ReplyEngine(llm=llm, sensitive_keywords=_TestConfig.SENSITIVE_KEYWORDS)
    store = SuggestionStore(db_path=":memory:")
    store.init()
    actuator = _FakeActuator()
    config = _TestConfig()
    bot = Bot(capture, vision, reader, engine, store, actuator, config)
    return bot, store, actuator


def test_tick_produces_suggestions():
    bot, store, actuator = _make_bot()
    results = bot.tick(None)
    # Two unread conversations that pass skip filter (张三, 李四)
    assert len(results) == 2
    for r in results:
        assert isinstance(r, TickResult)
        assert r.stored is True
        assert r.draft_reply == "您好！"

    # Store should have both
    stored = store.list_recent()
    assert len(stored) == 2
    contacts = {s["contact"] for s in stored}
    assert contacts == {"张三", "李四"}


def test_tick_no_send_actions():
    """Actuator must only contain 'open' actions, never 'send'."""
    bot, store, actuator = _make_bot()
    bot.tick(None)
    for action, value in actuator.actions:
        assert action != "send", f"unexpected send action: {action, value}"
        assert action == "open"


def test_tick_skips_bot_self_and_groups():
    convs = [
        Conversation(name="NeXTSCENE小助手", snippet="", y_full=50, has_unread=True),
        Conversation(name="工作群聊", snippet="消息", y_full=150, has_unread=True),
        Conversation(name="陌生人", snippet="你好", y_full=250, has_unread=True),
    ]
    bot, store, actuator = _make_bot(conversations=convs)
    results = bot.tick(None)
    # Only "陌生人" should pass
    assert len(results) == 1
    assert results[0].contact == "陌生人"


def test_tick_inbound_empty():
    """Skip conversations where the latest inbound is a non-text media marker."""
    bot, store, actuator = _make_bot(inbound_text="[图片]")
    results = bot.tick(None)
    assert len(results) == 0


def test_tick_stores_needs_confirmation():
    bot, store, actuator = _make_bot(
        need_confirm=True, confirm_reason="命中敏感词: 投诉"
    )
    results = bot.tick(None)
    assert len(results) == 2
    for r in results:
        assert r.needs_confirmation is True
        assert r.reason == "命中敏感词: 投诉"

    stored = store.list_recent()
    for s in stored:
        assert s["needs_confirmation"] == 1