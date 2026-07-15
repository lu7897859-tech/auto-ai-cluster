#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
# Form-A 社区分发版 · 一键部署脚本
# ═══════════════════════════════════════════════════════════════
# 适用环境: Linux / macOS / WSL2
# 前置要求: Docker 24+ / Docker Compose v2
# ═══════════════════════════════════════════════════════════════

set -euo pipefail

# ── 颜色定义 ──
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ── 辅助函数 ──
info()  { echo -e "${BLUE}[INFO]${NC}  $1"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $1"; }
err()   { echo -e "${RED}[ERROR]${NC} $1"; }

# ── 横幅 ──
echo ""
echo -e "${BLUE}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║        Form-A 社区分发版 · 一键部署             ║${NC}"
echo -e "${BLUE}║        Auto-AI 分析集群                         ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════╝${NC}"
echo ""

# ── Step 1: 环境检查 ──
info "Step 1/5: 检查运行环境..."

# Docker
if command -v docker &>/dev/null; then
    DOCKER_VER=$(docker --version 2>/dev/null | grep -oP '\d+\.\d+' | head -1 || true)
    ok "Docker 已安装: $(docker --version 2>/dev/null)"
else
    err "未检测到 Docker。请先安装 Docker 24+："
    err "  https://docs.docker.com/engine/install/"
    exit 1
fi

# Docker Compose v2
if docker compose version &>/dev/null; then
    ok "Docker Compose v2 已安装: $(docker compose version 2>/dev/null)"
else
    err "未检测到 Docker Compose v2。请升级 Docker 至 24+。"
    exit 1
fi

# ── Step 2: .env ──
info "Step 2/5: 检查 .env 配置..."
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -f ".env" ]; then
    warn ".env 文件不存在，正在从 .env.example 创建..."
    cp .env.example .env
    ok ".env 已创建"
    echo ""
    warn "╔══════════════════════════════════════════════════════════════╗"
    warn "║  重要：请立即编辑 .env 文件，修改所有 'changeme' 密码！     ║"
    warn "║  编辑完成后重新运行本脚本即可继续部署。                     ║"
    warn "╚══════════════════════════════════════════════════════════════╝"
    echo ""
    echo -e "   ${YELLOW}vi .env${NC}"
    echo ""
    exit 0
fi

# 检查是否还有 changeme 密码
CHANGEME_COUNT=$(grep -c "changeme" .env 2>/dev/null || true)
if [ "$CHANGEME_COUNT" -gt 0 ]; then
    warn ".env 中仍有 ${CHANGEME_COUNT} 处密码未修改（包含 'changeme'）"
    echo ""
    read -r -p "  继续部署？密码将在生产环境暴露风险 [y/N] " confirm
    if [[ ! "$confirm" =~ ^[yY]$ ]]; then
        info "已取消部署。请修改 .env 中的密码后重试。"
        exit 0
    fi
fi

# ── Step 3: Nginx 目录 ──
info "Step 3/5: 检查 Nginx 配置目录..."
mkdir -p nginx/conf.d nginx/ssl nginx/www

# 默认 nginx.conf（如果不存在）
NGINX_CONF="nginx/nginx.conf"
if [ ! -f "$NGINX_CONF" ]; then
    info "创建默认 nginx.conf..."
    cat > "$NGINX_CONF" << 'NGINXEOF'
