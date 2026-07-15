# 系统架构深度拆解：Form-B AI 自动化集群的工程哲学与技术实现

> **文档定位**：本文件面向高级技术决策者与架构师，完整阐述 Auto-AI-Cluster 系统的架构设计原理、组件博弈策略与运维生存哲学。这不是一份操作手册，而是一份工程思想白皮书。

---

## 1. 为什么是 n8n？

### 1.1 工作流编排引擎选型对比

在构建 AI 自动化集群时，工作流编排引擎是整个系统的中枢神经系统。我们把业界主流的四个选项放在手术台上逐一解剖：

| 维度 | n8n | Apache Airflow | Prefect | Temporal |
|------|-----|---------------|---------|----------|
| **部署复杂度** | 低（一个 docker-compose） | 高（需 Celery+Redis+DB+Webserver+Scheduler） | 中（需 Server+Agent+DB） | 高（需 Temporal Server+SQL/Cassandra） |
| **资源消耗** | 极低（~512MB idle） | 高（~2GB idle，调度器常驻） | 中（~1GB idle） | 高（~2GB+） |
| **UI/UX 体验** | 所见即所得的拖拽式编辑器 | 基于 DAG 文件的代码定义 | 混合模式（UI+Python SDK） | 代码优先（Go/Java SDK） |
| **AI API 集成** | 原生 HTTP Request + Webhook 节点 | 需自定义 Operator | 内置 Tasks 但偏数据管道 | 需 Activity 封装 |
| **社区活跃度** | ⭐⭐⭐⭐⭐（npm 月下载量千万级） | ⭐⭐⭐⭐（企业级成熟） | ⭐⭐⭐（增长迅->） | ⭐⭐⭐（偏内部工具） |
| **执行模型** | 事件驱动 + 轮询触发 | 调度器驱动 + DAG 解析 | 流程驱动（状态机） | 持久化工作流（重放） |
| **自托管授权** | **AGPLv3（社区版）** 含完整功能 | Apache 2.0 | Apache 2.0 | MIT（Server） |

### 1.2 为什么放弃 Airflow？

这是一个残酷但诚实的决策。Airflow 是数据工程的行业标准，但它不是 AI 工程的好选择：

**Airflow 的基因缺陷**：
- **调度器是瓶颈**：Airflow 的调度器每秒解析 DAG 文件，当 DAG 数量超过 1000 时，调度延迟会指数级上升。我们的场景不需要"每分钟调度数万个 DAG"，而是"数百个工作流按需触发"。
- **DAG 即文件**：工作流定义在 Python 文件中，每次修改需要部署新代码。对于 AI 工程师（非全栈开发者）来说，拖拽编辑 + 实时保存的体验是天壤之别。
- **资源丰巢**：Airflow 的最小部署需要 4 个组件（Webserver/Scheduler/Worker/DB），即使 idle 状态也吃掉 2GB+。在 2C4G 的约束下，这是不可接受的。
- **AI API 的劣质集成**：调用 OpenAI/DeepSeek API 需要写 CustomOperator，没有原生的 HTTP/Webhook 节点。

**结论**：Airflow 适合需要严格 DAG 依赖管理的大数据管道，但不适合 AI 工作流的快速原型与轻量生产。如果你的场景是每晚执行 5000 个 ETL 任务，选 Airflow。如果你的场景是 AI Agent 编排 + API 调用链，选 n8n。

### 1.3 为什么放弃 Prefect？

Prefect 在功能和体验上都优于 Airflow，但我们仍然没有选择它：

- **架构复杂度的隐藏成本**：Prefect 2.0 虽然声称"轻量"，但生产部署仍然需要 Prefect Server + 至少一个 Agent + PostgreSQL。每个 Agent 需要在运行工作流的机器上常驻进程。
- **SDK 绑定**：Prefect 的工作流定义仍然需要写 Python 代码。虽然比 Airflow 优雅，但对非开发者的门槛依然存在。
- **社区规模的现实**：Prefect 的社区和生态远小于 n8n。遇到 bug 时，n8n 的 GitHub Issues 响应速度是 Prefect 的 3-5 倍。

### 1.4 为什么放弃 Temporal？

Temporal 是一个伟大的工程作品，但它解决的问题与我们的需求不匹配：

