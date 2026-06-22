# WeChat Mobile Automation - 手机端自动化方案

## 1. 方案概述

通过 ADB 连接本地 Android 手机，在手机微信 App 上实现消息监控和自动回复。

### 为什么手机端更好？

| 对比项 | PC 端 (当前) | 手机端 (新方案) |
|--------|-------------|-----------------|
| 文字大小 | 小 (10-14px) | 大 (16-24px) |
| OCR 准确率 | 低 (cnocr ~60%) | 高 (AI Vision ~95%) |
| UI 结构 | 复杂 (Qt框架) | 标准 (Android View) |
| 自动化工具 | 有限 (pyautogui) | 丰富 (uiautomator2, Airtest) |
| AI 理解能力 | 需要 OCR 后处理 | Vision 模型直接理解 |

---

## 2. 技术架构

```
┌──────────────────────────────────────────┐
│              Android 手机                 │
│  ┌──────────────────────────────────┐    │
│  │        微信 App                    │    │
│  │  (聊天列表 / 对话 / 输入框)        │    │
│  └──────────────┬───────────────────┘    │
│                 │ ADB                    │
└─────────────────┼────────────────────────┘
                  │ USB / WiFi
┌─────────────────▼────────────────────────┐
│              Windows PC                   │
│                                          │
│  ┌─────────────┐  ┌──────────────────┐  │
│  │ ADB 截图    │  │ uiautomator2     │  │
│  │ (screencap) │  │ (点击/输入/滑动)  │  │
│  └──────┬──────┘  └────────┬─────────┘  │
│         │                  │             │
│         ▼                  ▼             │
│  ┌──────────────────────────────────┐   │
│  │     AI Vision 模型               │   │
│  │  (Qwen-VL / GLM-4V / Gemini)    │   │
│  │  直接理解屏幕内容，无需 OCR       │   │
│  └──────────────┬───────────────────┘   │
│                 │                        │
│                 ▼                        │
│  ┌──────────────────────────────────┐   │
│  │     SenseNova LLM (回复生成)     │   │
│  └──────────────┬───────────────────┘   │
│                 │                        │
│                 ▼                        │
│  ┌──────────────────────────────────┐   │
│  │     转发给 musomuso               │   │
│  └──────────────────────────────────┘   │
└──────────────────────────────────────────┘
```

---

## 3. 核心组件

### 3.1 ADB 连接
```bash
# 连接手机（USB 模式）
adb devices
# 或 WiFi 模式
adb connect 192.168.1.100:5555
```

### 3.2 截图与输入
```python
import uiautomator2 as u2

# 连接设备
d = u2.connect()  # USB
# 或 d = u2.connect("192.168.1.100")  # WiFi

# 截图
screenshot = d.screenshot()
screenshot.save("screen.png")

# 点击
d.click(x, y)

# 输入文字
d(text="输入框").set_text("你好")

# 滑动
d.swipe(x1, y1, x2, y2)

# 查找元素
d(text="发送").click()
d(resourceId="com.tencent.mm:id/chatting_content").exists
```

### 3.3 AI Vision 模型（屏幕理解）

#### 方案 A: Qwen-VL (阿里通义千问)
```python
from openai import OpenAI

client = OpenAI(
    api_key="your-qwen-api-key",
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
)

# 发送截图给 Vision 模型
response = client.chat.completions.create(
    model="qwen-vl-plus",
    messages=[{
        "role": "user",
        "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}},
            {"type": "text", "text": "请分析这个微信聊天界面：1. 最新消息是什么？2. 是谁发的？3. 需要回复吗？"}
        ]
    }]
)
```

**优势**：
- 阿里官方维护，稳定性高
- 中文理解能力强
- 支持截图直接分析
- API 价格低廉

#### 方案 B: GLM-4V (智谱清言)
```python
from zhipuai import ZhipuAI

client = ZhipuAI(api_key="your-zhipu-key")

response = client.chat.completions.create(
    model="glm-4v",
    messages=[{
        "role": "user",
        "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}},
            {"type": "text", "text": "分析这个微信界面，告诉我最新消息和发送者"}
        ]
    }]
)
```

