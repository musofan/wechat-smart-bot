# WeChat Smart Bot

微信个人号智能监控与自动回复系统 — 基于 Computer Use 方式。

## 技术路线

**屏幕截图 + OCR + LLM + 键盘模拟** — 不依赖任何微信逆向工程。

```
微信窗口 → 屏幕截图 → OCR文字识别 → LLM智能回复 / 仅建议 → 键盘模拟发送
```

**当前状态 (night-build): 仅 SUGGEST 模式运行，绝不发送真实消息。**

## 核心功能

- **消息监控**：实时监控微信窗口新消息（OCR 识别）
- **智能回复建议**：基于商汤 SenseNova LLM 生成回复草稿，保存到建议队列
- **安全门控**：敏感词检测、人工确认标记、DRY_RUN= True 确保零发送
- **消息转发**：自动转发给监控账户（P2，门控关闭）
- **人工确认**：关键问题检测，需人工确认后回复

## 快速开始 (安全离线模式)

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置
cp .env.example .env
# 编辑 .env 填入 API 密钥（可选；无 API 密钥时使用桩回复）

# 3. 运行（离线 fixture 模式）
python run_suggest.py --once --frames data/
# 读取 data/ 下的截图，运行一个 tick 后退出，输出到 data/suggestions.jsonl
```

完整操作指南见 [`RUNBOOK.md`](RUNBOOK.md)。

## 项目结构

```
├── bot_core.py              # 编排器 — Bot.tick() 驱动全管道
├── config.py                # 配置管理（Env + 默认值）
├── database.py              # SQLite 对话存储
├── knowledge_base.md        # 知识库（运营人员填充）
├── llm_client.py            # SenseNova LLM 集成
├── observability.py         # 可观测性 — 运行报告 + 日志配置
├── reply_engine.py          # 回复引擎 — 合成 persona + KB + LLM 回复
├── robustness.py            # 鲁棒性 — 空白帧检测、重试、窗口检查
├── run_suggest.py           # SUGGEST 模式入口（loop / --once / --frames）
├── safety.py                # 安全门控 — 限速、业务时间、kill-switch
├── store.py                 # 建议存储 — SQLite + JSONL append
├── wechat_actuator.py       # 动作层 — DryRunActuator / LiveActuator
├── wechat_capture.py        # 窗口捕获 — 屏幕截图
├── wechat_handler.py        # 消息处理逻辑
├── wechat_message.py        # 消息类型与路由
├── wechat_monitor.py        # 监控循环（旧版）
├── wechat_reader.py         # 对话读取 — 消息气泡解析 + sender 判别
├── wechat_vision.py         # OCR 视觉识别 — 文字提取 + LAYOUT 解析
├── data/
│   ├── suggestions.jsonl    # 建议输出（JSONL append）
│   └── run_report.md        # 退出报告
├── tests/                   # 全离线 mock 测试
│   ├── test_actuator.py
│   ├── test_bot_core.py
│   ├── test_config.py
│   ├── test_observability.py
│   ├── test_reader.py
│   ├── test_reply_engine.py
│   ├── test_robustness.py
│   ├── test_run_suggest.py
│   ├── test_safety.py
│   ├── test_send_flow.py
│   ├── test_store.py
│   └── test_vision.py
├── .ci/                     # CI 门控
│   ├── ci_check.sh          # 本地提交前检查脚本
│   ├── STATUS.md            # 状态标记（OK / FAIL）
│   └── BLOCKED.md           # 阻塞项记录
├── PRD.md                   # 产品需求文档
├── RUNBOOK.md               # 运行手册
├── TASKS.md                 # 开发任务清单
└── .env                     # 配置（不提交）
```

## 兼容性

- Windows 10/11
- Weixin 4.x（通过窗口类名 `Qt51514QWindowIcon` 定位）
- Python 3.9+

## License

MIT
