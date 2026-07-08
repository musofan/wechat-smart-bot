# 方案设计：视觉驱动的微信个人号自动回复机器人（Weixin 4.1.x）

> 结论文档 —— 基于对 Weixin 4.1.10.53 的**本机实测** + 大厂方案深度调研得出。取代早期"UIA vs OCR"的思路。

## 0. 决策摘要

- **账号**：专用号 **NeXTSCENE小助手**（本机已登录）跑机器人，所有消息转发给 **musomuso**（Muso 主号）。风险隔离：即使小助手被限制，也不牵连实名主号。
- **路线**：**视觉自动化 + 真人身份操作真客户端**。这是唯一同时满足"以真实个人号 / 在 4.1.10.53 上可跑 / 像真人"三者的方案。
- **首版范围**：**只读 / 只建议**（监控→读→草拟→转发给 musomuso 审阅），验证稳定后再开启自动发送。

## 1. 为什么是视觉路线（实测依据）

在本机 Weixin 4.1.10.53 上直接测量：

| 实验 | 结果 |
|---|---|
| UIA/MSAA 树 | **仅 2 个节点**（不透明 Qt Pane）→ wxauto/wxautox/pyweixin 结构性死亡 |
| 强制屏幕阅读器标志位（讲述人偏方原理） | **无效** → 该偏方已被封死 |
| `PrintWindow(PW_RENDERFULLCONTENT)` 截图 | **完整 UI，VLM 零 OCR 全可读** |
| 后台 + 被遮挡时截图 | **依然完整**，无需抢焦点 |
| 截图延迟 | **~16ms（~60/秒）** |

窗口最小化时抓不到（客户端区域塌缩）——微信保持"打开不最小化"即可，可藏在其它窗口后。

## 2. 架构

```
后台循环(1-2s, 不抢焦点):
  PrintWindow 截图 ──► 像素差 + 红点预筛 ──► 变化? ──► RapidOCR 读列表/气泡
                                                          │
                                          识别: 新消息? 谁? 群/单聊?
                                                          ▼
  LLM 层(云 API): 真人口吻回复(注入知识库) + 敏感分类(报价/合同/投诉→转人工)
                                                          ▼
        自动回复 ──► 短暂置顶 + SendInput + 剪贴板粘贴 + 拟人抖动发送
        需确认   ──► 转发 musomuso, 进人工确认队列 (回复 1/2改文/3跳过)
```

## 3. 组件选型（对齐 8GB RTX 3060 Ti / 32GB RAM）

| 层 | 选型 | 理由 |
|---|---|---|
| 抓取 | `PrintWindow(PW_RENDERFULLCONTENT)`（已验证）→ 二期 `Windows.Graphics.Capture` | 后台/遮挡可抓、不抢焦点、16ms |
| 检测 | 像素差 + 左侧导航红点检测 | 便宜，只有变化才进 OCR/LLM |
| 读取 | **RapidOCR**（PP-OCRv5 ONNX，CPU 也快，中文准）+ 几何锚点 | 微信固定布局，锚点+OCR 足够定位；day-1 不需要重 VLM |
| 点击定位 | 几何锚点优先；歧义时才升级本地 Qwen3-VL-4B(4bit) 或对裁剪区调云 VLM | 8GB 显存不必强跑 7B |
| 动作 | 短暂置顶 + `SendInput` + 剪贴板粘贴中文 + 对数正态延时/贝塞尔轨迹 | 拟人；**不用** PostMessage 后台注入（Qt/CEF 会忽略且更易被识别） |
| 业务 | 复用现有 `llm_client.py` / `message_router.py` / `database.py` / 知识库 | 只换底层感知+动作引擎，业务不重写 |

## 4. 明确否决

- **wxauto/wxautox/pyweixin**：UIA 仅 2 节点，4.x 死路。
- **WeChatFerry / DLL 注入**：无 4.1.10.53 支持；封号最高，作者自述用户"几乎无一幸免"，且会**连坐封实名主号**。
- **安卓模拟器**：个人号封号高（群控风控画像）+ 个人微信"单端在线"与真手机冲突。

## 5. 备选/增强（暂不采用，记录备查）

- **腾讯官方 iLink/OpenClaw 机器人通道**（`@tencent-weixin/openclaw-weixin`，@tencent.com 发布）：近乎零封号，但对方看到"机器人"身份、仅 1:1、Beta。适合"可接受 AI 身份"的场景，可作并行通道。
- **本地库解密只读检测**（`ylytdeng/wechat-decrypt`，支持 Weixin 4.0 内存取密钥+实时监听）：比 OCR 更可靠的收信检测，但**法律面烫手**（PyWxDump/chatlog/wechat-dump-rs 已于 2025-10 被腾讯 DMCA 团灭）。仅谨慎备选。

## 6. 封号安全阀（默认值）

只回复已有会话、不批量加人/群发、营业时间运行（非 7×24）、发送频率远低于 ~20 条/分、本地 IP（不上云、不异地登录）、账号养熟（实名/历史活跃）。低频精品咨询场景天然低风险。

## 7. 开发阶段

- **P0（进行中）**：`PrintWindow` 后台抓取模块 + RapidOCR 读取 + 未读检测 → **只读 dry-run**，在本机跑通、验证 OCR 准确率。
- **P1**：接入 LLM 生成回复 + 敏感分类 + 转发 musomuso（**仍只建议不自动发**，人工审阅）。
- **P2**：开启自动发送（SendInput + 拟人），人工确认队列，去重/错误恢复。
- **P3**：WGC 抓取硬化、VLM 兜底定位、Web 管理面板（可选）。

## 8. 关键文件（新引擎）

- `wechat_capture.py` —— 后台 PrintWindow 抓取（找窗口/DPI-safe rect/返回 PIL 图）。
- `wechat_vision.py` —— RapidOCR 读取 + 红点/像素差检测 + 布局锚点。
- `dryrun_vision.py` —— 只读演示：抓取→检测→OCR→结构化打印（不发送）。
- 复用：`llm_client.py`、`message_router.py`、`database.py`、`config.py`、`knowledge_base.md`。
