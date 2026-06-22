# WeChat Smart Bot

微信个人号智能监控与自动回复系统 — 基于 Computer Use 方式。

## 技术路线

**屏幕截图 + OCR + LLM + 键盘模拟** — 不依赖任何微信逆向工程。

```
微信窗口 → 屏幕截图 → OCR文字识别 → LLM智能回复 → 键盘模拟发送
```

## 核心功能

- **消息监控**：实时监控微信窗口新消息（OCR 识别）
- **智能回复**：基于商汤 SenseNova LLM 生成回复
- **消息转发**：自动转发给监控账户
- **人工确认**：关键问题检测，需人工确认后回复

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置
cp .env.example .env
# 编辑 .env 填入 API 密钥

# 3. 运行（确保微信已打开）
python wechat_computer_use.py
```

## 项目结构

```
├── config.py               # 配置管理
├── database.py             # SQLite 对话存储
├── llm_client.py           # SenseNova LLM 集成
├── wechat_computer_use.py  # Computer Use 主程序
├── wechat_handler.py       # 消息处理逻辑
├── message_router.py       # 消息路由引擎
├── PRD.md                  # 产品需求文档
└── .env                    # 配置（不提交）
```

## 兼容性

- Windows 10/11
- Weixin 4.x（通过窗口类名 `Qt51514QWindowIcon` 定位）
- Python 3.9+

## License

MIT
