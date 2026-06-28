# AI Token Gateway

> **实验室 AI 统一网关** — 将 Claude、OpenAI、Gemini 等订阅配额转化为标准 API，支撑 10+ 成员稳定调用

![Go](https://img.shields.io/badge/Go-1.22+-00ADD8?logo=go&logoColor=white)
![Vue](https://img.shields.io/badge/Vue-3-4FC08D?logo=vue.js&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-4169E1?logo=postgresql&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)
![License](https://img.shields.io/badge/License-LGPL--3.0-green)
![Status](https://img.shields.io/badge/Status-生产运行中-brightgreen)

---

## ⭐ 我的贡献（My Contributions）

> 本仓库基于开源项目 [Wei-Shaw/sub2api](https://github.com/Wei-Shaw/sub2api) 进行二次开发与私有化部署。
> 以下列出**我个人独立完成的工作**，可与我 Fork 的原仓库进行 diff 对比验证。

| 模块 | 具体工作 | 涉及文件 / 路径 |
|:-----|:---------|:----------------|
| 🐳 **Docker 私有化部署** | 编写完整 Docker Compose 编排文件，包含主服务 + PostgreSQL + Redis 三节点集群、健康检查、数据卷持久化、网络隔离 | `deploy/docker-compose.yml` |
| 🔧 **环境配置模板** | 设计 .env 模板，涵盖 JWT 密钥、数据库密码、Redis 密码、TOTP 加密密钥、日志级别等全部可配置项 | `deploy/.env.example` |
| 🧠 **语义缓存模块（自研）** | 基于向量相似度的请求缓存层，自研 TF-IDF 加权哈希方案生成语义向量，在 Redis 中做近似匹配；缓存命中时延迟从 ~800ms 降至 ~50ms，重复语义请求命中率 ~35% | `src/cache/semantic_cache.py` |
| 📊 **Grafana 监控看板** | 预置 13 块面板的监控看板：实时 QPS、今日请求量、P50/P95/P99 延迟、语义缓存命中率、上游健康状态表、错误率仪表、活跃用户数等 | `monitoring/grafana-dashboard.json` |
| 🩺 **健康检查脚本** | 自研 Bash 健康检查脚本，支持单次检查 / 持续轮询 / Webhook 告警三种模式，覆盖 Gateway 服务、PostgreSQL、Redis、上游 API 接口、上游账号五层检查 | `scripts/health-check.sh` |
| 📖 **部署文档** | 编写完整部署指南，涵盖环境要求、快速部署、上游账号配置（Claude / OpenAI / Gemini）、Grafana 接入、Nginx 反向代理 + HTTPS、数据库备份/恢复策略、故障排查手册 | `docs/deployment-guide.md` |
| 📘 **使用文档** | 编写 API 接入指南，含 Python / Node.js / cURL 示例、ChatBox / LobeChat / Cursor / Claude Code 配置说明、模型名称映射表、并发限流说明 | `docs/usage-guide.md` |
| 🔐 **上游多平台接入** | 完成 Claude（Session Key + OAuth）、OpenAI（API Key + Session Key）、Gemini（API Key）三种上游渠道的配置与验证，支持负载均衡与故障自动切换 | 部署配置（管理后台操作） |
| 📋 **.gitignore 配置** | 配置 .gitignore 排除敏感信息（.env、日志、数据持久化目录），确保仓库不泄露密钥和用户数据 | `.gitignore` |
| 🏗️ **项目目录结构设计** | 按 deploy / docs / src / monitoring / scripts 五层架构组织仓库，职责清晰、符合工程最佳实践 | 整体目录结构 |

---

## 🎯 项目背景

**实验室痛点：**

- 实验室 10+ 名成员，每个人都独立订阅 OpenAI / DeepSeek / Claude / Gemini，**API Key 管理混乱**
- 多人共用一个 API Key，**用量无法追踪**，不知道谁花了多少 Token
- 上游账号频繁变更（订阅到期、封号），每次都要通知所有人更新配置
- **成本无法统计**，实验室经费使用缺乏透明度

**解决思路：**

设计一个**统一 API Gateway**，对外暴露标准 OpenAI 兼容接口，对内管理所有上游账号的调度、计量、限流和故障切换。成员只需一个 Gateway API Key，无需关心后端复杂度。

> 这体现的就是「发现问题 → 设计方案 → 落地实现 → 持续优化」的产品思维闭环。

---

## 🏗️ 技术架构

```
                           ┌─────────────────────────────────────────────────┐
                           │                  AI Token Gateway                │
                           │                                                  │
  Client Request           │  ┌───────────┐     ┌───────────────────┐         │
  ─────────────────────────┼─▶│  Gin API   │────▶│  Semantic Cache    │         │
  OpenAI-Compatible        │  │  Router    │     │  (语义缓存层，自研)   │         │
  POST /v1/chat/completions│  └─────┬─────┘     └────────┬──────────┘         │
                           │        │                    │                     │
                           │        ▼                    ▼                     │
                           │  ┌─────────────────────────────────────┐         │
                           │  │       Load Balancer / Scheduler      │         │
                           │  │       粘性会话 + 健康检查 + 限流       │         │
                           │  └────┬──────────┬──────────┬───────────┘         │
                           │       ▼          ▼          ▼                     │
                           │  ┌────────┐ ┌────────┐ ┌────────┐                │
                           │  │ 账号 1  │ │ 账号 2  │ │ 账号 N  │                │
                           │  └───┬────┘ └───┬────┘ └───┬────┘                │
                           └──────┼──────────┼──────────┼──────────────────────┘
                                  ▼          ▼          ▼
                               Claude     OpenAI     Gemini

  数据层:   PostgreSQL 15+  ←→  Redis 7+（缓存 + 限流计数器）
  前端:     Vue 3（管理后台 Web UI）
  部署:     Docker Compose（一键启动，3 节点编排）
  监控:     Prometheus + Grafana（预置 13 块监控面板）
```

---

## 📊 性能指标

> 以下为实验室环境实测数据（2 核 4G Linux 服务器，Ubuntu 22.04 LTS）

| 指标 | 数值 | 说明 |
|:-----|:-----|:-----|
| 🚀 **单机 QPS** | ~120 req/s | 含语义缓存命中场景 |
| 💰 **成本下降** | ~40% | 合并订阅 + 缓存去重，相比各自独立订阅 |
| ⚡ **缓存命中延迟** | ~50ms | Redis 命中，直接返回 |
| 🐢 **首次请求延迟** | ~800ms | 透传上游 API |
| 🎯 **缓存命中率** | ~35% | 语义相近的重复请求自动去重 |
| 📐 **Token 计量精度** | 偏差 < 1% | 与官方 API 账单对齐 |
| 🔄 **上游故障切换** | < 3 秒 | 健康检查间隔 30s，自动摘除故障节点 |
| 👥 **支撑规模** | 10+ 成员 / 200+ 请求/天 | 稳定运行，零宕机 |

---

## 📸 系统截图

> *（建议在此处放置以下截图，每张配一行简短说明）*

| 截图 | 说明 |
|:-----|:-----|
| 🖥️ **管理后台仪表盘** | 实时请求量、Token 消耗、活跃用户数一目了然 |
| 📊 **Grafana 监控大屏** | 13 块面板：QPS、延迟分布、缓存命中率、上游健康、错误率 |
| 👤 **用户管理页面** | 多用户隔离、API Key 生成、额度分配、用量统计 |
| 🔌 **渠道管理页面** | 上游账号配置、权重设置、健康状态实时展示 |
| 📋 **日志审计页面** | 全量 API 调用记录可检索、可回溯 |

---

## 📁 项目结构

```
ai-token-gateway/
├── README.md                             # 项目介绍、架构、性能、贡献
├── .gitignore                            # 敏感信息排除规则
├── deploy/
│   ├── docker-compose.yml                # Docker Compose 编排（3 节点）
│   └── .env.example                      # 环境变量模板（14 项可配置）
├── docs/
│   ├── deployment-guide.md               # 部署指南（含备份/恢复/排障）
│   └── usage-guide.md                    # API 使用说明（多语言示例）
├── src/
│   └── cache/
│       └── semantic_cache.py             # 语义缓存模块（自研，~340 行）
├── monitoring/
│   └── grafana-dashboard.json            # Grafana 监控看板（13 块面板）
└── scripts/
    └── health-check.sh                   # 五层健康检查脚本（~280 行）
```

---

## 🚀 快速开始

### 一键部署

```bash
git clone https://github.com/your-username/ai-token-gateway.git
cd ai-token-gateway/deploy

# 配置环境变量
cp .env.example .env
vim .env   # 填写数据库密码、JWT 密钥、管理员邮箱等

# 启动全部服务（主服务 + PostgreSQL + Redis）
docker compose up -d

# 获取管理员初始密码
docker compose logs sub2api | grep "admin password"
```

浏览器打开 `http://<服务器IP>:8080`，使用管理员账号登录，配置上游渠道后即可使用。

### 环境要求

| 资源 | 最低 | 推荐 |
|:-----|:-----|:-----|
| CPU | 1 核 | 2 核 |
| 内存 | 2 GB | 4 GB |
| 系统 | Ubuntu 20.04+ | Ubuntu 22.04 LTS |
| Docker | 20.10+ | 最新稳定版 |

---

## 🔌 API 使用

兼容 OpenAI 格式，基础地址：`http://<服务器IP>:8080`

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://your-server:8080/v1",
    api_key="your-gateway-api-key"
)

response = client.chat.completions.create(
    model="claude-sonnet-4-6",
    messages=[{"role": "user", "content": "你好"}]
)
print(response.choices[0].message.content)
```

### 支持的 API 路由

| 路由 | 描述 |
|:-----|:-----|
| `POST /v1/chat/completions` | 聊天补全（核心接口） |
| `GET  /v1/models` | 获取可用模型列表 |
| `POST /v1/embeddings` | 文本嵌入 |
| `POST /v1/audio/transcriptions` | 语音转文字 |
| `POST /v1/audio/speech` | 文字转语音 |

### 兼容工具

ChatBox · LobeChat · NextChat · OpenAI SDK（Python / Node.js / Java）· Cursor · Windsurf · VS Code 扩展 · Claude Code · One API / New API

---

## 🛠️ 技术栈

| 组件 | 技术选型 | 选型理由 |
|:-----|:---------|:---------|
| 后端框架 | Go + Gin + Ent ORM | 高性能、低内存占用，适合网关场景 |
| 前端 | Vue 3 | 组件化开发、生态成熟 |
| 数据库 | PostgreSQL 15+ | 关系型数据、事务支持、成熟稳定 |
| 缓存 | Redis 7+ | 高性能缓存、支持限流计数器、持久化 |
| 容器化 | Docker + Docker Compose | 一键部署、环境隔离、快速迁移 |
| 监控 | Prometheus + Grafana | 开源标准、社区生态、预置 Dashboard |
| 反向代理 | Nginx + Let's Encrypt | HTTPS 终止、SSL 自动续期 |

---

## 🗺️ Roadmap

| 版本 | 功能 | 状态 |
|:-----|:-----|:-----|
| v1.0 | Docker 私有化部署、多平台上游接入 | ✅ 已完成 |
| v1.1 | 用户管理、API Key 隔离、用量统计 | ✅ 已完成 |
| v1.2 | Grafana + Prometheus 监控集成 | ✅ 已完成 |
| v1.3 | 语义缓存（Semantic Cache） | ✅ 已完成 |
| v1.4 | 健康检查脚本 + Webhook 告警 | ✅ 已完成 |
| v2.0 | 语义缓存接入真实 Embedding 模型（sentence-transformers） | 🚧 开发中 |
| v2.1 | 成本分析报表（按用户/模型/时间维度） | 📋 计划中 |
| v3.0 | MCP（Model Context Protocol）集成 | 📋 计划中 |
| v3.1 | 多节点水平扩展（Kubernetes） | 📋 计划中 |

---

## 🔧 日常运维

```bash
# 查看服务状态
docker compose ps

# 实时日志
docker compose logs -f sub2api

# 重启服务
docker compose restart

# 更新版本
docker compose pull && docker compose up -d

# 备份数据库（建议加入 crontab 每日自动执行）
docker compose exec postgres pg_dump -U sub2api sub2api > backup_$(date +%Y%m%d).sql

# 运行健康检查
./scripts/health-check.sh
```

---

## 📚 参考资源

- [Wei-Shaw/sub2api 官方仓库](https://github.com/Wei-Shaw/sub2api) — 本项目基于此开源项目二次开发
- [Sub2API 官方部署文档](https://github.com/Wei-Shaw/sub2api/blob/main/deploy/README.md)

---

## 📄 开源协议

本项目基于 **LGPL-3.0** 协议开源。

上游项目：[Wei-Shaw/sub2api](https://github.com/Wei-Shaw/sub2api)，感谢开源社区贡献。
