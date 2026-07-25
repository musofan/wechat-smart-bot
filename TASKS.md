# TASKS — Wave 2 backlog (work top-to-bottom)

> 前一轮（night-build, T1–T14）已全部完成，见 `TASKS_NIGHT_BUILD_DONE.md` 与 `NIGHT_SUMMARY.md`。
> 本轮目标：**从"fixture 全绿"走向"真实窗口验证过的 SUGGEST 模式产品"**。
>
> 安全护栏（延续 DEV_BRIEF，永远有效）：
> 1. 默认 `DRY_RUN=True`、`MODE=SUGGEST`，禁止真实发送。
> 2. 新增 `NAV_ENABLED`（默认 False）：只允许"点击打开会话"等导航动作，与发送动作分闸。
> 3. 任何真实窗口操作必须操作员在场；live 测试一律 `@pytest.mark.live`。
> 4. 每个任务：加测试（offline/mocked），`bash .ci/ci_check.sh` 全绿后勾选。

## Wave A — 真实世界验证（最高优先级，需操作员在场）

- [ ] **A1. 真机冒烟采集。** 操作员在场运行 `python run_suggest.py --once`，原始帧保存到
  `data/live/`（保持 gitignored）；人工核对 ≥5 个真实会话的未读检测与 name/snippet 切分正确率。
  *Done when:* `data/live/VALIDATION.md` 记录 OCR 准确率（正确/总数）、失败案例与原因分类。

- [ ] **A2. 真实帧回归测试。** 把 3–5 帧脱敏真实截图转为测试夹具（gitignored），
  vision 测试在夹具存在时加载、缺失时 skip。
  *Done when:* 有无夹具两种情况下 `pytest` 均绿。

- [ ] **A3. 填充 `knowledge_base.md`。** 运营提供 NeXTSCENE 真实业务信息（营业信息/FAQ/联系方式），
  消除全部"待补充"。回复质量直接取决于此。
  *Done when:* 无占位符；`test_reply_engine.py` 增加一条"KB 事实进入 prompt"的断言。

## Wave B — 导航/发送分闸 + 确认闭环

- [ ] **B1. Actuator 拆分。** `NavigationActuator`（打开会话/滚动）与 `SendActuator` 分离；
  新增 `NAV_ENABLED` 配置独立于 `DRY_RUN`。默认工厂：NAV_ENABLED=False 时导航也走 DryRun。
  *Done when:* 测试断言"导航放行但发送仍被阻断"的组合态；LiveActuator 仍仅 live 标记。

- [ ] **B2. 真机 SUGGEST 读完整会话。** NAV_ENABLED 下 `tick()` 真正点开未读会话，
  用 `wechat_reader` 读消息区全文（而非列表摘要）生成建议。
  *Done when:* 操作员在场的一次真实 dry-run 产出来自完整会话内容的建议记录。

- [ ] **B3. 监控号确认闭环。** 扫描循环解析 musomuso 会话中的 `1` / `2 <文本>` / `3`，
  回写 store 中建议状态（suggested→approved/custom/skipped）。
  *Done when:* fake 帧驱动状态迁移的测试通过；run_report 计入确认统计。

## Wave C — 质量与运营化

- [ ] **C1. LLM 端点可配置。** OpenAI 兼容 `base_url`/`model` 走 `.env`（默认 SenseNova；
  支持本地网关 127.0.0.1:18789 / 远端 LiteLLM）。
  *Done when:* config 测试覆盖端点覆盖；操作员手动跑一次真实 API 冒烟并记录时延。

- [ ] **C2. 建议复核 CLI。** `python review.py` 列出待办建议，支持 采用/改文/跳过 并回写 store。
  （后续可升级为最小 Web 面板，对应旧 PRD 的 P3。）
  *Done when:* 状态迁移测试通过；jsonl 与 SQLite 状态一致。

- [ ] **C3. 指标进 run_report。** OCR 置信度均值、建议按状态分布、分类准确率（复核后回填）。
  *Done when:* 报告含新字段且有测试断言。

## Wave D — 仓库卫生（可随时穿插，纯 autonomous 安全）

- [ ] **D1. 遗留代码清理。** `wechat_monitor.py` / `wechat_smart_monitor.py` / `wechat_computer_use.py` /
  `wechat_handler.py` / `main.py` / `message_router.py` / `database.py` 确认无引用后移入 `legacy/` 或删除；
  `channel1_ilink_bot.py` 标记 experimental（`weixin-bot-sdk` 不进 requirements 主依赖）。
  *Done when:* ruff+pytest 全绿；README 模块图更新。

- [ ] **D2. 文档对齐。** 更新 `PRD.md` 勾选项与 `PRD_DualChannel.md` 状态，使其与 night-build 实际架构一致。
  *Done when:* 文档不再描述"未完成"的已完成项，链接可解析。

- [ ] **D3. 分支合并。** Wave A 完成后 `night-build` → `master`。
  *Done when:* master 上 CI 全绿。

---
_If you finish early:_ 为 VLM 兜底定位（Qwen3-VL 本地 4bit）写接口骨架（不实现），
或把 review.py 升级为 FastAPI 单页面板。仍不得开启真实发送。