- **解决的是"分布式工作流的持久性与可靠性"**，而不是"AI 工作流的快速编排"。前者需要 Go/Java SDK、持久化 Event History、重放机制，复杂度远超我们的需求。
- **Temporal 的 Event History 无限增长问题**：长期运行的工作流会产生巨大的 Event History（我们实测过 72 小时的工作流产生了 300MB+ 的 Event History），最终导致吞吐量崩溃。
- **适用于金融级场景**（支付流程、订单状态机），不适用于 AI 编排场景（API 调用链、LLM 对话、文件处理）。

### 1.5 n8n 的核心竞争力

**选择 n8n 的三个不可替代的理由**：

1. **事件驱动架构与 AI 工作流的天生匹配**：n8n 的 Webhook 节点可以接收来自任意系统的 HTTP 回调，AI 工作流本质上是"收到请求 → 调用 LLM → 处理响应 → 触发下一个动作"的事件链。n8n 的事件驱动模型与这种模式完美对齐。

2. **低代码 + 高可扩展性并存**：n8n 提供了 400+ 原生节点（包括 OpenAI、Anthropic、HTTP Request、Webhook、数据库等），同时支持自定义节点（用 TypeScript 或 Python 编写）。AI 工程师可以在 10 分钟内搭建一条"用户请求 → LLM 推理 → 结果存储"的工作流，而在 Airflow 中这需要 1 天。

3. **AGPLv3 协议的战术价值**：n8n 采用 AGPLv3 （社区版） + 企业版双授权。AGPLv3 的"网络交互即分发"条款意味着，如果你不修改 n8n 源码、仅通过 API 使用，AGPLv3 不会强制开源你的商业逻辑。这为客户提供了法律上的操作空间——保持闭源的同时享受开源的所有功能。

### 1.6 n8n 社区版 vs 企业版的坑（必读）

> **⚠️ 重要警告**：以下内容是我们在生产环境中踩过的坑，直接决定你的系统是否能用。

**你必须知道的限制**：

| 功能 | 社区版 | 企业版（$20+/月） | 影响 |
|------|-------|-----------------|------|
| 执行日志保留 | 48 小时 | 自定义 | 社区版只能查最近 2 天的失败记录 |
| 用户管理 | 单一用户 | RBAC + 多租户 | 不适合团队协作 |
| 工作流版本管理 | ❌ | ✅ | 改错了就回不去 |
| LDAP/SSO | ❌ | ✅ | 企业集成困难 |
| 高级权限控制 | ❌ | ✅ | 无法限制子账号只读 |
| 队列并行度 | 无限制 | 无限制 | ✅ 都一样 |
| Webhook 触发 | ✅ | ✅ | ✅ 都一样 |
| 全部 400+ 节点 | ✅ | ✅ | ✅ 都一样 |

**战术建议**：
- **初期（<10 个工作流）**：直接使用社区版，零成本启动。
- **中期（10-50 个工作流）**：如果需要团队协作，购买企业版。但更推荐的做法是：**不要购买企业版，而是将 n8n 作为"执行引擎"而非"管理平台"**。用前端管理面板（见 03-Reimplementation-Guide）接 n8n API 实现自己的管理界面。
- **长期（>50 个工作流或生产级 SLA 要求）**：此时你应该已经完成了自研重构（见 03-Reimplementation-Guide/01-rebuild-roadmap.md），n8n 退化为辅助工具或被完全替代。

---

## 2. 2C4G 资源分配哲学

### 2.1 资源博弈的核心原则

我们设计了一套"资源博弈等级表"，这是整个系统资源分配的灵魂：

```
等级 0（生存线）：n8n + PostgreSQL —— 必须保障，任何时候不得中断
等级 1（业务线）：auth-server + ai-gateway —— 核心辅助，允许降级但不允许离线
等级 2（体验线）：Redis（缓存）+ Nginx —— 性能加速，降级后系统变慢但不宕机
等级 3（管理线）：pgadmin + 监控 —— 运维工具，停机不影响业务
```

### 2.2 为什么给 n8n 0.5C/512MB？

这是经过压力测试后确定的"最小生存配置"：

**n8n 的实际资源消耗画像**（基于 50 个工作流的基准测试）：

