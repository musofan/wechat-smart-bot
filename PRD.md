# WeChat Smart Bot - 产品需求文档 (PRD)

## 1. 项目概述

### 1.1 项目名称
WeChat Smart Bot（微信智能监控与自动回复系统）

### 1.2 项目目标
基于普通微信个人号，实现实时消息监控、智能自动回复、消息转发、以及关键问题人工确认的完整工作流。

### 1.3 技术路线
采用 **Computer Use** 方式：屏幕截图 + OCR 文字识别 + LLM 智能回复 + 键盘模拟发送。
不依赖任何微信逆向工程或 Hook 技术，完全通过 GUI 自动化实现。

---

## 2. 核心功能

### 2.1 消息监控
- 实时监控微信窗口中的新消息
- 通过屏幕截图 + OCR 识别消息内容
- 支持中英文混合识别
- 自动区分发送者和消息内容

### 2.2 智能自动回复
- 基于商汤 SenseNova LLM 生成回复
- 支持对话上下文管理（SQLite 存储）
- 可配置 System Prompt 设定角色和业务规则
- 回复前经过关键词和语义双重检查

### 2.3 消息转发
- 所有收到的消息自动转发给指定监控账户
- 转发消息包含：发送者、时间、内容、AI回复状态
- 支持格式化消息卡片

### 2.4 关键问题检测与人工确认
- **关键词匹配**：投诉、退款、赔偿等敏感词
- **LLM 语义判断**：AI 判断消息是否需要人工确认
- **确认流程**：
  - 待确认消息加入队列
  - 监控账户收到确认请求
  - 支持三种操作：使用AI建议 / 自定义回复 / 跳过

---

## 3. 技术架构

```
┌─────────────────────────────────────────────┐
│              WeChat PC Client               │
│              (Weixin 4.1.10.53)             │
└─────────────┬───────────────────────────────┘
              │ Screen Capture
              ▼
┌─────────────────────────────────────────────┐
│         pyautogui (Screenshot)              │
└─────────────┬───────────────────────────────┘
              │ Image
              ▼
┌─────────────────────────────────────────────┐
│         EasyOCR / PaddleOCR                 │
│         (Text Recognition)                  │
└─────────────┬───────────────────────────────┘
              │ Text
              ▼
┌─────────────────────────────────────────────┐
│         Message Router Engine               │
│  ┌───────────┐ ┌──────────┐ ┌───────────┐  │
│  │ Filter    │ │ Classify │ │ Forward   │  │
│  │ (Rules)   │ │ (LLM)    │ │ (Monitor) │  │
│  └───────────┘ └──────────┘ └───────────┘  │
└─────────────┬───────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────┐
│         SenseNova LLM API                   │
│  - Generate Reply                           │
│  - Classify Message                         │
└─────────────┬───────────────────────────────┘
              │ Reply
              ▼
┌─────────────────────────────────────────────┐
│  pyautogui + pyperclip (Keyboard Sim)       │
│  → Paste reply into WeChat input            │
│  → Press Enter to send                      │
└─────────────────────────────────────────────┘
```

---

## 4. 项目文件结构

```
wechat-smart-bot/
├── .env                    # API 密钥和配置
├── .env.example            # 配置模板
├── .gitignore              # Git 忽略文件
├── PRD.md                  # 产品需求文档
├── README.md               # 项目说明
├── requirements.txt        # Python 依赖
├── config.py               # 配置管理
├── database.py             # SQLite 对话存储
├── llm_client.py           # SenseNova LLM 集成
├── wechat_computer_use.py  # Computer Use 主程序
├── wechat_handler.py       # 消息处理逻辑
├── message_router.py       # 消息路由引擎
├── main.py                 # HTTP API 版入口（备用）
└── data/                   # SQLite 数据库
```

---

## 5. 配置说明

### 5.1 环境变量 (.env)

| 变量 | 说明 | 示例 |
|------|------|------|
| SENSENOVA_API_KEY | 商汤 API 密钥 | sk-xxx |
| SENSENOVA_BASE_URL | API 地址 | https://token.sensenova.cn/v1 |
| SENSENOVA_MODEL | 模型名称 | sense-chat |
| MONITOR_ACCOUNT_NAME | 监控账户微信名 | 梦境空港小助手 |
| BOT_NAME | 本机微信昵称 | Muso |
| CRITICAL_KEYWORDS | 关键词（逗号分隔） | 投诉,退款,赔偿 |

---

## 6. 使用方法

### 6.1 安装依赖
```bash
pip install -r requirements.txt
pip install easyocr pyautogui pyperclip
```

### 6.2 配置
```bash
cp .env.example .env
# 编辑 .env 填入 API 密钥和配置
```

### 6.3 运行
```bash
# 确保微信已打开并登录
python wechat_computer_use.py
```

---

## 7. 开发计划

### Phase 1: 基础框架 ✅
- [x] 项目结构搭建
- [x] 配置管理
- [x] 数据库设计
- [x] LLM 集成

### Phase 2: Computer Use 核心 ⏳
- [x] 微信窗口定位（Qt51514QWindowIcon）
- [x] 屏幕截图模块
- [ ] OCR 文字识别（适配 Weixin 4.x）
- [ ] 消息内容解析
- [ ] 键盘模拟发送

### Phase 3: 智能回复 ⏳
- [x] SenseNova LLM 调用
- [x] 对话上下文管理
- [ ] 消息分类（需要人工确认 vs 自动回复）
- [ ] 关键词检测

### Phase 4: 转发与确认 ⏳
- [ ] 消息转发给监控账户
- [ ] 确认队列管理
- [ ] 监控账户回复解析

### Phase 5: 生产化 🔜
- [ ] 错误恢复机制
- [ ] 消息去重
- [ ] 性能优化
- [ ] Web 管理面板（可选）

---

## 8. 风险与限制

| 风险 | 等级 | 缓解措施 |
|------|------|----------|
| OCR 识别不准确 | ⚠️ 中 | 多次截图对比 + 置信度过滤 |
| 微信窗口被遮挡 | ⚠️ 中 | 每次操作前 bring_to_front |
| 消息发送延迟 | ⭐ 低 | 可调节监控间隔 |
| 微信版本更新 | ⚠️ 中 | 窗口类名可能变化，需适配 |
| LLM API 费用 | ⭐ 低 | SenseNova 价格低廉 |

---

## 9. 技术选型

| 组件 | 选型 | 理由 |
|------|------|------|
| 屏幕截图 | pyautogui | 跨平台，简单易用 |
| OCR | EasyOCR | 中文支持好，轻量级 |
| LLM | SenseNova | 性价比高，兼容 OpenAI 格式 |
| 存储 | SQLite | 轻量，无需额外服务 |
| 键盘模拟 | pyautogui + pyperclip | 支持中文粘贴 |
| 窗口管理 | ctypes + user32 | 直接调用 Windows API |

---

## 10. 版本历史

- **v0.1.0** (2026-06-22): 初始版本，基础框架搭建
