#!/usr/bin/env bash
# ============================================================
# AI Token Gateway - 上游账号健康检查脚本
# 定期检测上游 API 账号可用性，不可用时自动通知
#
# 使用方式：
#   ./health-check.sh                    # 单次检查
#   ./health-check.sh --loop             # 持续检查（每 30 秒）
#   ./health-check.sh --alert-webhook URL  # 配置告警通知
#
# 依赖：curl, jq
# ============================================================

set -euo pipefail

# ----- 配置 -----
GATEWAY_URL="${GATEWAY_URL:-http://localhost:8080}"
ADMIN_TOKEN="${ADMIN_TOKEN:-}"
CHECK_INTERVAL="${CHECK_INTERVAL:-30}"
ALERT_WEBHOOK="${ALERT_WEBHOOK:-}"
LOG_FILE="${LOG_FILE:-/var/log/ai-token-gateway/health-check.log}"

# 上游接口健康检查超时（秒）
HEALTH_TIMEOUT=10

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# ----- 函数 -----

log() {
    local level="$1"
    shift
    local msg="$*"
    local timestamp
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${timestamp} [${level}] ${msg}"

    if [[ -n "$LOG_FILE" ]]; then
        mkdir -p "$(dirname "$LOG_FILE")"
        echo "${timestamp} [${level}] ${msg}" >> "$LOG_FILE"
    fi
}

check_gateway_health() {
    local http_code
    http_code=$(curl -s -o /dev/null -w "%{http_code}" \
        --max-time "$HEALTH_TIMEOUT" \
        "${GATEWAY_URL}/health" 2>/dev/null) || true

    if [[ "$http_code" == "200" ]]; then
        echo -e "${GREEN}✓${NC} Gateway 服务正常 (HTTP ${http_code})"
        return 0
    else
        echo -e "${RED}✗${NC} Gateway 服务异常 (HTTP ${http_code})"
        return 1
    fi
}

check_api_endpoint() {
    local endpoint="$1"
    local label="$2"
    local http_code

    http_code=$(curl -s -o /dev/null -w "%{http_code}" \
        --max-time "$HEALTH_TIMEOUT" \
        -H "Authorization: Bearer ${ADMIN_TOKEN}" \
        "${GATEWAY_URL}${endpoint}" 2>/dev/null) || true

    if [[ "$http_code" =~ ^(200|201|204)$ ]]; then
        echo -e "${GREEN}✓${NC} ${label} 正常 (HTTP ${http_code})"
        return 0
    else
        echo -e "${RED}✗${NC} ${label} 异常 (HTTP ${http_code})"
        return 1
    fi
}

check_database() {
    local status
    status=$(docker inspect --format='{{.State.Health.Status}}' sub2api-postgres 2>/dev/null) || status="unknown"

    if [[ "$status" == "healthy" ]]; then
        echo -e "${GREEN}✓${NC} PostgreSQL 数据库正常"
        return 0
    else
        echo -e "${RED}✗${NC} PostgreSQL 数据库状态异常: ${status}"
        return 1
    fi
}

check_redis() {
    local status
    status=$(docker inspect --format='{{.State.Health.Status}}' sub2api-redis 2>/dev/null) || status="unknown"

    if [[ "$status" == "healthy" ]]; then
        echo -e "${GREEN}✓${NC} Redis 缓存正常"
        return 0
    else
        echo -e "${RED}✗${NC} Redis 缓存状态异常: ${status}"
        return 1
    fi
}

