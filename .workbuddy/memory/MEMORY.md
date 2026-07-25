# wechat-smart-bot — 长期项目笔记

## 项目定位
微信个人号智能监控+自动回复。视觉自动化路线（PrintWindow 截图 + RapidOCR + LLM + SendInput），
明确否决 wxauto/UIA（4.x 仅 2 节点）、WeChatFerry/DLL 注入（封号+连坐主号）。
账号隔离：机器人跑 NeXTSCENE小助手 号，消息转发 musomuso 主号。

## 安全护栏（不可违反）
- DRY_RUN=True / MODE=SUGGEST 是默认；禁止真实发送；live 测试一律 @pytest.mark.live。
- 禁止 wcferry/wxauto/PyWxDump/注入/解密依赖；感知只允许截图+OCR。
- .env 不入库；data/ 下截图与 jsonl gitignored。
- 测试门禁：bash .ci/ci_check.sh（ruff + pytest），绿后小步 conventional commit。

## 环境
- 开发用 Python: C:\Users\Tung\AppData\Local\Python\pythoncore-3.12-64\python.exe（3.12，pytest/ruff 在此）。
- 目标客户端 Weixin 4.1.10.53，窗口类 Qt51514QWindowIcon，采样尺寸 705x999。
- 窗口最小化时 PrintWindow 抓不到（客户端区域塌缩），保持不最小化即可，可被遮挡。

## 状态（2026-07-25）
- night-build 分支 T1–T14 完成（SUGGEST 管线 + 动作层 gated OFF），142 测试绿。
- 从未真机验证；TASKS.md 已切换为 Wave-2 backlog（A 真机验证/B 导航分闸/C 运营化/D 卫生）。
- 关键待办：knowledge_base.md 待运营填充；channel1 (iLink) 为 experimental 未集成。
