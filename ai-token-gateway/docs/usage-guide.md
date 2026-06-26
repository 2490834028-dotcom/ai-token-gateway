# 使用说明

本文档介绍如何通过 AI Token Gateway 接入各类 AI API，以及在常见工具中配置使用。

---

## 获取 API Key

1. 访问管理后台：`http://<服务器IP>:8080`
2. 使用管理员账号登录
3. 进入 **用户管理**，创建新用户或为现有用户生成 API Key
4. 复制 API Key，后续请求中使用

---

## API 接口说明

基础地址：`http://<服务器IP>:8080`（生产环境建议使用 HTTPS 域名）

所有接口均兼容 OpenAI API 格式，支持标准的 Bearer Token 认证。

### 聊天补全

```
POST /v1/chat/completions
Authorization: Bearer <your-api-key>
Content-Type: application/json

{
  "model": "claude-sonnet-4-6",
  "messages": [
    {"role": "user", "content": "你好，请介绍一下自己"}
  ],
  "temperature": 0.7,
  "max_tokens": 1024
}
```

### 获取模型列表

```
GET /v1/models
Authorization: Bearer <your-api-key>
```

### 文本嵌入

```
POST /v1/embeddings
Authorization: Bearer <your-api-key>
Content-Type: application/json

{
  "model": "text-embedding-3-small",
  "input": "这是一段需要嵌入的文本"
}
```

### 语音转文字

```
POST /v1/audio/transcriptions
Authorization: Bearer <your-api-key>

Form Data:
  file: <audio-file>
  model: whisper-1
```

### 文字转语音

```
POST /v1/audio/speech
Authorization: Bearer <your-api-key>
Content-Type: application/json

{
  "model": "tts-1",
  "input": "你好，这是一段测试语音",
  "voice": "alloy"
}
```

---

## 在各工具中配置

### Python（OpenAI SDK）

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://your-server:8080/v1",
    api_key="your-gateway-api-key"
)

# 聊天
response = client.chat.completions.create(
    model="claude-sonnet-4-6",
    messages=[{"role": "user", "content": "你好"}]
)
print(response.choices[0].message.content)

# 流式输出
stream = client.chat.completions.create(
    model="claude-sonnet-4-6",
    messages=[{"role": "user", "content": "讲一个故事"}],
    stream=True
)
for chunk in stream:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="")
```

### Node.js（OpenAI SDK）

```javascript
import OpenAI from "openai";

const client = new OpenAI({
  baseURL: "http://your-server:8080/v1",
  apiKey: "your-gateway-api-key",
});

const response = await client.chat.completions.create({
  model: "claude-sonnet-4-6",
  messages: [{ role: "user", content: "你好" }],
});

console.log(response.choices[0].message.content);
```

### cURL

```bash
curl http://your-server:8080/v1/chat/completions \
  -H "Authorization: Bearer your-gateway-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-sonnet-4-6",
    "messages": [{"role": "user", "content": "你好"}]
  }'
```

---

## 常见工具接入

### ChatBox

1. 打开设置 → 模型提供方 → 选择 OpenAI Compatible
2. API Host 填写：`http://your-server:8080`
3. API Key 填写：你的 Gateway API Key

### LobeChat / NextChat

1. 进入设置 → 语言模型
2. OpenAI 兼容接口配置：
   - API 代理地址：`http://your-server:8080/v1`
   - API Key：你的 Gateway API Key

### Cursor

1. 打开 Settings → Models
2. 在 OpenAI API Key 处填入你的 Gateway API Key
3. 点击 "Override OpenAI Base URL"
4. 填写：`http://your-server:8080/v1`

### Claude Code

```bash
export ANTHROPIC_BASE_URL=http://your-server:8080
export ANTHROPIC_API_KEY=your-gateway-api-key
```

或在配置文件中设置自定义 API 端点。

### One API / New API

可将 AI Token Gateway 作为 One API / New API 的下级渠道：
1. 在 One API 中创建新渠道
2. 类型选择 "OpenAI"
3. Base URL 填写：`http://your-server:8080/v1`
4. 填入 Gateway API Key

---

## 模型名称映射

Gateway 使用的模型名称与上游平台对应关系：

| Gateway 模型名称       | 上游平台   | 对应模型              |
|:---------------------|:----------|:---------------------|
| `claude-sonnet-4-6`  | Claude     | Claude Sonnet 4      |
| `claude-opus-4-0`    | Claude     | Claude Opus 4        |
| `claude-haiku-3-5`   | Claude     | Claude 3.5 Haiku     |
| `gpt-4o`             | OpenAI     | GPT-4o               |
| `gpt-4o-mini`        | OpenAI     | GPT-4o Mini          |
| `gpt-4-turbo`        | OpenAI     | GPT-4 Turbo          |
| `gemini-pro`         | Gemini     | Gemini Pro           |
| `gemini-2.0-flash`   | Gemini     | Gemini 2.0 Flash     |

具体可用模型以管理后台配置的上游账号类型为准，可通过 `GET /v1/models` 接口查询。

---

## 用量查看

### 管理后台查看

登录管理后台 → **仪表盘**，可查看：
- 实时请求量趋势
- Token 消耗统计
- 活跃用户数
- 各上游账号的调用分布

### 用户自助查看

用户可通过管理后台登录后查看：
- 个人 Token 使用量
- 余额与消费明细
- 历史对话记录（如有权限）

---

## 并发与限流说明

| 限制维度       | 说明                                    |
|:-------------|:---------------------------------------|
| 用户级并发     | 单用户同时处理的请求数上限（可配置）            |
| 用户级频率     | 单用户每分钟最大请求数（可配置）              |
| 上游账号并发   | 单上游账号同时处理的请求数，超出自动路由到其他账号 |
| 粘性会话      | 同一会话内的请求优先路由到同一上游账号          |

超出限制时返回 `429 Too Many Requests`，响应头中包含 `Retry-After` 信息。
