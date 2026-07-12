"""Bot orchestrator (SUGGEST mode): produces a suggestion and NEVER sends."""

from types import SimpleNamespace

from PIL import Image

from bot_core import Bot
from store import SuggestionStore
from wechat_reader import Message


class FakeReader:
    def __init__(self, name, inbound):
        self._name = name
        self._inbound = inbound

    def read_contact_name(self, full):
        return self._name

    def read_open_conversation(self, full):
        return [Message("other", self._inbound, "text")] if self._inbound else []

    @staticmethod
    def latest_inbound(msgs):
        for m in reversed(msgs):
            if m.sender == "other":
                return m
        return None


class FakeReplyEngine:
    def draft(self, history, incoming):
        return "你好呀"

    def classify(self, incoming, history=None):
        return {"needs_confirmation": False, "reason": ""}


def _cfg(skip=(), groups=("群",)):
    return SimpleNamespace(SKIP_NAMES=list(skip), GROUP_MARKERS=list(groups))


def _img():
    return Image.new("RGB", (705, 999), (245, 245, 245))


def test_tick_produces_suggestion_and_never_sends(tmp_path, actuator):
    store = SuggestionStore(tmp_path / "b.db", tmp_path / "s.jsonl", clock=lambda: 1.0)
    bot = Bot(vision=None, reader=FakeReader("蒋智华", "想咨询业务"),
              reply_engine=FakeReplyEngine(), store=store, config=_cfg(),
              actuator=actuator)
    sug = bot.handle_open_conversation(_img())
    assert sug is not None
    assert sug.contact == "蒋智华" and sug.draft_reply == "你好呀"
    assert store.count() == 1
    # THE key safety assertion: nothing was sent.
    assert all(a[0] != "send" for a in actuator.actions)


def test_skips_groups_and_skipnames(tmp_path, actuator):
    store = SuggestionStore(tmp_path / "b.db", tmp_path / "s.jsonl")
    bot = Bot(None, FakeReader("706上海5群", "hi"), FakeReplyEngine(), store,
              _cfg(groups=("群",)), actuator=actuator)
    assert bot.handle_open_conversation(_img()) is None
    assert store.count() == 0


def test_skips_group_by_member_count(tmp_path, actuator):
    # "机友圈儿RoboCrew（446)" has no 群 marker but the (446) member count = group
    store = SuggestionStore(tmp_path / "b.db", tmp_path / "s.jsonl")
    bot = Bot(None, FakeReader("机友圈儿RoboCrew（446)", "刘启迪：在吗"), FakeReplyEngine(),
              store, _cfg(groups=("群",)), actuator=actuator)
    assert bot.handle_open_conversation(_img()) is None
    # a real person name is NOT skipped
    assert bot.should_skip("蒋智华") is False


def test_dedup_returns_none_second_time(tmp_path, actuator):
    store = SuggestionStore(tmp_path / "b.db", tmp_path / "s.jsonl")
    bot = Bot(None, FakeReader("客户", "在吗"), FakeReplyEngine(), store, _cfg(),
              actuator=actuator)
    assert bot.handle_open_conversation(_img()) is not None
    assert bot.handle_open_conversation(_img()) is None  # duplicate suppressed
