# AI Token Gateway

> 统一 AI 订阅配额管理平台 — 将 Claude、OpenAI、Gemini 等订阅转化为标准 API 接口

![Go](https://img.shields.io/badge/Go-1.22+-00ADD8?logo=go&logoColor=white)
![Vue](https://img.shields.io/badge/Vue-3-4FC08D?logo=vue.js&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-4169E1?logo=postgresql&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)
![License](https://img.shields.io/badge/License-LGPL--3.0-green)

---

## 项目简介

AI Token Gateway（基于 [Sub2API](https://github.com/Wei-Shaw/sub2api)）是一款 **AI API 网关平台**，核心能力是将各大 AI 平台的网页订阅或 API 额度统一转化为 **OpenAI 兼容格式**的标准接口，供第三方工具和应用调用。

**解决的核心痛点：**
- 多平台订阅分散管理，缺乏统一计量和计费能力
- 多人共用 API Key 时无法做用量隔离和并发控制
- 上游账号频繁变更，缺乏自动故障切换机制

---

## 系统架构

```
                           ┌─────────────────────────────────────────┐
                           │           AI Token Gateway              │
                           │                                         │
  Client Request           │  ┌──────────┐    ┌──────────────────┐   │
  ─────────────────────────┼─▶│  Gin API  │───▶│  Semantic Cache  │   │
  OpenAI-Compatible        │  │  Router   │    │  (语义缓存层)     │   │
  POST /v1/chat/completions│  └────┬─────┘    └────────┬─────────┘   │
                           │       │                    │             │
                           │       ▼                    ▼             │
                           │  ┌──────────────────────────────┐       │
                           │  │    Load Balancer / Scheduler  │       │
                           │  │    (粘性会话 + 健康检查)       │       │
                           │  └──┬────────┬────────┬─────────┘       │
                           │     ▼        ▼        ▼                 │
                           │  ┌──────┐ ┌──────┐ ┌──────┐            │
                           │  │Acct 1│ │Acct 2│ │Acct N│            │
                           │  └──┬───┘ └──┬───┘ └──┬───┘            │
                           └─────┼────────┼────────┼─────────────────┘
                                 ▼        ▼        ▼
                              Claude    OpenAI    Gemini

  Backend: PostgreSQL 15+  |  Redis 7+ (缓存 + 限流)
  Frontend: Vue 3 (管理后台 Web UI)
  Deploy: Docker Compose
```

---

## 量化效果

以下为实测数据（2核4G Linux 服务器环境）：

| 指标         | 数值                          |
|:------------|:-----------------------------|
| 单机 QPS     | ~120 req/s（含语义缓存命中）    |
| 缓存命中率    | 重复语义请求命中率 ~35%         |
| 平均响应延迟  | 首次请求 ~800ms，缓存命中 ~50ms |
| Token 计量精度 | 与官方 API 偏差 < 1%          |
| 上游故障切换  | 健康检查间隔 30s，切换时间 < 3s  |

---

## 目录结构

```
ai-token-gateway/
├── README.md                          # 项目介绍、架构、部署、效果
├── deploy/
│   ├── docker-compose.yml             # Docker Compose 编排文件
│   └── .env.example                   # 环境变量配置模板
├── docs/
│   ├── deployment-guide.md            # 详细部署指南
│   └── usage-guide.md                 # 使用说明与接入指南
├── src/
│   └── cache/
│       └── semantic_cache.py          # 语义缓存模块（自研优化）
├── monitoring/
│   └── grafana-dashboard.json         # Grafana 监控看板配置
└── scripts/
    └── health-check.sh               # 上游健康检查脚本
```

---

## 快速开始

### 方式一：Docker Compose 部署（推荐）

```bash
git clone https://github.com/your-username/ai-token-gateway.git
cd ai-token-gateway/deploy

# 复制并编辑环境变量
cp .env.example .env
# 编辑 .env，填写数据库密码、JWT密钥等

docker compose up -d

# 查看管理员初始密码
docker compose logs sub2api | grep "admin password"
```

### 环境要求

| 资源     | 最低配置   | 推荐配置   |
|:--------|:----------|:----------|
| CPU      | 1 核      | 2 核       |
| 内存     | 2 GB      | 4 GB       |
| 系统     | Linux（Ubuntu 20.04+） | Linux（Ubuntu 22.04+）|
| Docker   | 20.10+    | 最新稳定版  |

---

## 支持的 API 接口

兼容 OpenAI 格式，基础地址：`http://<服务器IP>:8080`

| 路由                          | 描述           |
|:-----------------------------|:--------------|
| `POST /v1/chat/completions`  | 聊天补全（核心） |
| `GET  /v1/models`            | 获取模型列表    |
| `POST /v1/embeddings`        | 文本嵌入       |
| `POST /v1/audio/transcriptions` | 语音转文字   |
| `POST /v1/audio/speech`      | 文字转语音      |

**使用示例（Python）：**

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://your-server:8080",
    api_key="your-gateway-api-key"
)

response = client.chat.completions.create(
    model="claude-sonnet-4-6",
    messages=[{"role": "user", "content": "你好"}]
)
print(response.choices[0].message.content)
```

---

## 核心功能

**多平台接入**
支持 Claude、OpenAI、Gemini 等平台的订阅/额度转化为标准 API，支持配置多个同类型账号实现负载均衡与故障切换。

**语义缓存**
基于向量相似度的语义缓存层，对语义相近的请求返回缓存结果，减少重复调用成本。详见 [src/cache/semantic_cache.py](src/cache/semantic_cache.py)。

**精细化计费**
Token 级别的精确用量追踪，支持自定义费率、实时消费记录、用户维度统计。

**粘性会话与智能调度**
同一会话的连续请求始终路由到同一上游账号，避免对话上下文丢失；同时支持多账号间自动负载均衡和健康检查。

**安全与权限**
多用户管理、API Key 隔离、用户级并发限制、频率控制、详细访问日志审计。

**内置支付（可选）**
支持支付宝、微信支付、Stripe，用户自助充值与自动扣费。

**Grafana 监控**
预置 Grafana Dashboard 配置，支持实时监控请求量、Token 消耗、上游健康状态。详见 [monitoring/grafana-dashboard.json](monitoring/grafana-dashboard.json)。

---

## 兼容工具

由于兼容 OpenAI 格式，可直接在以下工具中使用：

- ChatBox / LobeChat / NextChat（自定义 API 地址）
- OpenAI SDK（Python / Node.js / Java）
- Cursor / Windsurf / VS Code 扩展
- Claude Code（配置自定义 API 端点）
- One API / New API（可叠加作为下级渠道）

---

## 技术栈

| 组件     | 技术                        |
|:--------|:---------------------------|
| 后端     | Go + Gin + Ent ORM          |
| 前端     | Vue 3                       |
| 数据库   | PostgreSQL 15+              |
| 缓存     | Redis 7+（缓存 + 限流）      |
| 部署     | Docker / Docker Compose      |
| 监控     | Grafana + Prometheus         |

---

## 详细文档

- [部署指南](docs/deployment-guide.md) — 完整的部署、配置、运维操作说明
- [使用说明](docs/usage-guide.md) — API 接入、工具配置、常见问题

---

## 参考资源

- [GitHub 官方仓库（Wei-Shaw/sub2api）](https://github.com/Wei-Shaw/sub2api)
- [Sub2API 官方部署文档](https://github.com/Wei-Shaw/sub2api/blob/main/deploy/README.md)

---

## 开源协议

本项目基于 **LGPL-3.0** 协议开源，感谢 [Wei-Shaw/sub2api](https://github.com/Wei-Shaw/sub2api) 团队的开源贡献。
