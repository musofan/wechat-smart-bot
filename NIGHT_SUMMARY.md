# 夜间开发总结 (2026-07-09)

## TL;DR
Cline **整晚被卡住**（它的 GLM-5.2 模型 API 返回 429 quota_exceeded，自动重试失败、等待人工点
Retry）。为不浪费这一夜，**Claude 直接接管开发**，在分支 `claude/wechat-bot-automation-cd5a36`
上把 `TASKS.md` 的 **P1 + P2 + 硬化 + 文档（T1–T14）** 全部实现并测试通过。**没动 Cline 的
`night-build` 分支**，你早上可任选：合并我的分支，或点 Retry / 换模型让 Cline 重跑。

- ✅ 41 个离线单测全绿，ruff 干净，GitHub Actions 每次 push 均通过。
- ✅ **真机端到端只读冒烟测试通过**：`python run_suggest.py --once` 成功抓屏+OCR+识别未读会话，全程不发送。
- 🔒 安全默认：`DRY_RUN=True`、`MODE=SUGGEST` —— 代码与测试双重保证**不会发任何消息**。

## Cline 为什么没产出（截图诊断）
- Cline 配置正确：已 `checkout night-build`、YOLO 自动批准已开、我的指令已加载。
- 但底层模型 `openai-compat:glm-5.2` 返回：`429 rpm exhausted / quota_exceeded_error`。
- Cline 3 次自动重试失败 →「Manual intervention required」，停在等你点 **Retry**。整夜零提交。
- 我无法充值你的 GLM 额度、也未擅自操作你的 VSCode，故改为自己在独立分支开发。

## 我做了什么（分支 `claude/wechat-bot-automation-cd5a36`）
P1 建议模式（T1–T7）· P2 门控动作层（T8–T10）· 硬化（T11–T12）· 文档（T13–T14）：
- `config.py`：账号/跳过名单/敏感词/营业时间/`DRY_RUN`/`MODE`/人设，dotenv 变为可选
- `wechat_vision.py`：`parse_list_row`（名/时间/摘要/媒体拆分）、可覆盖 layout
- `wechat_reader.py`：`Message` 模型、自己/对方气泡区分、`latest_inbound`
- `reply_engine.py`：人设+知识库系统提示、关键词+LLM 敏感分类（LLM 注入可测）
- `store.py`：`SuggestionStore`（sqlite+jsonl，按 联系人+消息 去重）
- `bot_core.py`：SUGGEST 编排（**永不发送**，测试断言）+ 门控 `send_reply` + 确认指令解析
- `safety.py`：营业时间/最小间隔/每小时上限/`data/STOP` 急停
- `wechat_actuator.py`：`DryRunActuator`（默认，只记录）/ `LiveActuator`（win32，拟人，未测/未运行）
- `run_suggest.py`：`--frames` 离线回放 / `--once` 实时读当前会话；逐帧失败隔离
- `reporting.py`：运行报告；`RUNBOOK.md`：运行与**日后**开启发送的谨慎步骤
- `tests/`：41 个 mock 测试（`@pytest.mark.live` 的需 `--run-live`）

## 早上如何对接（二选一）
**A. 采用我的实现（推荐）**：把我的分支合到 `night-build`（Cline 无产出，零冲突）：
```
cd C:\Users\Tung\Documents\GitHub\wechat-smart-bot
git checkout night-build
git merge --ff-only origin/claude/wechat-bot-automation-cd5a36   # 应可快进
```
然后按 `RUNBOOK.md` 试跑 `python run_suggest.py --frames data\frames`。

**B. 仍用 Cline**：在 Cline 面板点 **Retry**（若额度已恢复），或切换到有额度的模型；它会按
`TASKS.md` 重做。可先参考我的分支。

## 还没做 / 建议下一步（需你在场）
- 填充 `knowledge_base.md` 真实业务内容（回复质量的关键）。
- 调优 `SKIP_NAMES`/`GROUP_MARKERS`（冒烟测试里有个别群未被过滤）。
- 校准 header/messages 区域（需打开一个会话时验证）。
- **开启发送前**务必：先对 文件传输助手 单条测试，再逐个熟人，全程保留安全阀。
- LiveActuator 尚未真机验证（设计上未在无人值守时运行）。

## 运维现状
- 我的 CI 监控仍在跑（观察 `night-build`）；GitHub Actions 在服务端校验每次 push。
- 全程只读，未向任何真实联系人发送消息。
