"""Vision client for screen understanding.

Supports multiple Vision models:
- Qwen-VL (DashScope/Alibaba)
- GLM-4V (Zhipu)
- Gemini (Google)
- Fallback to cnocr if no Vision API available
"""

import base64
import io
import re
from PIL import Image


class VisionClient:
    """Unified Vision client for screen understanding."""

    def __init__(self, provider="auto", api_key=None, base_url=None):
        self.provider = provider
        self.api_key = api_key
        self.base_url = base_url
        self._client = None

        if provider == "auto":
            self._detect_provider()

    def _detect_provider(self):
        """Auto-detect available Vision provider."""
        import os

        # Check environment variables
        if os.getenv("DASHSCOPE_API_KEY"):
            self.provider = "qwen"
            self.api_key = os.getenv("DASHSCOPE_API_KEY")
            self.base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
        elif os.getenv("ZHIPU_API_KEY"):
            self.provider = "glm"
            self.api_key = os.getenv("ZHIPU_API_KEY")
            self.base_url = "https://open.bigmodel.cn/api/paas/v4"
        else:
            self.provider = "none"
            print("[VISION] No Vision API configured. Using OCR fallback.")

    def _get_client(self):
        """Get OpenAI-compatible client."""
        if self._client:
            return self._client

        from openai import OpenAI
        self._client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
        )
        return self._client

    def image_to_base64(self, img: Image.Image) -> str:
        """Convert PIL Image to base64 string."""
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        return base64.b64encode(buf.getvalue()).decode()

    def analyze_screen(self, img: Image.Image, prompt: str) -> str:
        """Analyze a screenshot using Vision model.

        Args:
            img: PIL Image of the screenshot
            prompt: Question/instruction about the image

        Returns:
            Text response from Vision model
        """
        if self.provider == "none":
            return self._fallback_ocr(img, prompt)

        img_b64 = self.image_to_base64(img)

        try:
            client = self._get_client()

            # Use model names based on provider
            model_map = {
                "qwen": "qwen-vl-plus",
                "glm": "glm-4v",
            }
            model = model_map.get(self.provider, "gpt-4o-mini")

            response = client.chat.completions.create(
                model=model,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}},
                        {"type": "text", "text": prompt}
                    ]
                }],
                max_tokens=1000,
                temperature=0.3,
            )
            return response.choices[0].message.content.strip()

        except Exception as e:
            print(f"[VISION ERROR] {e}")
            return self._fallback_ocr(img, prompt)

    def analyze_wechat_chat_list(self, img: Image.Image) -> list[dict]:
        """Analyze WeChat chat list screenshot.

        Returns list of conversations:
        [{"name": "...", "preview": "...", "time": "...", "has_unread": bool}]
        """
        prompt = """分析这个微信聊天列表截图。请列出所有可见的对话，每个对话包含：
1. name: 联系人/群名称
2. preview: 最后一条消息预览
3. time: 时间戳
4. has_unread: 是否有未读消息（看是否有红色角标或蓝色数字）

请用JSON数组格式返回，例如：
[{"name": "张三", "preview": "你好", "time": "14:30", "has_unread": true}]

只返回JSON，不要其他文字。"""

        result = self.analyze_screen(img, prompt)

        # Parse JSON from response
        try:
            # Try to extract JSON from response
            json_match = re.search(r'\[.*\]', result, re.DOTALL)
            if json_match:
                import json
                return json.loads(json_match.group())
        except Exception as e:
            print(f"[VISION PARSE ERROR] {e}")

        return []

    def analyze_wechat_messages(self, img: Image.Image) -> list[dict]:
        """Analyze WeChat conversation screenshot.

        Returns list of messages:
        [{"sender": "...", "content": "...", "is_self": bool}]
        """
        prompt = """分析这个微信对话截图。请列出所有可见的消息，每条消息包含：
1. sender: 发送者名称（如果是自己发的就写"我"）
2. content: 消息内容
3. is_self: 是否是自己发的消息（自己发的消息在右侧）

请用JSON数组格式返回，例如：
[{"sender": "张三", "content": "你好", "is_self": false}, {"sender": "我", "content": "你好！", "is_self": true}]

只返回JSON，不要其他文字。"""

        result = self.analyze_screen(img, prompt)

        try:
            json_match = re.search(r'\[.*\]', result, re.DOTALL)
            if json_match:
                import json
                return json.loads(json_match.group())
        except Exception as e:
            print(f"[VISION PARSE ERROR] {e}")

        return []

    def _fallback_ocr(self, img: Image.Image, prompt: str) -> str:
        """Fallback to cnocr if Vision API not available."""
        try:
            from cnocr import CnOcr
            import numpy as np
            ocr = CnOcr()
            result = ocr.ocr(np.array(img))
            texts = [item.get('text', '') for item in result if item.get('score', 0) > 0.4]
            return '\n'.join(texts)
        except Exception as e:
            return f"OCR fallback failed: {e}"
