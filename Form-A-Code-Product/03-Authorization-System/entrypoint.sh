#!/bin/bash
# ─── Form-A 授权验证服务 启动入口 ───
set -e

echo "============================================"
echo "  Form-A Authorization Server Starting..."
echo "============================================"
echo "DB_PATH:            ${DB_PATH:-/app/data/auth.db}"
echo "PRIVATE_KEY_PATH:   ${PRIVATE_KEY_PATH:-/app/data/private.pem}"
echo "PUBLIC_KEY_PATH:    ${PUBLIC_KEY_PATH:-/app/data/public.pem}"
echo "PORT:               ${PORT:-5000}"
echo "============================================"

# 进入应用目录
cd /app

# 启动服务
exec python3 auth-server.py
