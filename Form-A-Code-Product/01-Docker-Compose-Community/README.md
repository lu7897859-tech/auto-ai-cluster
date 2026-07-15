# Form-A 自主AI分析集群 · 社区分发版

> **docker-compose 一键部署的自主AI分析集群**，集成工作流引擎、AI安全网关、授权管理，开箱即用。

## 适用场景

- **自主AI代理集群** — 搭建个人/团队级的多Agent协同分析平台
- **AI API 安全管控** — 对AI调用进行鉴权、限流、审计，防止滥用
- **工作流自动化** — 使用 n8n 编排 AI + 传统业务逻辑的工作流
- **企业PoC 快速验证** — 5分钟部署，快速向客户演示 AI 分析能力
- **本地开发/测试环境** — 完整的微服务架构，助力 AI 应用本地调试

## 架构总览

```
┌─────────────────────────────────────────────────────┐
│                     Nginx (80/443)                    │
│                  API 网关 / 反向代理                   │
└─┬──────────┬──────────┬──────────┬─────────────────┘
  │          │          │          │
  ▼          ▼          ▼          ▼
┌──────┐ ┌────────┐ ┌─────────┐ ┌──────────┐
│ n8n  │ │ Auth   │ │AI-Gatewy│ │ pgAdmin  │
│工作流 │ │授权服务│ │安全审核  │ │数据库管理 │
│:5678 │ │:4000   │ │:5000    │ │:5050     │
└──┬───┘ └───┬────┘ └────┬────┘ └──────────┘
   │         │           │
   └─────────┼───────────┘
             ▼
     ┌──────────────┐
     │  PostgreSQL   │ ─── Redis (缓存/队列)
     │   主数据库     │
     └──────────────┘
```

## 部署要求

| 项目 | 要求 |
|------|------|
| **Docker** | 24.0+（含 Docker Compose v2） |
| **CPU** | 2 核（推荐 4 核） |
| **内存** | 4 GB（推荐 8 GB） |
| **磁盘** | 20 GB 可用空间 |
| **OS** | Linux / macOS / WSL2 |

## 快速开始

```bash
# 1. 进入部署目录
cd 01-Docker-Compose-Community

# 2. 复制配置并修改密码
cp .env.example .env
# 编辑 .env，将所有 changeme 改为强密码

# 3. 一键部署
bash deploy.sh
```

部署完成后可通过以下地址访问：

| 服务 | 地址 | 默认账号 |
|------|------|---------|
| **n8n 工作流引擎** | http://localhost:5678 | admin / changeme |
| **pgAdmin 管理** | http://localhost:5050 | admin@form-a.local / changeme |
| **Auth 授权服务** | http://localhost:4000/health | — |
| **AI 安全网关** | http://localhost:5000/health | API Key: changeme |
| **Nginx 入口** | http://localhost | — |

> ⚠ **首次部署后请立即修改 .env 中的所有默认密码！**

## 目录结构

```
01-Docker-Compose-Community/
├── docker-compose.yml       # 主编排文件（7 个服务）
├── .env.example             # 环境变量模板
├── .env                     # 实际配置（需从模板复制）
├── deploy.sh                # 一键部署脚本
├── healthcheck.sh           # 运维健康检查脚本
├── README.md                # 本文件
└── nginx/
    ├── nginx.conf           # Nginx 主配置
    ├── conf.d/
    │   └── default.conf     # 站点配置（反向代理规则）
    ├── ssl/                 # SSL 证书目录（启用 HTTPS 时使用）
    └── www/
        └── index.html       # Nginx 默认欢迎页
```

## 服务详情

### n8n — 工作流引擎
- 基于视觉的工作流自动化平台
- 支持 400+ 集成（OpenAI、HTTP、数据库、Slack 等）
- 预配置 PostgreSQL 持久化，Redis 队列
- 内置基本认证

### PostgreSQL — 主数据库
- 存储 n8n 工作流数据、Auth 授权数据
- 预留高可用扩展接口
- 基于 WAL 的持续归档支持

### pgAdmin — 数据库管理
- Web 界面的 PostgreSQL 管理工具
- 预连接到 postgres 服务
- 无需密码模式（方便调试，生产环境需修改）