**优势**：
- 智谱官方，更新频繁
- Vision 能力强
- 支持长上下文

#### 方案 C: Gemini (Google)
```python
import google.generativeai as genai

model = genai.GenerativeModel("gemini-1.5-flash")
response = model.generate_content([
    "分析这个微信截图",
    Image.open("screen.png")
])
```

#### 方案 D: 本地模型 (Ollama + LLaVA)
```bash
ollama pull llava
```
```python
import requests

response = requests.post("http://localhost:11434/api/generate", json={
    "model": "llava",
    "prompt": "分析这个微信截图",
    "images": [base64_image]
})
```

### 3.4 方案对比

| 模型 | 中文能力 | 截图理解 | 价格 | 延迟 | 推荐度 |
|------|----------|----------|------|------|--------|
| Qwen-VL Plus | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ¥0.003/千tokens | ~1s | ⭐⭐⭐⭐⭐ |
| GLM-4V | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ¥0.05/千tokens | ~1.5s | ⭐⭐⭐⭐ |
| Gemini 1.5 Flash | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | $0.075/千tokens | ~1s | ⭐⭐⭐⭐ |
| SenseNova (商汤) | ⭐⭐⭐⭐ | ⭐⭐⭐ | 低 | ~1s | ⭐⭐⭐ |
| 本地 LLaVA | ⭐⭐⭐ | ⭐⭐⭐ | 免费 | ~5s+ | ⭐⭐ |

---

## 4. 实施步骤

### Phase 1: 基础连接 (1天)
1. 手机开启 USB 调试
2. ADB 连接测试
3. 安装 uiautomator2
4. 截图 + 基本 UI 操作测试

### Phase 2: AI Vision 集成 (1-2天)
1. 选择 Vision 模型（推荐 Qwen-VL）
2. 截图 → Vision 模型分析
3. 验证屏幕理解准确率
4. 对比多个模型效果

### Phase 3: 微信自动化 (2-3天)
1. 微信 App UI 元素定位
2. 聊天列表监控
3. 打开对话 → 读取消息
4. 输入回复 → 发送
5. 转发给 musomuso

### Phase 4: 智能化 (1-2天)
1. LLM 回复生成
2. 关键问题检测
3. 人工确认流程
4. 对话上下文管理

---

## 5. 微信 Android UI 关键元素

```
微信 Android 界面布局:
┌────────────────────────────┐
│ [微信] [通讯录] [发现] [我] │  ← 底部导航栏
│────────────────────────────│
│ 搜索                        │
│────────────────────────────│
│ [头像] 联系人1    14:30     │  ← 聊天列表
│ [头像] 联系人2    14:25     │
│ [头像] 群聊1      14:20     │
│ ...                        │
└────────────────────────────┘

关键 resource-id (可能因版本不同):
- 聊天列表: com.tencent.mm:id/...
- 消息内容: com.tencent.mm:id/chatting_content
- 输入框: com.tencent.mm:id/chatting_content_et
- 发送按钮: com.tencent.mm:id/chatting_send_btn
```

---

## 6. 风险与注意事项

| 风险 | 等级 | 缓解措施 |
|------|------|----------|
| USB 连接不稳定 | ⭐ 低 | 使用 WiFi ADB |
| 微信版本更新 UI 变化 | ⚠️ 中 | 使用 Vision 模型自适应 |
| 手机电量消耗 | ⭐ 低 | 保持充电 |
| AI Vision API 费用 | ⭐ 低 | Qwen-VL 价格很低 |
| 微信封号 | ⭐ 低 | 操作频率控制 |

---

## 7. 依赖安装

```bash
pip install uiautomator2 adbutils
pip install openai  # For Qwen-VL
# 或
pip install zhipuai  # For GLM-4V
```
