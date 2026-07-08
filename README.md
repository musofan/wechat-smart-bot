# WeChat Smart Bot

微信个人号智能监控与自动回复系统 — 基于**视觉自动化**（后台截图 + OCR + 模拟输入），适配新版 Weixin 4.x。

> 方案依据见 [SOLUTION.md](SOLUTION.md)；运行方式见 [RUNBOOK.md](RUNBOOK.md)。
> 默认**只读/只建议**（`DRY_RUN=True`、`MODE=SUGGEST`）——读消息、拟回复，但**不发送**。

## 视觉引擎模块图

| 模块 | 作用 |
|---|---|
| `wechat_capture.py` | 后台 `PrintWindow` 截图（不抢焦点，遮挡也可）+ 空白帧检测 |
| `wechat_vision.py` | RapidOCR 读取 + 未读红点/变化检测 + 列表行解析（名/时间/摘要/媒体） |
| `wechat_reader.py` | 结构化消息（自己/对方/系统气泡区分）+ latest_inbound |
| `reply_engine.py` | 真人口吻回复（注入知识库）+ 敏感分类（关键词 + LLM） |
| `store.py` | 建议存储（sqlite + jsonl，按 联系人+消息 去重） |
| `safety.py` | 发送安全阀（营业时间 / 最小间隔 / 每小时上限 / `data/STOP` 急停） |
| `wechat_actuator.py` | 动作层：DryRun（默认，只记录）/ Live（win32 点击+粘贴，拟人节奏） |
| `bot_core.py` | 编排：读→拟→分类→存；门控的 SEND 路径（默认永不触发） |
| `run_suggest.py` | 建议模式入口（`--frames` 离线回放 / `--once` 实时读当前会话） |

旧的 Computer Use 原型（`wechat_computer_use.py` / `wechat_smart_monitor.py` 等）保留供参考，已被上表取代。

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
