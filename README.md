# ai-token-gateway
# Sub2API - AI Token 中转站

> 将 Claude、OpenAI、Gemini 等 AI 订阅配额统一转化为标准 API 接口，实现高效分发和管理

---

## 📖 项目简介

**Sub2API**（也称 CRS2）是一款基于 **Go 语言**开发的开源 **AI API 网关平台**。它可以将各大 AI 平台的网页版订阅（如 ChatGPT Plus、Claude Pro 等）或 API 额度，统一转化为标准的 OpenAI 兼容 API 接口，供第三方工具和应用调用。

本项目基于 [Wei-Shaw/sub2api](https://github.com/Wei-Shaw/sub2api) 部署搭建。

---

## ✨ 核心功能

### 🔄 多平台接入
支持将以下平台的订阅/额度转化为 API：
- **Claude**（Claude Pro / Claude Team 订阅）
- **OpenAI**（ChatGPT Plus / API Key）
- **Gemini**（Google AI 订阅）
- **Antigravity** 等更多平台

### 📊 精细化计费
- Token 级别的精确用量追踪
- 自定义费率设置
- 实时消费记录查询
- 用户维度使用统计

### 🧠 智能调度
- **粘性会话(Sticky Sessions)**：同一会话请求始终路由到同一上游账号，避免对话上下文丢失
- **负载均衡**：多账号间自动分配请求
- **健康检查**：自动检测上游账号可用性

### 🔐 安全与权限
- 多用户管理，API Key 隔离
- 并发限制与频率控制（用户级 + 上游账号级）
- 详细的访问日志审计

### 💳 内置支付（可选）
- 支持支付宝、微信支付、Stripe
- 开箱即用，无需额外部署支付服务
- 用户自助充值、自动扣费

### 🖥️ 管理面板
- Web UI 可视化后台管理
- 用户管理、套餐配置
- 实时监控大盘

---

## 🏗️ 技术栈

| 组件 | 技术 |
|------|------|
| **后端** | Go + Gin 框架 + Ent ORM |
| **前端** | Vue 3 |
| **数据库** | PostgreSQL 15+ |
| **缓存** | Redis 7+ |
| **部署** | Docker / Docker Compose |

---

## 🚀 部署方式

### 方式一：Docker Compose 部署（推荐）

```bash
# 1. 创建部署目录
mkdir -p sub2api-deploy && cd sub2api-deploy

# 2. 下载并运行一键部署脚本
curl -sSL https://raw.githubusercontent.com/Wei-Shaw/sub2api/main/deploy/docker-deploy.sh | bash

# 3. 启动所有服务
docker compose up -d

# 4. 查看管理员初始密码
docker compose logs sub2api | grep "admin password"
```

### 方式二：一键脚本安装

```bash
curl -sSL https://raw.githubusercontent.com/Wei-Shaw/sub2api/main/deploy/install.sh | sudo bash
```

### 环境要求

| 资源 | 最低配置 | 推荐配置 |
|------|----------|----------|
| **CPU** | 1 核 | 2 核 |
| **内存** | 2 GB | 4 GB |
| **系统** | Linux (Ubuntu 20.04+) | Linux (Ubuntu 22.04+) |
| **软件依赖** | Docker, Docker Compose | Docker, Docker Compose |

---

## ⚙️ 配置说明

### 核心环境变量（.env）

| 变量名 | 说明 | 是否必填 |
|--------|------|----------|
| `POSTGRES_PASSWORD` | PostgreSQL 数据库密码 | ✅ 必填 |
| `JWT_SECRET` | JWT 加密密钥 | ✅ 推荐固定 |
| `TOTP_ENCRYPTION_KEY` | 双因素认证密钥 | ❌ 可选 |
| `ADMIN_EMAIL` | 管理员邮箱 | ✅ 首次部署必填 |
| `ADMIN_PASSWORD` | 管理员密码 | ❌ 不填则自动生成 |

### 上游账号配置

登录后台后，在 **渠道管理** 中添加上游账号：

1. **Claude 订阅**：使用 Session Key 或 OAuth 方式接入
2. **OpenAI 订阅**：使用 API Key 或 Session Key 接入
3. **Gemini**：使用 API Key 接入

支持配置多个同类型账号，系统会自动进行负载均衡和故障切换。

---

## 🔌 API 使用

Sub2API 提供 **兼容 OpenAI 格式** 的 API 接口，可直接在支持 OpenAI API 的工具和库中使用。

### 基础地址

```
http://你的服务器IP:8080
```

### 支持的 API 路由

| 路由 | 描述 |
|------|------|
| `POST /v1/chat/completions` | 聊天补全（核心接口） |
| `GET /v1/models` | 获取可用模型列表 |
| `POST /v1/embeddings` | 文本嵌入 |
| `POST /v1/audio/transcriptions` | 语音转文字 |
| `POST /v1/audio/speech` | 文字转语音 |

### 使用示例

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://你的服务器IP:8080",
    api_key="你的Sub2API Key"
)