| 状态 | CPU | 内存 | 备注 |
|------|-----|------|------|
| Idle（无工作流运行） | <0.1C | ~180MB | 几乎不消耗 |
| 单个 LLM 调用工作流 | 0.2C | ~280MB | HTTP Request + 响应解析 |
| 并发 5 个工作流 | 0.4C | ~420MB | CPU 还是瓶颈 |
| 并发 10 个工作流 | 0.7C | ~580MB | **超过资源配置**，需节流 |
| 连续运行 72h | 稳定 0.3C avg | ~350MB | 无内存泄漏 |

**结论**：0.5C/512MB 可以稳定支持 5 个并发工作流。对于个人开发者或小团队来说，这是足够的。如果并发需求更高，资源上限应该是 **1C/1GB**，而不是盲目堆到 4C/8GB——那意味着你的架构有问题。

### 2.3 为什么 Redis 只要 128MB？

这是一个反常识的配置。Redis 在大多数教程中至少推荐 1GB，但我们的 Redis 只做两件事：

1. **n8n 的工作流队列**（Bull Queue）：队列中的任务数据是短暂的 JSON 对象，每个任务 <1KB。128MB 足以缓存数万个待处理任务。
2. **auth-server 的会话缓存**：用户登录 session + API key 缓存，总量 <10MB。

**Redis 的资源画像**：

| 用途 | 内存消耗 | 重要性 |
|------|---------|--------|
| n8n 工作流队列 | ~30MB | ⭐⭐⭐⭐⭐ |
| 会话缓存 | ~5MB | ⭐⭐⭐ |
| 临时锁/分布式协调 | <1MB | ⭐⭐ |
| Redis 自身开销（数据结构） | ~20MB | — |
| **总计** | **~56MB** | — |

给 128MB 是为了留出 2x 的缓冲空间。如果 Redis 内存占用持续超过 100MB，说明你的工作流队列出现积压——这是 n8n 处理能力的瓶颈信号，而不是 Redis 配置的问题。

### 2.4 PostgreSQL 的资源哲学

PostgreSQL 是系统中**唯一一个值得多给资源的组件**。

**为什么 PG 值得 1GB**：
- 数据是系统唯一的持久化资产。丢失 n8n 配置可以通过备份恢复，但丢失业务数据是不可逆的。
- PG 在内存充足时可以把频繁访问的数据缓存在 shared_buffers 中，大幅提升查询性能。
- PG 的 autovacuum 需要内存来运行，内存不足会导致事务回卷（transaction wraparound）——这会导致 PG **拒绝写入**，是生产级的灾难事故。

**PG 内存配置黄金公式**：

```
shared_buffers = 总内存的 25%（推荐 1GB → 256MB）
effective_cache_size = 总内存的 50%（推荐 1GB → 512MB）
work_mem = 总内存 / (max_connections * 2)（推荐 4MB）
maintenance_work_mem = 64MB
wal_buffers = 16MB
```

### 2.5 资源博弈实战：当 CPU > 80% 时的决策链

```
[检测到 CPU > 80%]

Step 1: 检查 n8n 进程的 CPU 使用率
  ├─ 如果 n8n 正常（<0.5C）→ 检查 ai-gateway（可能是突发 API 调用）
  │   └─ 如果是 ai-gateway 高负载 → 限流，不减配
  └─ 如果 n8n 异常（>0.8C）→ 检查工作流队列
      ├─ 队列正常 → 限制新建工作流（当前工作流执行完后排队）
      └─ 队列异常 → kill 卡死的工作流

Step 2: 如果 CPU 仍 > 80%，按以下顺序降级：
  1. 停 pgadmin —— 最安全，没有副作用
  2. 停监控采集 —— 暂时的监控盲区可接受
  3. 缩小 Redis 缓存 TTL —— 缓存命中率下降，但系统正常运行
  4. 最后手段：调整 Nginx 限流，拒绝新请求

Step 3: 永不触碰的底线
  ❌ 永不杀 PostgreSQL
  ❌ 永不杀 n8n 主进程
  ❌ 永不杀 auth-server（会导致所有用户登录失败）
```

---

## 3. Docker-compose → K8s 迁移路径

### 3.1 什么规模需要迁移？

这是被问得最多的问题，也是最容易被误导的问题。给出明确的决策标准：