check_upstream_accounts() {
    if [[ -z "$ADMIN_TOKEN" ]]; then
        echo -e "${YELLOW}⚠${NC} 未配置 ADMIN_TOKEN，跳过上游账号检查"
        return 0
    fi

    local response
    response=$(curl -s --max-time "$HEALTH_TIMEOUT" \
        -H "Authorization: Bearer ${ADMIN_TOKEN}" \
        "${GATEWAY_URL}/api/admin/channels" 2>/dev/null) || {
        echo -e "${RED}✗${NC} 无法获取上游账号列表"
        return 1
    }

    local total
    total=$(echo "$response" | jq '.data | length' 2>/dev/null) || total=0

    if [[ "$total" -eq 0 ]]; then
        echo -e "${YELLOW}⚠${NC} 未配置任何上游账号"
        return 0
    fi

    local healthy=0
    local unhealthy=0

    for i in $(seq 0 $((total - 1))); do
        local name status
        name=$(echo "$response" | jq -r ".data[$i].name // \"account-$i\"" 2>/dev/null)
        status=$(echo "$response" | jq -r ".data[$i].status // \"unknown\"" 2>/dev/null)

        if [[ "$status" == "active" || "$status" == "healthy" ]]; then
            echo -e "${GREEN}✓${NC} 上游账号 [${name}] 正常"
            ((healthy++))
        else
            echo -e "${RED}✗${NC} 上游账号 [${name}] 异常 (状态: ${status})"
            ((unhealthy++))
        fi
    done

    echo -e "   上游账号汇总: ${GREEN}${healthy} 正常${NC} / ${RED}${unhealthy} 异常${NC}"

    if [[ "$unhealthy" -gt 0 ]]; then
        return 1
    fi
    return 0
}

send_alert() {
    local message="$1"

    if [[ -z "$ALERT_WEBHOOK" ]]; then
        return 0
    fi

    local payload
    payload=$(jq -n \
        --arg text "$message" \
        '{text: $text}')

    curl -s -o /dev/null \
        --max-time 10 \
        -X POST \
        -H "Content-Type: application/json" \
        -d "$payload" \
        "$ALERT_WEBHOOK" 2>/dev/null || true
}

run_health_check() {
    local failed=0
    local start_time
    start_time=$(date '+%s')

    echo ""
    echo "=========================================="
    echo " AI Token Gateway 健康检查"
    echo " $(date '+%Y-%m-%d %H:%M:%S')"
    echo "=========================================="
    echo ""

    # 1. 服务健康
    check_gateway_health || ((failed++))
    echo ""

    # 2. 基础设施
    check_database    || ((failed++))
    check_redis       || ((failed++))
    echo ""

    # 3. API 接口
    if [[ -n "$ADMIN_TOKEN" ]]; then
        check_api_endpoint "/v1/models" "模型列表接口" || ((failed++))
    fi
    echo ""

    # 4. 上游账号
    check_upstream_accounts || ((failed++))

    local end_time
    end_time=$(date '+%s')
    local duration=$((end_time - start_time))

    echo ""
    echo "------------------------------------------"
    if [[ "$failed" -eq 0 ]]; then
        echo -e "${GREEN}全部检查通过${NC}（耗时 ${duration}s）"
        log "INFO" "健康检查通过（耗时 ${duration}s）"
    else
        echo -e "${RED}${failed} 项检查失败${NC}（耗时 ${duration}s）"
        log "ERROR" "${failed} 项检查失败（耗时 ${duration}s）"
        send_alert "⚠️ AI Token Gateway 健康检查告警：${failed} 项检查失败，请立即检查！"
    fi
    echo "------------------------------------------"
    echo ""

    return "$failed"
}

# ----- 参数解析 -----
LOOP_MODE=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --loop)
            LOOP_MODE=true
            shift
            ;;
        --alert-webhook)
            ALERT_WEBHOOK="$2"
            shift 2
            ;;
        --gateway-url)
            GATEWAY_URL="$2"
            shift 2
            ;;
        --admin-token)
            ADMIN_TOKEN="$2"
            shift 2
            ;;
        --interval)
            CHECK_INTERVAL="$2"
            shift 2
            ;;
        --help)
            echo "用法: $0 [选项]"
            echo ""
            echo "选项:"
            echo "  --loop                 持续检查模式"
            echo "  --interval <秒>        检查间隔（默认 30 秒）"
            echo "  --gateway-url <URL>    Gateway 地址（默认 http://localhost:8080）"
            echo "  --admin-token <token>  管理员 API Token"
            echo "  --alert-webhook <URL>  告警通知 Webhook 地址"
            echo "  --help                 显示帮助信息"
            exit 0
            ;;
        *)
            echo "未知参数: $1"
            exit 1
            ;;
    esac
done

# ----- 主程序 -----
if [[ "$LOOP_MODE" == true ]]; then
    log "INFO" "启动持续健康检查模式（间隔 ${CHECK_INTERVAL}s）"
    while true; do
        run_health_check || true
        sleep "$CHECK_INTERVAL"
    done
else
    run_health_check
fi