response = client.chat.completions.create(
    model="claude-sonnet-4-6",
    messages=[{"role": "user", "content": "你好"}]
)
print(response.choices[0].message.content)
```

---

## 🧩 兼容工具

由于兼容 OpenAI 格式，可直接在以下工具中使用：

- **ChatBox / LobeChat / NextChat** — 自定义 API 地址
- **OpenAI SDK**（Python / Node.js / Java 等）
- **Cursor / Windsurf / VS Code 扩展**
- **Claude Code**（配置自定义 API 端点）
- **One API / New API**（可叠加作为下级渠道）

---

## 📸 界面预览

### 管理面板
- **仪表盘**：实时查看请求量、Token 消耗、活跃用户
- **用户管理**：创建用户、分配额度、查看用量
- **渠道管理**：配置上游账号、设置权重和优先级
- **套餐配置**：定义不同等级的服务套餐
- **订单系统**：查看充值记录和消费明细
- **日志审计**：检索所有 API 调用记录
- **系统设置**：全局参数、支付配置、安全策略

---

## 📁 项目结构

```
sub2api-deploy/
├── docker-compose.yml    # Docker Compose 编排文件
├── .env                  # 环境变量配置
├── data/
│   ├── postgres/         # PostgreSQL 数据持久化
│   └── redis/            # Redis 数据持久化
└── logs/                 # 日志文件
```

---

## 🔧 日常维护

### 查看服务状态
```bash
docker compose ps
```

### 查看日志
```bash
# 查看所有服务日志
docker compose logs -f

# 查看 Sub2API 主服务日志
docker compose logs -f sub2api
```

### 重启服务
```bash
docker compose restart
```

### 更新版本
```bash
docker compose pull
docker compose up -d
```

### 备份数据库
```bash
docker compose exec postgres pg_dump -U sub2api sub2api > backup.sql
```

---

## ❓ 常见问题

**Q：无法访问管理后台？**
A：检查防火墙是否放行了 8080 端口，确认服务已启动：`docker compose ps`

**Q：忘记管理员密码？**
A：查看启动日志：`docker compose logs sub2api | grep "admin password"`

**Q：上游账号频繁超时？**
A：检查网络连通性，可尝试配置多个同类型账号开启负载均衡

**Q：如何修改管理员邮箱？**
A：在 .env 文件中修改 `ADMIN_EMAIL` 后执行 `docker compose up -d` 重启

**Q：支持 HTTPS 吗？**
A：建议使用 Nginx 反向代理并配置 SSL 证书

---

## 📚 参考资源

- [GitHub 官方仓库](https://github.com/Wei-Shaw/sub2api)
- [Sub2API 官方部署文档](https://github.com/Wei-Shaw/sub2api/blob/main/deploy/README.md)
- [吴宾的 Sub2API 教程](https://wu.wubin.cc/171.html)（含 B 站视频讲解）
- [Sub2API 使用对比与 New-API 对比](https://zengwu.com.cn/archives/ocsubnew)
- [演示站](https://demo.sub2api.org/)

---

## 📄 开源协议

本项目基于 **LGPL-3.0** 协议开源，感谢 [Wei-Shaw/sub2api](https://github.com/Wei-Shaw/sub2api) 团队的开源贡献。
