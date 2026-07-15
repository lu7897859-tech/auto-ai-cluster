# ─── Form-A 授权验证服务 Dockerfile ───
# 基于 Python 3.11-slim，轻量级部署
# 构建: docker build -t form-a-auth-server .
# 运行: docker run -d -p 5000:5000 -v auth-data:/app/data --name auth-server form-a-auth-server

FROM python:3.11-slim

LABEL maintainer="Form-A Team"
LABEL description="Form-A Authorization & License Management Server"
LABEL version="1.0.0"

# 设置工作目录
WORKDIR /app

# 安装系统依赖（SQLite 已内置在 Python 中）
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        # 用于机器指纹采集（dmidecode / lsblk）
        dmidecode \
        util-linux \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件并安装 Python 包
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY auth-server.py .
COPY entrypoint.sh .

# 创建数据目录
RUN mkdir -p /app/data

# 暴露 API 端口
EXPOSE 5000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/health')" || exit 1

# 使用 Shell 格式入口（支持环境变量）
ENTRYPOINT ["/bin/bash", "/app/entrypoint.sh"]