user  nginx;
worker_processes  auto;
error_log  /var/log/nginx/error.log warn;
pid        /var/run/nginx.pid;
events {
    worker_connections  1024;
    multi_accept on;
}
http {
    include       /etc/nginx/mime.types;
    default_type  application/octet-stream;
    log_format  main  '$remote_addr - $remote_user [$time_local] "$request" '
                      '$status $body_bytes_sent "$http_referer" '
                      '"$http_user_agent" "$http_x_forwarded_for"';
    access_log  /var/log/nginx/access.log  main;
    sendfile        on;
    tcp_nopush      on;
    tcp_nodelay     on;
    keepalive_timeout  65;
    types_hash_max_size 2048;
    client_max_body_size 50M;
    gzip  on;
    gzip_vary on;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml application/xml+rss text/javascript;

    include /etc/nginx/conf.d/*.conf;
}
NGINXEOF
    ok "默认 nginx.conf 已创建"
fi

# 默认站点配置（如果不存在）
VHOST_CONF="nginx/conf.d/default.conf"
if [ ! -f "$VHOST_CONF" ]; then
    info "创建默认站点配置..."
    cat > "$VHOST_CONF" << 'VHEOF'
# ── upstream 后端服务 ──
upstream n8n_backend {
    server n8n:5678;
}

upstream auth_backend {
    server auth:4000;
}

upstream ai_gateway_backend {
    server ai-gateway:5000;
}

# ── HTTP 站点 ──
server {
    listen 80;
    server_name _;
    server_tokens off;

    # ── n8n 工作流 ──
    location /n8n/ {
        proxy_pass http://n8n_backend/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 120s;
        proxy_send_timeout 120s;
    }

    # ── 授权服务 ──
    location /auth/ {
        proxy_pass http://auth_backend/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # ── AI 网关 ──
    location /ai/ {
        proxy_pass http://ai_gateway_backend/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # ── 健康检查 ──
    location /health {
        return 200 "OK\n";
        add_header Content-Type text/plain;
    }

    # ── 默认页 ──
    location / {
        root /var/www/html;
        index index.html;
    }
}
VHEOF
    ok "默认站点配置已创建"
fi

# 默认 index.html（如果不存在）
INDEX_HTML="nginx/www/index.html"
if [ ! -f "$INDEX_HTML" ]; then
    info "创建默认欢迎页..."
    cat > "$INDEX_HTML" << 'HTMLEOF'
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Form-A 自主AI分析集群</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #0f0c29, #302b63, #24243e);
            color: #fff;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .container {
            text-align: center;
            padding: 2rem;
            max-width: 600px;
        }
        h1 { font-size: 2.5rem; margin-bottom: 0.5rem; letter-spacing: -0.02em; }
        .subtitle { font-size: 1.1rem; opacity: 0.8; margin-bottom: 2rem; }
        .links { display: flex; flex-direction: column; gap: 0.75rem; }
        .links a {
            color: #a78bfa;
            text-decoration: none;
            padding: 0.75rem 1.5rem;
            border: 1px solid rgba(167, 139, 250, 0.3);
            border-radius: 8px;
            transition: all 0.2s;
        }
        .links a:hover {
            background: rgba(167, 139, 250, 0.1);
            border-color: #a78bfa;
        }
        .footer { margin-top: 2rem; font-size: 0.8rem; opacity: 0.5; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🚀 Form-A</h1>
        <p class="subtitle">自主AI分析集群 · 社区分发版</p>
        <div class="links">
            <a href="/n8n/">→ 进入 n8n 工作流引擎</a>
            <a href="/auth/">→ 授权服务中心</a>
            <a href="/health">→ 健康检查</a>
        </div>
        <p class="footer">Form-A 社区版 · 开源可分发 · 企业版需 License</p>
    </div>
</body>
</html>
HTMLEOF
    ok "默认欢迎页已创建"
fi

ok "Nginx 配置就绪"

# ── Step 4: 部署 ──
info "Step 4/5: 启动所有服务..."
info "拉取镜像..."
docker compose pull

info "启动容器..."
docker compose up -d --remove-orphans

# ── Step 5: 等待健康 ──
info "Step 5/5: 等待所有容器健康..."
SERVICES=$(docker compose config --services 2>/dev/null || true)
if [ -z "$SERVICES" ]; then
    # fallback
    SERVICES="postgres redis n8n auth ai-gateway pgadmin nginx"
fi

TIMEOUT=180
INTERVAL=10
ELAPSED=0

while [ $ELAPSED -lt $TIMEOUT ]; do
    ALL_HEALTHY=true
    for svc in $SERVICES; do
        STATUS=$(docker inspect --format='{{.State.Health.Status}}' "$svc" 2>/dev/null || echo "unhealthy")
        if [ "$STATUS" != "healthy" ]; then
            ALL_HEALTHY=false
            break
        fi
    done

    if [ "$ALL_HEALTHY" = true ]; then
        ok "所有容器运行健康！"
        break
    fi

    ELAPSED=$((ELAPSED + INTERVAL))
    info "等待容器就绪... (${ELAPSED}s / ${TIMEOUT}s)"
    sleep $INTERVAL
done

if [ "$ALL_HEALTHY" != true ]; then
    warn "部分容器未在 ${TIMEOUT}s 内达到健康状态。"
    warn "请运行 ./healthcheck.sh 查看详情。"
fi

# ── 输出访问信息 ──
DOMAIN="${DOMAIN:-localhost}"
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║       🚀 Form-A 集群已成功部署！                ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${BLUE}服务                   访问地址                         默认账号${NC}"
echo -e "  ─────────────────────────────────────────────────────────────────────────"
echo -e "  n8n 工作流              http://${DOMAIN}:5678                    admin / changeme"
echo -e "  pgAdmin 数据库管理      http://${DOMAIN}:5050                    admin@form-a.local / changeme"
echo -e "  授权服务 (Auth)         http://${DOMAIN}:4000/health"
echo -e "  AI 安全网关             http://${DOMAIN}:5000/health"
echo -e "  Nginx 入口              http://${DOMAIN}"
echo ""

if [ "$ALL_HEALTHY" = true ]; then
    ok "部署完成！请修改 .env 中的密码以保障生产安全。"
else
    warn "部署完成，但有服务未通过健康检查。请运行 ./healthcheck.sh 诊断。"
fi

echo ""
ok "如需停止集群: docker compose down"
ok "如需查看日志: docker compose logs -f"