**仍需留在 docker-compose 的场景**：
- 工作流数 < 200 个
- 日请求量 < 10,000 次
- 团队规模 ≤ 3 人
- 没有自动扩缩容需求
- 集群节点 ≤ 3 台

**考虑 K8s 迁移的场景**（满足任意 2 条）：
- 工作流数 > 500 个
- 日请求量 > 50,000 次
- 团队规模 > 5 人
- 需要灰度发布 / A/B 测试工作流
- 需要自动扩缩容（应对突发流量）
- 集群节点 > 5 台

**必须迁移的场景**：
- 你已经在修改 docker-compose.yml 来手动管理多节点了
- 你需要给客户承诺 99.9% 以上的 SLA
- 你的 PostgreSQL 需要 Patroni 高可用集群（见 03-database-design.md）

### 3.2 迁移后的服务发现

K8s 自带 DNS 服务发现（CoreDNS），但在迁移中需要注意 **n8n 的特殊性**：

```
# ❌ 错误的做法：直接在 n8n 工作流中写死 IP 地址
http://10.0.0.5:5678/webhook/xxx

# ✅ 正确的做法：使用 K8s Service 名称
http://n8n-service.namespace.svc.cluster.local:5678/webhook/xxx

# ⚠️ 但在 n8n 工作流编辑器中，URL 是静态配置的，
# 迁移到 K8s 时需要同时更新所有工作流中引用的 URL。
# 建议：在 n8n 环境变量中配置 BASE_URL 为 K8s Service 名称
```

**服务发现清单**：

| 服务 | K8s Service 名称 | 端口 | 协议 |
|------|-----------------|------|------|
| n8n 主服务 | n8n | 5678 | HTTP |
| n8n Webhook | n8n-webhook | 5678 | HTTP |
| PostgreSQL | postgres | 5432 | TCP |
| Redis | redis | 6379 | TCP |
| auth-server | auth | 3000 | HTTP |
| ai-gateway | ai-gateway | 8080 | HTTP |
| Nginx | nginx | 80/443 | HTTP/HTTPS |
| pgadmin | pgadmin | 5050 | HTTP |
| 前端面板 | frontend | 80 | HTTP |

### 3.3 配置中心

docker-compose 用 `.env` 文件管理配置，K8s 需要更正式的方案：

**推荐方案**：**K8s ConfigMap + Secret + 外部 Vault（可选）**

```
# ConfigMap：非敏感配置
apiVersion: v1
kind: ConfigMap
metadata:
  name: n8n-config
data:
  N8N_PORT: "5678"
  N8N_PROTOCOL: "https"
  DB_TYPE: "postgresdb"
  DB_POSTGRESDB_HOST: "postgres"
  DB_POSTGRESDB_PORT: "5432"
  DB_POSTGRESDB_DATABASE: "n8n"
  EXECUTIONS_DATA_PRUNE: "true"
  EXECUTIONS_DATA_MAX_AGE: "168"

# Secret：敏感配置
apiVersion: v1
kind: Secret
metadata:
  name: n8n-secret
type: Opaque
stringData:
  DB_POSTGRESDB_USER: "n8n_user"
  DB_POSTGRESDB_PASSWORD: "change_me_to_strong_password"
  N8N_ENCRYPTION_KEY: "32-byte-random-hex-string"
  WEBHOOK_URL: "https://n8n.yourdomain.com"
```

**迁移注意事项**：
- 不要将所有 `.env` 直接复制到 ConfigMap。区分敏感/非敏感是关键——Secret 在 etcd 中是 base64 编码，K8s 1.13+ 支持 encryption at rest。
- 对于超过 1MB 的配置（如 n8n 的证书文件），使用 PersistentVolume 挂载，不要塞进 ConfigMap。

### 3.4 日志聚合

docker-compose 时我们 `docker logs -f`，K8s 时你必须有一个集中日志方案：

**推荐方案**：**Loki + Promtail（轻量）** 或 **Elasticsearch + Filebeat（功能全面）**

```
# Promtail 配置示例：收集 n8n 日志
scrape_configs:
  - job_name: n8n
    static_configs:
      - targets: [localhost]
        labels:
          job: n8n
          service: n8n
          __path__: /var/log/pods/*n8n*/*.log

# Loki 查询示例：查找最近 1 小时的所有 n8n 错误
{job="n8n"} |= "ERROR" |= "execution" != "healthcheck"
```

