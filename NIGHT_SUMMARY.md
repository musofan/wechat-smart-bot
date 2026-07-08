# 夜间开发总结 (2026-07-09)

## TL;DR（含 02:30 更新）
1) Cline 前半夜被卡住（GLM-5.2 API 429 quota_exceeded），零产出。为不浪费一夜，**Claude 直接接管**，
在分支 `claude/wechat-bot-automation-cd5a36` 上把 `TASKS.md` 的 **P1+P2+硬化+文档（T1–T14）+审阅CLI**
全部实现，**43 测试全绿、GitHub Actions 通过**。
2) **~01:38 Cline 额度恢复、自己开始干了**，在 `night-build` 上提交了 T2–T7（vision/reader/reply/
store/bot_core/run_suggest）。**但它的 CI 一直红**：`config.py` 硬 `import dotenv`，而精简 CI 环境没装
`python-dotenv` → 测试全在收集期 `ModuleNotFoundError`。我修好了 CI 监控（改为汇报 GitHub Actions 的
真实结论到 `.ci/STATUS.md`，之前因本机装了 dotenv 而误报绿），Cline 下个任务读到后应会修掉。

**所以现在有两条线**：
- `claude/wechat-bot-automation-cd5a36`（我的）：**完整、全绿**，可直接用。
- `night-build`（Cline 的）：进行中、目前 CI 红（就差一个 dotenv 修复）。

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
> 注意：现在两条线都有代码，不能简单快进合并；请二选一。

**A. 采用我的实现（最快拿到可用、全绿的完整版本）**：
```
cd C:\Users\Tung\Documents\GitHub\wechat-smart-bot
git checkout claude/wechat-bot-automation-cd5a36
python run_suggest.py --frames data\frames    # 按 RUNBOOK 试跑
```
满意的话可把它设为主线（如 `git branch -f master ...` 或直接在此分支上继续）。

**B. 继续用 Cline 的 `night-build`**：它进度到 T7，但 CI 红。让 Cline 读 `.ci/STATUS.md`（已是
真实的 GitHub Actions 结论）并修复 `config.py` 的 dotenv 导入（改成 try/except 可选，或把
`python-dotenv` 加进 `requirements-dev.txt`——我在自己分支已这么做）。修完 T8–T14 仍需 Cline 完成。

**建议**：直接用 A（完整全绿），把 B 当参考；或对比两版实现后择优。

## 还没做 / 建议下一步（需你在场）
- 填充 `knowledge_base.md` 真实业务内容（回复质量的关键）。
- 调优 `SKIP_NAMES`/`GROUP_MARKERS`（冒烟测试里有个别群未被过滤）。
- 校准 header/messages 区域（需打开一个会话时验证）。
- **开启发送前**务必：先对 文件传输助手 单条测试，再逐个熟人，全程保留安全阀。
- LiveActuator 尚未真机验证（设计上未在无人值守时运行）。

## 运维现状
- 我的 CI 监控仍在跑（观察 `night-build`）；GitHub Actions 在服务端校验每次 push。
- 全程只读，未向任何真实联系人发送消息。
