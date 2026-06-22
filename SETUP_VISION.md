# Vision API 设置指南

## 推荐：阿里 DashScope (Qwen-VL)

### 注册步骤（约 3 分钟）

1. 打开 https://dashscope.console.aliyun.com/
2. 用支付宝/淘宝扫码登录
3. 点击 **「模型广场」** → 找到 **「qwen-vl-plus」**
4. 点击 **「API-KEY管理」** → **「创建」**
5. 复制 API Key（格式：`sk-xxxxxxxx`）

### 配置

在 `.env` 文件中添加：
```
DASHSCOPE_API_KEY=sk-你复制的key
```

### 费用
- 新用户免费额度：约 100 万 tokens
- qwen-vl-plus 价格：¥0.003/千tokens（极低）
- 一次截图分析约 100 tokens ≈ ¥0.0003

---

## 备选：智谱 GLM-4V

1. 打开 https://open.bigmodel.cn/
2. 注册账号
3. 创建 API Key
4. 在 `.env` 中设置 `ZHIPU_API_KEY=你的key`

---

## 设置完成后

```bash
python mobile_bot.py
```

Bot 会自动检测并使用 Vision 模型。