### Redis — 缓存 / 消息队列
- n8n 工作流队列后端
- Auth 服务会话缓存
- AI-Gateway 限流计数器

### Auth — 授权服务中心
- License 验证（社区版免费）
- JWT 令牌签发与校验
- API Key 管理
- 基于角色的访问控制（RBAC）

### AI-Gateway — AI API 安全审核代理
- API Key 鉴权
- 请求速率限制（可配置窗口/上限）
- 完整的请求审计日志
- 内容合规过滤
- 授权服务集成

### Nginx — API 网关
- 统一入口 /n8n/ /auth/ /ai/
- SSL 终端（需配置证书）
- 反向代理 + 负载均衡
- 请求体上限 50MB
- WebSocket 升级支持

## 运维命令

```bash
# 查看所有容器状态
docker compose ps

# 查看实时日志
docker compose logs -f

# 查看指定服务日志
docker compose logs -f n8n

# 重启服务
docker compose restart nginx

# 停止集群
docker compose down

# 停止并清理数据卷（⚠ 清空所有数据）
docker compose down -v

# 重新构建镜像
docker compose build --no-cache

# 更新到最新镜像
docker compose pull
docker compose up -d
```

## 授权说明

| 版本 | 价格 | 功能差异 |
|------|------|---------|
| **社区版** (本版本) | 免费 🆓 | 完整功能集，无限节点，Apache 2.0 许可证 |
| **企业版** | 需购买 License | 额外包含：SSO 集成、审计合规面板、高可用部署模板、商业支持 SLA |

社区版完整可用，不存在功能阉割。企业版 License 主要提供的是企业级运维支持和合规组件。

**关于 License Key**：社区版部署时 `.env` 中 `AUTH_LICENSE_KEY` 留空即可。企业版用户填写购买后获得的 License Key。

## 升级路径

```bash
# 从社区版 → 企业版
# 1. 获取企业版 License Key
# 2. 更新 .env 中的 AUTH_LICENSE_KEY
# 3. 拉取企业版镜像
docker compose pull
# 4. 平滑重启
docker compose up -d --remove-orphans
```

## 安全注意事项

1. ⚠ **首次部署必须修改所有 changeme 密码**
2. 生产环境建议启用 Nginx SSL（配置证书至 `nginx/ssl/` 并设置 `NGINX_SSL_ENABLED=true`）
3. 建议使用强密码：`openssl rand -base64 32` 生成
4. 定期更新镜像：`docker compose pull && docker compose up -d`
5. 开启防火墙，仅暴露必要的端口（80/443）

## 环境变量速查

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `POSTGRES_PASSWORD` | changeme | PostgreSQL 密码 |
| `N8N_ENCRYPTION_KEY` | changeme | n8n 加密密钥（务必修改） |
| `N8N_BASIC_AUTH_PASSWORD` | changeme | n8n Web UI 登录密码 |
| `AUTH_LICENSE_KEY` | (空) | 企业版 License Key，社区版留空 |
| `AI_GATEWAY_API_KEY` | changeme | AI 网关 API Key |
| `REDIS_PASSWORD` | changeme | Redis 密码 |
| `DOMAIN` | localhost | 部署域名（用于反向代理） |

## 常见问题

**Q: 为什么容器启动后无法访问？**
A: 首次启动需要拉取镜像并等待所有服务健康检查通过（约 1-3 分钟）。运行 `./healthcheck.sh` 查看状态。

**Q: 如何启用 HTTPS？**
A: 将 SSL 证书放入 `nginx/ssl/`，并修改 `nginx/conf.d/default.conf` 中的 server 配置，设置 `.env` 中 `NGINX_SSL_ENABLED=true`。

**Q: 如何备份数据？**
A: Docker 数据卷存储在 `/var/lib/docker/volumes/` 下。可通过 `docker run --rm -v postgres_data:/source -v $(pwd):/backup alpine tar czf /backup/postgres_backup.tar.gz -C /source .` 备份。

**Q: 宿主机端口冲突怎么办？**
A: 修改 `docker-compose.yml` 中 ports 映射的宿主机端口，例如 `"5678:5678"` → `"8080:5678"`。

---

**Form-A** — 自主AI分析集群 · 社区分发版
Apache 2.0 License · Built for the AI Era
