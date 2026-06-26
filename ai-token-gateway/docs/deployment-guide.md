# 部署指南

本文档提供 AI Token Gateway 的完整部署、配置与运维操作说明。

---

## 环境要求

| 资源     | 最低配置           | 推荐配置             |
|:--------|:------------------|:--------------------|
| CPU      | 1 核              | 2 核                 |
| 内存     | 2 GB              | 4 GB                 |
| 磁盘     | 20 GB             | 50 GB（含日志持久化）  |
| 系统     | Ubuntu 20.04+ / Debian 11+ | Ubuntu 22.04 LTS |
| Docker   | 20.10+            | 最新稳定版            |
| Docker Compose | v2.0+       | 最新稳定版            |

---

## 快速部署（Docker Compose）

### 1. 克隆仓库

```bash
git clone https://github.com/your-username/ai-token-gateway.git
cd ai-token-gateway/deploy
```

### 2. 配置环境变量

```bash
cp .env.example .env
vim .env   # 或 nano .env
```

必须填写的变量：

| 变量                 | 说明                    | 示例                                    |
|:-------------------|:-----------------------|:---------------------------------------|
| `POSTGRES_PASSWORD` | PostgreSQL 数据库密码    | `MyStr0ngP@ss!2024`                    |
| `JWT_SECRET`        | JWT 加密密钥（建议64位） | `openssl rand -hex 32` 生成             |
| `ADMIN_EMAIL`       | 管理员登录邮箱           | `admin@yourdomain.com`                 |
| `ADMIN_PASSWORD`    | 管理员密码（留空则自动生成）| `SecureP@ssword123`                    |
| `REDIS_PASSWORD`    | Redis 访问密码          | `RedisStr0ngP@ss`                      |

可选变量：

| 变量                  | 说明               | 默认值   |
|:---------------------|:------------------|:--------|
| `TOTP_ENCRYPTION_KEY` | 双因素认证加密密钥  | 空（不启用）|
| `APP_PORT`            | 主服务对外端口      | `8080`   |
| `LOG_LEVEL`           | 日志级别           | `info`   |

### 3. 启动服务

```bash
docker compose up -d
```

首次启动会拉取镜像，预计需要 2-5 分钟（取决于网络速度）。

### 4. 查看服务状态

```bash
# 检查所有容器状态
docker compose ps

# 查看启动日志，获取管理员初始密码
docker compose logs sub2api | grep "admin password"
```

### 5. 访问管理后台

浏览器打开 `http://<服务器IP>:8080`，使用上一步获取的管理员账号密码登录。

---

## 上游账号配置

登录管理后台后，进入 **渠道管理** 页面，添加上游账号：

### Claude 接入

1. **Session Key 方式**：从浏览器获取 Claude 的 Session Key，填入渠道配置
2. **OAuth 方式**：按照后台引导完成 OAuth 授权流程
3. 建议配置 2-3 个账号，开启负载均衡

### OpenAI 接入

1. **API Key 方式**：从 [OpenAI Platform](https://platform.openai.com/api-keys) 获取 API Key
2. **Session Key 方式**：从浏览器获取 ChatGPT Session Key
3. 建议同时配置 API Key 和 Session Key 作为备选

### Gemini 接入

1. 从 [Google AI Studio](https://aistudio.google.com/) 获取 API Key
2. 填入渠道配置即可

---

## 监控配置

### Grafana 接入（可选）

1. 安装 Grafana（如未安装）：

```bash
docker run -d \
  --name grafana \
  -p 3000:3000 \
  -v grafana-data:/var/lib/grafana \
  grafana/grafana:latest
```

2. 访问 `http://<服务器IP>:3000`，默认账号密码 `admin/admin`

3. 导入监控看板：将 `monitoring/grafana-dashboard.json` 通过 Grafana UI 导入

4. 配置 Prometheus 数据源（如需指标采集）

---

## Nginx 反向代理 + HTTPS（生产环境推荐）

```nginx
server {
    listen 80;
    server_name api.yourdomain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name api.yourdomain.com;

    ssl_certificate     /etc/letsencrypt/live/api.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.yourdomain.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
        proxy_buffering off;
    }
}
```

---

## 日常运维

### 查看日志

```bash
# 所有服务日志（实时）
docker compose logs -f

# 仅 Sub2API 主服务日志
docker compose logs -f sub2api

# 最近 100 行日志
docker compose logs --tail=100 sub2api
```

### 重启服务

```bash
# 重启所有服务
docker compose restart

# 仅重启主服务
docker compose restart sub2api
```

### 更新版本

```bash
docker compose pull
docker compose up -d
```

### 备份数据库

```bash
# 手动备份（带时间戳）
docker compose exec postgres pg_dump -U sub2api sub2api \
  > "backup_$(date +%Y%m%d_%H%M%S).sql"

# 定时备份（添加到 crontab）
# 每天凌晨 3 点自动备份
0 3 * * * cd /path/to/ai-token-gateway/deploy && \
  docker compose exec -T postgres pg_dump -U sub2api sub2api \
  > /backups/sub2api_$(date +\%Y\%m\%d).sql
```

### 恢复数据库

```bash
cat backup.sql | docker compose exec -T postgres psql -U sub2api -d sub2api
```

---

## 故障排查

**无法访问管理后台？**
- 检查防火墙是否放行 8080 端口：`sudo ufw allow 8080`
- 确认服务已启动：`docker compose ps`
- 查看启动日志：`docker compose logs sub2api`

**上游账号频繁超时？**
- 检查服务器到上游服务的网络连通性：`curl -I https://api.anthropic.com`
- 配置多个同类型账号开启负载均衡
- 查看健康检查日志确认账号状态

**数据库连接失败？**
- 确认 PostgreSQL 容器健康：`docker compose ps postgres`
- 检查 `.env` 中 `POSTGRES_PASSWORD` 是否正确
- 查看数据库日志：`docker compose logs postgres`

**内存占用过高？**
- 检查 Redis 内存使用：`docker compose exec redis redis-cli -a $REDIS_PASSWORD info memory`
- 调整 Redis maxmemory 配置
- 检查日志文件大小，配置日志轮转
