#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
# Form-A 社区分发版 · 运维健康检查脚本
# ═══════════════════════════════════════════════════════════════
# 检查所有容器运行状态、资源占用、关键端口
# ═══════════════════════════════════════════════════════════════

set -euo pipefail

# ── 颜色 ──
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# ── 容器列表 ──
SERVICES=(
    "postgres:5432"
    "redis:6379"
    "n8n:5678"
    "auth:4000"
    "ai-gateway:5000"
    "pgadmin:5050"
    "nginx:80"
)

# ── 辅助函数 ──
info()  { echo -e "${BLUE}[INFO]${NC}  $1"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $1"; }
err()   { echo -e "${RED}[ERROR]${NC} $1"; }

# ── 横幅 ──
echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║      Form-A 集群 · 健康检查                      ║${NC}"
echo -e "${CYAN}║      $(date '+%Y-%m-%d %H:%M:%S')                    ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════╝${NC}"
echo ""

# ── 1. Docker Engine ──
echo -e "${BLUE}━━━ 1. Docker 引擎状态 ─────────────────────────${NC}"
if docker info --format '{{.ServerVersion}}' &>/dev/null; then
    DOCKER_VER=$(docker info --format '{{.ServerVersion}}' 2>/dev/null)
    CONT_RUNNING=$(docker info --format '{{.ContainersRunning}}' 2>/dev/null)
    CONT_TOTAL=$(docker info --format '{{.Containers}}' 2>/dev/null)
    ok "Docker Engine v${DOCKER_VER} | 运行中容器: ${CONT_RUNNING}/${CONT_TOTAL}"
else
    err "Docker 未运行或无法连接！"
    exit 1
fi
echo ""

# ── 2. Compose 项目状态 ──
echo -e "${BLUE}━━━ 2. Compose 项目状态 ─────────────────────────${NC}"
PROJECT=$(docker compose ls --format json 2>/dev/null | head -1 || echo "")
if [ -z "$PROJECT" ]; then
    err "未检测到运行中的 Compose 项目！"
    exit 1
fi
echo -e "  项目状态: $(docker compose ps --format json 2>/dev/null | head -1 | grep -oP '"Status":"[^"]*"' | head -1 || echo '未知')"
echo ""

# ── 3. 检查单个容器 ──
echo -e "${BLUE}━━━ 3. 容器健康状态 ─────────────────────────────${NC}"
echo ""
printf "  %-18s %-14s %-12s %-12s %s\n" "容器名" "状态" "健康" "重启次数" "端口映射"
printf "  %-18s %-14s %-12s %-12s %s\n" "──────────────────" "──────────────" "────────────" "────────────" "──────────────────"

ALL_HEALTHY=true
for svc_entry in "${SERVICES[@]}"; do
    CNAME="${svc_entry%%:*}"
    CPORT="${svc_entry##*:}"

    STATUS=$(docker inspect --format='{{.State.Status}}' "$CNAME" 2>/dev/null || echo "missing")
    HEALTH=$(docker inspect --format='{{.State.Health.Status}}' "$CNAME" 2>/dev/null || echo "none")
    RESTARTS=$(docker inspect --format='{{.RestartCount}}' "$CNAME" 2>/dev/null || echo "?")

    # 端口映射
    PORTS=$(docker port "$CNAME" 2>/dev/null | grep -oP '\d+\.\d+\.\d+\.\d+:\d+' | tr '\n' ',' | sed 's/,$//' || echo "-")

    # 着色
    STATUS_ICON=""
    case "$STATUS" in
        running) STATUS_ICON="${GREEN}" ;;
        exited|dead) STATUS_ICON="${RED}" ; ALL_HEALTHY=false ;;
        paused) STATUS_ICON="${YELLOW}" ;;
        *) STATUS_ICON="${YELLOW}" ;;
    esac

    HEALTH_ICON=""
    case "$HEALTH" in
        healthy) HEALTH_ICON="${GREEN}" ;;
        unhealthy) HEALTH_ICON="${RED}" ; ALL_HEALTHY=false ;;
        starting) HEALTH_ICON="${YELLOW}" ;;
        none) HEALTH_ICON="${CYAN}" ;;
        *) HEALTH_ICON="${YELLOW}" ;;
    esac

    printf "  ${STATUS_ICON}%-18s${NC} ${STATUS_ICON}%-14s${NC} ${HEALTH_ICON}%-12s${NC} %-12s %s\n" \
        "$CNAME" "$STATUS" "$HEALTH" "$RESTARTS" "$PORTS"
done
echo ""

# ── 4. 资源占用 ──
echo -e "${BLUE}━━━ 4. 资源占用 ─────────────────────────────────${NC}"
echo ""
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}\t{{.NetIO}}" 2>/dev/null || warn "无法获取资源占用信息"
echo ""

# ── 5. 磁盘空间 ──
echo -e "${BLUE}━━━ 5. Docker 磁盘占用 ─────────────────────────${NC}"
echo ""
docker system df 2>/dev/null || warn "无法获取磁盘信息"
echo ""

# ── 6. 关键端口可达性 ──
echo -e "${BLUE}━━━ 6. 关键端口可达性 ───────────────────────────${NC}"
echo ""
for svc_entry in "${SERVICES[@]}"; do
    CNAME="${svc_entry%%:*}"
    CPORT="${svc_entry##*:}"

    # 获取宿主机映射端口
    HOST_PORT=$(docker port "$CNAME" "$CPORT" 2>/dev/null | head -1 | grep -oP '\d+$' || echo "")

    if [ -n "$HOST_PORT" ]; then
        if nc -z -w3 127.0.0.1 "$HOST_PORT" 2>/dev/null; then
            ok "${CNAME} → 127.0.0.1:${HOST_PORT} ✔"
        else
            err "${CNAME} → 127.0.0.1:${HOST_PORT} ✘ 端口不可达"
        fi
    else
        warn "${CNAME} → 端口未映射到宿主机"
    fi
done
echo ""

# ── 7. 健康检查端点 ──
echo -e "${BLUE}━━━ 7. HTTP 健康端点 ────────────────────────────${NC}"
echo ""
HEALTH_ENDPOINTS=(
    "n8n:5678:/healthz"
    "auth:4000:/health"
    "ai-gateway:5000:/health"
    "nginx:80:/health"
)

for ep in "${HEALTH_ENDPOINTS[@]}"; do
    IFS=':' read -r name port path <<< "$ep"
    HOST_PORT=$(docker port "$name" "$port" 2>/dev/null | head -1 | grep -oP '\d+$' || echo "")
    if [ -n "$HOST_PORT" ]; then
        HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 3 "http://127.0.0.1:${HOST_PORT}${path}" 2>/dev/null || echo "000")
        if [ "$HTTP_CODE" = "200" ]; then
            ok "${name} → http://127.0.0.1:${HOST_PORT}${path} → ${HTTP_CODE} ✔"
        else
            warn "${name} → http://127.0.0.1:${HOST_PORT}${path} → ${HTTP_CODE}"
        fi
    else
        warn "${name} → 无法获取端口映射"
    fi
done
echo ""

# ── 8. 总结 ──
echo -e "${BLUE}━━━ 8. 总结 ─────────────────────────────────────${NC}"
echo ""
if [ "$ALL_HEALTHY" = true ]; then
    ok "所有服务正常运行，集群状态健康。"
else
    err "存在异常服务，请查看上方红色标记项。"
    echo ""
    warn "常用运维命令："
    warn "  docker compose logs <容器名>   # 查看日志"
    warn "  docker compose restart <容器名> # 重启指定服务"
    warn "  docker compose ps              # 查看进程状态"
fi
echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