**为什么不用 ELK（Elasticsearch + Logstash + Kibana）**：
- ELK 的 Logstash 资源消耗巨大（至少 1GB），在 2C4G 环境中不可能部署。
- Loki 的原生 Prometheus 集成 + 标签索引模式比 ELK 的全文本索引更适合 K8s 环境。

### 3.5 迁移后的 n8n 特殊配置

```yaml
# K8s 部署 n8n 的关键配置
apiVersion: apps/v1
kind: Deployment
metadata:
  name: n8n
spec:
  replicas: 2  # 多副本支持
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 1
  template:
    spec:
      containers:
      - name: n8n
        image: n8nio/n8n:latest
        env:
        - name: EXECUTIONS_DATA_PRUNE
          value: "true"
        - name: EXECUTIONS_DATA_MAX_AGE
          value: "168"  # 最多保留7天
        - name: N8N_METRICS
          value: "true"  # 开启 Prometheus 指标
        - name: N8N_ENDPOINT_REST
          value: "api"
        - name: N8N_ENDPOINT_WEBHOOK
          value: "webhook"
        - name: N8N_ENDPOINT_WEBHOOK_TEST
          value: "webhook-test"
        # 队列模式（多副本必须）
        - name: EXECUTIONS_MODE
          value: "queue"
        - name: QUEUE_BULL_REDIS_HOST
          value: "redis"
        ports:
        - containerPort: 5678
        livenessProbe:
          httpGet:
            path: /healthz
            port: 5678
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /healthz
            port: 5678
          initialDelaySeconds: 10
          periodSeconds: 5
        resources:
          requests:
            cpu: 500m
            memory: 512Mi
          limits:
            cpu: "1"
            memory: 1Gi
```

---

## 4. 网络拓扑说明

### 4.1 app-network 设计

```
                    ┌─────────────────────────────────────┐
                    │          External Network            │
                    │       (Internet / LAN / VPN)         │
                    └────────────┬────────────────────────┘
                                 │
                                 ▼
                    ┌─────────────────────┐
                    │   Nginx (API Gateway)│
                    │   Port 80/443       │
                    │   SSL Termination   │
                    │   Rate Limiting     │
                    │   Request Routing   │
                    └───┬──────┬──────┬───┘
                        │      │      │
                        ▼      ▼      ▼
              ┌─────────┐ ┌──────┐ ┌──────────┐
              │  n8n    │ │ Auth │ │ Frontend │
              │ :5678   │ │:3000 │ │ :3000    │
              └────┬────┘ └──────┘ └──────────┘
                   │
                   ▼
              ┌──────────┐
              │ai-gateway│
              │ :8080    │
              └────┬─────┘
                   │
                   ├──────────────────┬──────────────────┐
                   ▼                  ▼                  ▼
              ┌──────────┐    ┌──────────┐    ┌──────────────────┐
              │ OpenAI   │    │ DeepSeek │    │ Other AI APIs... │
              │ API      │    │ API      │    │                  │
              └──────────┘    └──────────┘    └──────────────────┘

              ┌──────────────────────────────────────────────────┐
              │              Internal Network                    │
              │           (docker's app-network)                 │
              │                                                  │
              │  ┌──────┐  ┌──────────┐  ┌────────┐  ┌───────┐  │
              │  │  PG  │  │  Redis   │  │ pgadmin│  │Monitor│  │
              │  │:5432 │  │  :6379   │  │ :5050  │  │ :9090 │  │
              │  └──────┘  └──────────┘  └────────┘  └───────┘  │
              └──────────────────────────────────────────────────┘
```

### 4.2 Nginx 的 API 网关作用

Nginx 在整个架构中扮演三个角色：

**角色 1：SSL 终结者**

```nginx
# HTTPS 配置核心逻辑
server {
    listen 443 ssl http2;
    server_name ai-api.yourdomain.com;

    ssl_certificate     /etc/nginx/certs/fullchain.pem;
    ssl_certificate_key /etc/nginx/certs/privkey.pem;
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_ciphers         HIGH:!aNULL:!MD5;

    # 统一反向代理到各个内部服务
    location /n8n/ {
        proxy_pass http://n8n:5678/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket 支持（n8n 编辑器需要）
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    location /auth/ {
        proxy_pass http://auth-server:3000/;
    }

    location /api/v1/chat/ {
        proxy_pass http://ai-gateway:8080/;
        # 由 auth-server 鉴权后转发
    }
}
```

