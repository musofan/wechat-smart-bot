"""Shared pytest fixtures + mocks. The whole suite runs WITHOUT a live Weixin
window and WITHOUT real RapidOCR — perception is mocked. Tests that genuinely need
the live client or real OCR must be marked @pytest.mark.live (skipped by default)."""

import numpy as np
import pytest
from PIL import Image


def pytest_addoption(parser):
    parser.addoption(
        "--run-live", action="store_true", default=False,
        help="also run @pytest.mark.live tests (needs a live Weixin window / real OCR)",
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-live"):
        return
    skip_live = pytest.mark.skip(reason="needs --run-live (live Weixin window / real OCR)")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip_live)


@pytest.fixture
def synth_full():
    """A synthetic 705x999 'WeChat-like' RGB image with one red unread badge dot
    in the chat-list column near y=220."""
    arr = np.full((999, 705, 3), 245, dtype=np.uint8)
    arr[214:226, 296:308] = (250, 70, 70)  # red badge dot
    return Image.fromarray(arr)


@pytest.fixture
def fake_ocr_lines():
    """Two conversations' worth of OCR lines in cropped chat-list coordinates."""
    from wechat_vision import OcrLine
    return [
        OcrLine("蒋智华", 0.9, cx=40, cy=20),
        OcrLine("您视频卡住了", 0.9, cx=60, cy=42),
        OcrLine("HICOOL峰会", 0.9, cx=40, cy=98),
        OcrLine("好的收到", 0.9, cx=60, cy=118),
    ]


class FakeLLM:
    """Deterministic stand-in for llm_client.* so reply/classify tests are offline."""

    def __init__(self, reply="你好，方便说下具体需求吗？", needs_confirmation=False, reason=""):
        self.reply = reply
        self.needs_confirmation = needs_confirmation
        self.reason = reason
        self.calls = []

    def generate_reply(self, history, message, system_prompt=None):
        self.calls.append(("generate", message))
        return self.reply

    def classify_message(self, message, history=None):
        self.calls.append(("classify", message))
        return {"needs_confirmation": self.needs_confirmation, "reason": self.reason}


@pytest.fixture
def fake_llm():
    return FakeLLM()


class RecordingActuator:
    """Records intended actions instead of touching the real mouse/keyboard.
    The action layer must accept an Actuator so tests never send anything."""

    def __init__(self):
        self.actions = []

    def open_conversation(self, y):
        self.actions.append(("open", y))

    def send_text(self, text):
        self.actions.append(("send", text))

    def focus_input(self):
        self.actions.append(("focus_input", None))


@pytest.fixture
def actuator():
    return RecordingActuator()