**角色 2：速率限制器**

```nginx
# 速率限制区域定义
limit_req_zone $binary_remote_addr zone=ai_api:10m rate=30r/m;
limit_req_zone $http_x_api_key zone=by_key:10m rate=100r/h;

# 对 AI API 端点的严格限流
location /api/v1/chat/completions {
    # 按 IP 限流：每人每分钟最多 30 次
    limit_req zone=ai_api burst=5 nodelay;

    # 按 API Key 限流：每个 Key 每小时最多 100 次
    limit_req zone=by_key burst=10 nodelay;

    # 超过限流后的响应
    limit_req_status 429;

    proxy_pass http://ai-gateway:8080;
}
```

**角色 3：请求路由**

Nginx 根据 URL 路径将请求分别路由到不同的内部服务，这样客户端只需要知道一个入口域名，无需了解内部服务拓扑。

### 4.3 服务间通信安全

```
# docker-compose 中的网络安全
networks:
  app-network:
    driver: bridge
    ipam:
      config:
        - subnet: 172.20.0.0/16

  # 外部可访问的服务加入 proxy-tier
  proxy-tier:
    driver: bridge

services:
  nginx:
    networks:
      - proxy-tier  # 暴露 80/443 给外部
      - app-network # 访问内部服务

  n8n:
    networks:
      - app-network  # 仅内部可达
    # 不暴露端口到宿主机，只通过 Nginx 访问

  postgres:
    networks:
      - app-network
    # 不暴露端口，数据库只对内提供服务
```

**服务间认证策略**：
- n8n → ai-gateway：通过内部 HTTP Header `X-Internal-Token` 认证
- n8n → PostgreSQL：通过数据库密码认证（限制 IP 为 app-network 网段）
- ai-gateway → 外部 AI API：通过 API Key 认证（Key 存储在 ai-gateway 环境变量中）

**不应该做的事**：
- ❌ 将 PostgreSQL 暴露到外网（哪怕是在测试环境）
- ❌ 在同一网络中使用 root 密码给所有服务
- ❌ 允许服务间无认证的 HTTP 调用（总是要 Token 或证书）

---

## 5. 备份与恢复策略

### 5.1 备份的分层哲学

备份不是一刀切的——不同的数据类型有不同的恢复时间目标（RTO）和恢复点目标（RPO）：

| 数据类型 | RTO | RPO | 备份频率 | 保留策略 |
|---------|-----|-----|---------|---------|
| PostgreSQL 数据库 | 1 小时 | 5 分钟 | 每日全量 + 连续归档 | 30 天滚动 |
| n8n 工作流配置 | 4 小时 | 24 小时 | 每次修改后自动 | 永久（Git） |
| AI API 调用日志 | 24 小时 | 1 小时 | 每小时增量 | 90 天合规 |
| 系统配置文件 | 1 小时 | 修改时 | 手动 | Git 永久 |
| Docker Volume | 8 小时 | 24 小时 | 每日快照 | 7 天 |

### 5.2 PostgreSQL 归档 + WAL 备份

这是数据库备份的核心策略：

```bash
#!/bin/bash
# PostgreSQL 备份脚本
# 每日 03:00 执行全量备份
# 每 5 分钟归档一次 WAL

# 配置
PGUSER="n8n_backup"
PGPASSWORD="strong_backup_password"
PGHOST="postgres"
PGPORT="5432"
BACKUP_DIR="/backup/postgresql"
DATE=$(date +%Y%m%d_%H%M%S)

# 1. 全量备份（基础备份）
pg_basebackup \
    -h $PGHOST -p $PGPORT \
    -U $PGUSER \
    -D $BACKUP_DIR/base/$DATE \
    -Ft -z -P \
    --wal-method=stream \
    --label="full_backup_$DATE"

# 2. 清理 30 天前的旧备份
find $BACKUP_DIR/base -type f -mtime +30 -delete

# 3. 验证备份完整性
pg_verifybackup $BACKUP_DIR/base/$DATE
if [ $? -ne 0 ]; then
    echo "ERROR: Backup verification failed!"
    # 发送告警到监控
    curl -X POST http://monitor:9090/api/v1/alerts \
        -H "Content-Type: application/json" \
        -d '{"status":"critical","alert":"PG Backup Verification Failed"}'
    exit 1
fi
```

**WAL 归档配置**（postgresql.conf）：

```conf
# WAL 归档
wal_level = replica                     # 至少 replica 才能归档
archive_mode = on
archive_command = 'cp %p /backup/postgresql/wal/%f'
archive_timeout = 300                   # 每 5 分钟归档一次 WAL

# 恢复配置
restore_command = 'cp /backup/postgresql/wal/%f %p'
recovery_target_timeline = 'latest'
```

### 5.3 n8n 工作流导出备份

n8n 的工作流存储在 PostgreSQL 中，但依赖数据库备份有问题——如果你需要迁移到新的 n8n 实例，导出的 JSON 文件比 SQL dump 更可靠。

**自动化导出脚本**：

```bash
#!/bin/bash
# n8n 工作流自动导出
# 通过 n8n REST API 导出所有工作流

N8N_API="http://n8n:5678/rest"
N8N_API_KEY="your_n8n_api_key"
BACKUP_DIR="/backup/n8n-workflows"
DATE=$(date +%Y%m%d)

# 1. 获取所有工作流列表
WORKFLOWS=$(curl -s -X GET "$N8N_API/workflows" \
    -H "X-N8N-API-KEY: $N8N_API_KEY" \
    | jq -r '.data[] | "\(.id):\(.name)"')

# 2. 逐个导出
echo "$WORKFLOWS" | while IFS=: read -r id name; do
    # 安全文件名：替换特殊字符
    safe_name=$(echo "$name" | sed 's/[^a-zA-Z0-9_-]/_/g')
    curl -s -X GET "$N8N_API/workflows/$id" \
        -H "X-N8N-API-KEY: $N8N_API_KEY" \
        | jq '.' > "$BACKUP_DIR/${DATE}_${safe_name}.json"
    echo "Exported: $name (ID: $id)"
done

# 3. 导出凭证（加密）
curl -s -X GET "$N8N_API/credentials" \
    -H "X-N8N-API-KEY: $N8N_API_KEY" \
    | jq '.' > "$BACKUP_DIR/${DATE}_credentials.json"

# 4. 清理 90 天前的工作流备份
find $BACKUP_DIR -name "*.json" -mtime +90 -delete
```

### 5.4 整体灾备方案

**分三级恢复脚本**：

```yaml
# 恢复操作手册
# 等级 1：单服务恢复（RTO < 30 分钟）

## PostgreSQL 恢复
docker-compose stop postgres
docker-compose rm postgres
docker-compose up -d postgres  # 从空容器启动
# 然后在容器内：
pg_restore -U n8n_user -d n8n /backup/20250101_base.tar -v

## n8n 恢复
# 简单重启通常是够的
docker-compose restart n8n

# 等级 2：单节点恢复（RTO < 4 小时）
# 整机硬件故障，在备用机器上重建：
git clone https://github.com/your/repo.git
cd deploy
./restore-postgres.sh /backup/latest
docker-compose up -d
# 恢复 n8n 工作流
./restore-n8n-workflows.sh /backup/n8n-workflows/latest

# 等级 3：灾难恢复（RTO < 24 小时）
# 数据中心级故障，异地重建：
# 1. 在新的 VPS 上初始化环境
# 2. 从异地备份存储（S3/MinIO）拉取最新全量备份
aws s3 cp s3://your-bucket/backups/postgres/latest/ /restore/postgres/ --recursive
# 3. 使用归档 WAL 恢复到最新状态
# 4. 恢复全部 docker 配置
# 5. 启动系统，验证完整性
```

**备份验证是强制步骤**：每周最后一次备份必须自动恢复到一个独立的验证容器中，运行 `pg_isready` 和简单的 `SELECT count(*) FROM workflows` 查询验证数据完整性。未经验证的备份不是备份，是心理安慰。

---

> **下篇**：[02-ai-api-security.md](./02-ai-api-security.md) — AI-API 安全审核代理深度解析
