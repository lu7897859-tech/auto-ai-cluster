# 数据库设计深度解析

> **文档定位**：本文件面向后端工程师与 DBA，阐述 PostgreSQL 选型理由、高可用方案、核心数据表概念设计以及数据归档策略。

---

## 1. PostgreSQL 选型理由

### 1.1 对比矩阵：为什么不是 MongoDB / MySQL / ClickHouse？

| 维度 | PostgreSQL | MySQL 8.0 | MongoDB 7.0 | ClickHouse |
|------|-----------|-----------|-------------|------------|
| **ACID 事务** | 完整 ACID（MVCC） | 完整 ACID（InnoDB） | 多文档事务（有限） | 不支持（NoSQL 分析型） |
| **JSON 支持** | JSONB 原生索引（GIN） | JSON 函数（有限索引） | BSON 原生（最佳） | JSON 函数 |
| **并发控制** | MVCC，`SELECT` 不阻塞 `INSERT` | MVCC，但间隙锁较多 | Optimistic Concurrency | LSM-Tree，不适用 OLTP |
| **扩展性** | 丰富扩展（PostGIS, pgvector, TimescaleDB） | 商业扩展（少） | 原生分片 | 列式，适合分析 |
| **高可用工具链** | Patroni + etcd（成熟） | Orchestrator / InnoDB Cluster | Replica Set（原生） | ClickHouse Keeper |
| **pgvector / AI** | ⭐⭐⭐⭐⭐ 原生向量索引 | ❌ 不支持 | ⭐⭐⭐ MongoDB Atlas | ❌ 不支持向量搜索 |
| **社区活跃度** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ |
| **资源占用** | 适中（256MB.可启动） | 较低（128MB 可启动） | 高（常驻 1GB+） | 高（列式存储内存密集） |

### 1.2 核心选型理由

**理由 1：ACID 事务与 AI 工作流的天然匹配**

AI 工作流的执行对数据一致性有严格要求：

```
场景：用户提交文档 → LLM 生成摘要 → 摘要存入数据库 → 触发通知

在 MySQL 的 Read Committed 隔离级别下：
  1. 事务 A：插入文档记录（未提交）
  2. 事务 B：查询文档列表（看到脏数据？→ MySQL RC 不会，但...）
  3. 事务 A 回滚 → 事务 B 已经基于一份不存在的文档进行了后续处理

在 PostgreSQL 的 Repeatable Read / Serializable 下：
  完全隔离 → 要么全部成功，要么全部回滚
```

在 n8n 工作流中，多个步骤是链式调用的。工作流 A 写入数据、工作流 B 读取数据是常见的模式。PostgreSQL 的强一致性保障在这种场景下是刚需——不是"最好有"，而是"必须有"。

**理由 2：JSONB——n8n 数据模型的自然匹配**

n8n 的工作流配置、执行结果、节点参数都是 JSON 格式。PostgreSQL 的 JSONB 数据类型可以高效存储和查询这些数据：

```sql
-- n8n 工作流表中的 JSONB 数据示例
CREATE TABLE workflows (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255),
    nodes JSONB NOT NULL,      -- 工作流中的节点配置
    connections JSONB,         -- 节点间的连接关系
    settings JSONB,            -- 工作流设置（时区、错误处理等）
    tags TEXT[],
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- JSONB 高效查询：查找所有使用 OpenAI 节点的工作流
CREATE INDEX idx_workflow_nodes ON workflows USING GIN (nodes);

SELECT id, name
FROM workflows
WHERE nodes @> '[{"type": "n8n-nodes-base.openAi"}]';

-- 更新工作流中某个节点的参数（不需要读-改-写全部）
UPDATE workflows
SET nodes = jsonb_set(
    nodes,
    '{0, parameters, model}',
    '"gpt-4o"',
    false
)
WHERE id = 42;
```

**理由 3：pgvector——为 AI 原生铺路**

虽然当前架构中尚未使用向量数据库，但 pgvector 扩展让 PostgreSQL 天然支持向量相似搜索——这意味着你不需要额外部署 Milvus / Qdrant / Pinecone：

```sql
-- 安装 pgvector
CREATE EXTENSION vector;

-- 创建向量表（用于语义缓存/RAG）
CREATE TABLE embedding_cache (
    id SERIAL PRIMARY KEY,
    query_text TEXT NOT NULL,
    query_embedding VECTOR(1536),  -- OpenAI embedding 维度
    response_text TEXT NOT NULL,
    model VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    access_count INTEGER DEFAULT 0
);

-- 建索引（IVFFlat，平衡精度与速度）
CREATE INDEX idx_embedding_cache ON embedding_cache
USING ivfflat (query_embedding vector_cosine_ops)
WITH (lists = 100);

-- 语义搜索：查找最相似的 10 条缓存
SELECT query_text, response_text, access_count
FROM embedding_cache
ORDER BY query_embedding <=> $1  -- 余弦距离
LIMIT 10;
```

这意味着一台 PostgreSQL 可以同时承载：业务数据（OLTP）+ 分析报表（OLAP）+ 向量搜索（AI）。**减少组件数量本身就是架构优化的核心**——每一减少一个组件，故障率曲线就下降一阶。

**理由 4：为什么不是 MongoDB？**

MongoDB 在 JSON 存储方面有天然优势，但在我们的场景中有三个致命问题：

1. **事务局限**：MongoDB 4.0+ 支持多文档事务，但性能和稳定性远不如 PG。在 n8n 修改工作流配置（涉及多个文档的更新）时，PG 的 ACID 保障明显更可靠。
2. **连接管理**：MongoDB 的 connection pool 管理在容器化环境中容易出现问题（TIME_WAIT 堆积）。PG 的连接池（PgBouncer）更成熟。
3. **运维复杂度**：MongoDB 的分片集群部署是运维噩梦。PG 的单节点承载能力远超 Mongo 的单节点。

### 1.3 PostgreSQL 版本选择

```yaml
version_recommendation:
  production:
    version: PostgreSQL 16.x
    reason: |
      - 逻辑复制性能提升（pgoutput 插件原生支持）
      - pgvector 0.6+ 的最新特性支持
      - vacuum 优化（不再频繁触发 autovacuum 等待）
      - 并行查询能力进一步增强

  development:
    version: PostgreSQL 16.x  # 和生产环境保持一致
    warning: |
      不要在生产环境使用 PostgreSQL 17 的 beta 版本。
      不要使用安装包自带的默认配置——针对容器化环境优化过配置。

  compatibility_notes:
    n8n: 支持 PostgreSQL 12+
    auth-server: 使用 SQLite（轻量级），不依赖 PG 版本
    pgvector: 需要 PostgreSQL 13+
```

---

## 2. 高可用方案：Patroni + etcd

### 2.1 架构原理

```
                     ┌──────────────────┐
                     │   etcd Cluster   │
                     │  (3 nodes, Raft) │
                     └────────┬─────────┘
                              │  leader election via DCS
            ┌─────────────────┼─────────────────┐
            ▼                 ▼                  ▼
    ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
    │  Patroni     │  │  Patroni     │  │  Patroni     │
    │  Primary     │  │  Replica 1   │  │  Replica 2   │
    │  PostgreSQL  │◄─┤  PostgreSQL  │◄─┤  PostgreSQL  │
    │  (Read-Write)│  │  (Read-Only) │  │  (Read-Only) │
    └──────┬───────┘  └──────────────┘  └──────────────┘
           │  streaming replication (async/sync)
           │
           ▼
    ┌──────────────┐
    │  PgBouncer   │  ← 连接池，自动路由读写
    │  (Connection│
    │   Pool)      │
    └──────────────┘
```

### 2.2 Patroni 选型理由

Patroni 是目前 PostgreSQL 高可用的事实标准。为什么是它而不是 repmgr / pg_auto_failover：

```yaml
comparison:
  patroni:
    pros:
      - etcd/Consul/ZooKeeper 多后端支持
      -自动故障切换（检测 → 选举 → 切换，通常 < 30s）
      - REST API + CLI 管理界面
      - 支持同步/异步复制混合模式
      - 广泛的社区支持和文档
    cons:
      - 部署复杂度高（etcd 本身也需要高可用）
      - 学习曲线陡峭
      - 资源消耗（etcd 3 节点最少 1C1G）

  repmgr:
    pros:
      - 部署简单（不需要外部一致性存储）
      - 轻量级
    cons:
      - 故障检测依赖监控（没有 lease 机制）
      - 脑裂恢复需要手动介入
      - 功能集较小

  pg_auto_failover:
    pros:
      - Citus 出品，与 PostgreSQL 配合好
      - 自动化程度高
    cons:
      - 架构固定（只能做主从）
      - 不够灵活
      - 社区较小

  recommendation:
    small_scale: repmgr（2 节点，不需要 etcd）
    medium_scale: Patroni + etcd（3 节点，推荐）
    large_scale: Patroni + etcd + pgbouncer + haproxy
```

### 2.3 脑裂处理（Split Brain）

在 2C4G 的资源约束下，我们无法部署完整的 3 节点 etcd 集群。因此脑裂风险是真实存在的：

**脑裂场景分析**：

```
场景：网络分区
Node A（Primary）与 Node B（Replica）之间网络中断
Node A 以为 Node B 挂了，继续当 Primary
Node B 通过 etcd 发现 Primary 失联，自动提升为 Primary
→ 两个 Primary 同时写入数据 → 脑裂
```

**实测脑裂的影响**：

在我们的测试环境中，模拟网络分区后：

1. **同步复制模式**：脑裂在 ~30 秒内被 Patroni 检测到，replica 提升为新的 primary。但旧 primary 在 ~60 秒后会通过 etcd lease 超时感知到问题，自动降级为 replica。窗口期约 30 秒——在此期间两个 primary 都可能接受写入。
2. **异步复制模式**：在脑裂恢复后，旧 primary 上未被同步的数据会丢失。需要手动比对差异数据。

**脑裂防护策略**：

```yaml
split_brain_prevention:
  # 策略 1：设置合理的 TTL
  patroni:
    ttl: 30  # etcd lease TTL（秒），决定了故障检测的灵敏度
    loop_wait: 10  # 循环等待间隔
    retry_timeout: 10

  # 策略 2：同步复制 + 多数派确认（需要 3 节点）
  postgresql:
    synchronous_commit: 'on'
    synchronous_standby_names: 'ANY 1 (replica1, replica2)'
    # 至少一个 standby 确认，确保数据不丢

  # 策略 3：业务层去重
  # 即使发生脑裂，上层应用（n8n工作流）应为幂等设计
  # 这样即使重复执行也不会产生脏数据
```

### 2.4 切换流程（SOP）

```bash
# 健康切换（计划内维护）
# 将 Primary 从 Node A 切换到 Node B

# Step 1: 检查集群状态
patronictl -c /etc/patroni.yml list

# Step 2: 切换
patronictl -c /etc/patroni.yml switchover --master node_a --candidate node_b

# Step 3: 确认切换成功
patronictl -c /etc/patroni.yml list
# 预期：Primary 变为 node_b，node_a 变为 replica

# Step 4: 更新 n8n/auth-server 连接配置
# 使用 PgBouncer 自动处理——无需手动修改

# 故障切换（自动）
# Patroni 自动执行，不需要人工介入
# 恢复后执行以下检查：
# 1. 检查数据一致性对比
# 2. 确认并修复脑裂导致的数据冲突
# 3. 发送切换事件报告
```

---

## 3. 表结构设计

### 3.1 设计哲学

```
数据库分层设计（Conceptual Level）

┌──────────────────────────────────────────────────────────┐
│                  Layer 0: 基础设施                       │
│  PostgreSQL 16 + pgvector + pgbouncer + Patroni         │
├──────────────────────────────────────────────────────────┤
│                  Layer 1: 核心业务                       │
│  n8n 工作流数据库（PG）                                  │
│    - workflows（工作流定义）                              │
│    - executions（执行记录）                              │
│    - credentials（凭证存储 - 加密）                      │
│    - tags（标签管理）                                   │
├──────────────────────────────────────────────────────────┤
│                  Layer 2: 辅助业务                       │
│  auth-server 数据库（SQLite）                            │
│    - licenses（License 记录）                            │
│    - api_keys（API Key 管理）                            │
│    - customers（客户信息）                              │
├──────────────────────────────────────────────────────────┤
│                  Layer 3: 可扩展                         │
│  ai-gateway 审计日志（PG / ClickHouse）                  │
│    - audit_log（API 调用审计）                          │
│    - rate_limits（限流记录）                            │
│    - billing（费用统计）                               │
├──────────────────────────────────────────────────────────┤
│                  Layer 4: 向量/AI 数据                   │
│  embedding_cache（语义缓存，pgvector）                   │
│  customer_knowledge_base（客户知识库，pgvector）         │
└──────────────────────────────────────────────────────────┘
```

### 3.2 核心数据表概念设计

**n8n 数据（存储在 PostgreSQL）**：

n8n 自动管理自己的表结构，但了解核心表有助于故障排查和定制开发：

```sql
-- 工作流定义表（n8n 自动创建）
-- 关键字段解析
SELECT
    w.id,
    w.name,
    w.active,           -- 是否启用
    w.nodes,            -- JSONB：节点数组，每个节点有 id/name/type/parameters/position
    w.connections,      -- JSONB：节点间的连线关系
    w.settings,         -- JSONB：执行超时、错误处理策略等
    w.static_data,      -- JSONB：工作流版本的静态快照
    w.created_at,
    w.updated_at
FROM workflow_entity w
LIMIT 10;

-- 执行记录表（n8n 自动创建）
-- 这是排查工作流故障的核心表
SELECT
    e.id,
    e.workflow_id,
    e.status,           -- 'success' | 'error' | 'running' | 'waiting'
    e.finished,
    e.started_at,
    e.stopped_at,
    e.execution_data,   -- JSONB：完整执行数据（含节点输入输出）
    e.retry_of,         -- 如果是重试，指向原执行记录 ID
    e.retry_success_id  -- 重试成功的执行 ID
FROM execution_entity e
WHERE e.workflow_id = 42
  AND e.created_at > NOW() - INTERVAL '24 hours'
ORDER BY e.created_at DESC;
```

**auth-server 数据（存储在 SQLite，轻量级）**：

```sql
-- License 表
CREATE TABLE licenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    license_key TEXT UNIQUE NOT NULL,       -- License Key（格式：AAAA-BBBB-CCCC-DDDD）
    machine_fingerprint TEXT,               -- 机器指纹（SHA256 of CPU+MAC+Disk）
    customer_id TEXT NOT NULL,              -- 分销商/客户 ID
    feature_flags TEXT DEFAULT '{}',        -- JSON：功能开关
    max_workflows INTEGER DEFAULT 50,       -- 最大工作流数
    expires_at TEXT NOT NULL,               -- 过期时间（ISO8601）
    last_verified_at TEXT,                  -- 最后验证时间
    offline_until TEXT,                     -- 离线缓存截止时间（7天）
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

-- 创建索引
CREATE UNIQUE INDEX idx_licenses_key ON licenses(license_key);
CREATE INDEX idx_licenses_customer ON licenses(customer_id);

-- API Key 表
CREATE TABLE api_keys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key_hash TEXT UNIQUE NOT NULL,          -- API Key 的 SHA256 哈希
    key_prefix TEXT NOT NULL,               -- Key 的前 8 位（用于识别）
    license_id INTEGER REFERENCES licenses(id),
    name TEXT NOT NULL,                     -- Key 的用途描述，如 "customer-X-production"
    allowed_models TEXT DEFAULT '[]',       -- JSON 数组：允许的模型列表
    monthly_quota INTEGER DEFAULT 1000000,  -- 每月 Token 配额
    monthly_usage INTEGER DEFAULT 0,        -- 已用 Token 数
    rate_limit INTEGER DEFAULT 60,          -- 每分钟请求数限制
    is_active INTEGER DEFAULT 1,
    expires_at TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE UNIQUE INDEX idx_api_keys_hash ON api_keys(key_hash);
CREATE INDEX idx_api_keys_license ON api_keys(license_id);
```

### 3.3 为什么 auth-server 用 SQLite 而非 PG？

这是一个有意识的设计决策，源于工程简洁性：

| 维度 | SQLite | PostgreSQL | 我们的选择理由 |
|------|--------|-----------|--------------|
| 部署复杂度 | 零配置（文件级） | 需要服务 + 配置 | SQLite ✅ |
| 数据量承载 | 单库 < 100GB | 可 PB 级 | auth-server 数据 < 1GB ✅ |
| 高可用 | 不支持（只支持文件备份） | Patroni 集群 | 不需要（License 数据非实时） |
| 并发写入 | 写锁（单 writer） | MVCC 多版本 | API Key 验证是读密集型 ✅ |
| 维护成本 | 几乎为零 | 需要 DBA | ✅ |
| 备份复杂度 | 复制文件即可 | pg_dump / WAL 归档 | ✅ |

**核心选择逻辑**：auth-server 的数据特点是"低频写入、高频读取（每次 API 调用都会验证）、数据量小（< 1GB）、无需高可用"。SQLite 在这些条件下是完美匹配。

**⚠️ 但有一个核心约束**：每天必须自动备份 SQLite 文件到持久化存储。如果数据丢失，所有的 License 和 API Key 都要重新生成。

---

## 4. 数据归档策略

### 4.1 冷热分离架构

```yaml
data_tiers:
  hot_data:
    storage: PostgreSQL 主库
    characteristics:
      - 高性能存储（NVMe SSD）
      - 完整索引
      - 7×24 在线查询
    retention: 30 天
    data:
      - 当前正在运行的工作流
      - 最近 7 天的执行记录
      - 最新的 License/API Key 数据

  warm_data:
    storage: PostgreSQL 主库（分区表）
    characteristics:
      - 标准性能存储
      - 部分索引
      - 可查询但较慢
    retention: 90 天
    data:
      - 已完成工作流的执行日志
      - 审计日志（汇总级别）

  cold_data:
    storage: S3 / MinIO / 对象存储
    characteristics:
      - 低成本存储
      - 无实时查询能力
      - Parquet + Zstd 压缩
    retention: 永久（按客户策略）
    data:
      - 超过 90 天的审计日志
      - 已删除工作流的备份
      - License 历史记录
```

### 4.2 PostgreSQL 分区表实现

```sql
-- 按时间分区：执行记录表
-- 使用 PG 原生的声明式分区

CREATE TABLE execution_entity (
    id SERIAL,
    workflow_id INTEGER NOT NULL,
    status VARCHAR(20),
    started_at TIMESTAMPTZ NOT NULL,
    stopped_at TIMESTAMPTZ,
    execution_data JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
) PARTITION BY RANGE (created_at);

-- 创建分区
CREATE TABLE execution_2024_q4 PARTITION OF execution_entity
    FOR VALUES FROM ('2024-10-01') TO ('2025-01-01');
CREATE TABLE execution_2025_q1 PARTITION OF execution_entity
    FOR VALUES FROM ('2025-01-01') TO ('2025-04-01');
CREATE TABLE execution_2025_q2 PARTITION OF execution_entity
    FOR VALUES FROM ('2025-04-01') TO ('2025-07-01');
CREATE TABLE execution_2025_q3 PARTITION OF execution_entity
    FOR VALUES FROM ('2025-07-01') TO ('2025-10-01');

-- 自动创建未来分区（使用 pg_partman 扩展）
CREATE EXTENSION pg_partman;
SELECT partman.create_parent(
    p_parent_table := 'public.execution_entity',
    p_control := 'created_at',
    p_type := 'native',
    p_interval := '3 months',
    p_premake := 4
);
```

### 4.3 数据清理自动化

```bash
#!/bin/bash
# 自动清理脚本：cron 每 3 小时执行一次

# 配置
PGHOST="postgres"
PGUSER="n8n_user"
PGPASSWORD="strong_password"
PGDATABASE="n8n"
RETENTION_HOT=30     # 保留 30 天热数据
RETENTION_WARM=90    # 保留 90 天温数据
ARCHIVE_BUCKET="s3://your-bucket/archive"

# 1. 删除超过 30 天的执行记录（n8n 内部清理不够激-）
psql -h $PGHOST -U $PGUSER -d $PGDATABASE <<EOF
-- 删除超过 30 天且已完成的记录
DELETE FROM execution_entity
WHERE created_at < NOW() - INTERVAL '$RETENTION_HOT days'
  AND status IN ('success', 'error', 'crashed');

-- 对于超过 90 天的，记录简要信息后全量删除
DELETE FROM execution_entity
WHERE created_at < NOW() - INTERVAL '$RETENTION_WARM days';
EOF

# 2. n8n 执行日志裁剪
curl -X POST http://n8n:5678/rest/executions/prune \
  -H "X-N8N-API-KEY: $N8N_API_KEY"

# 3. 导出并归档 90 天前的审计日志
./archive-audit-logs.sh --before $(date -d "-90 days" +%Y-%m-%d) \
  --target "$ARCHIVE_BUCKET/audit-$(date +%Y%m%d).parquet"

# 4. 清理归档后确认
if [ $? -eq 0 ]; then
    echo "Archival successful: $(date)"
else
    curl -X POST http://monitor:9090/api/v1/alerts \
      -H "Content-Type: application/json" \
      -d '{"status":"warning","alert":"Data archival failed"}'
fi
```

### 4.4 保留策略矩阵

```yaml
retention_policy:
  # 默认策略（适用于大多数客户）
  default:
    n8n_executions:
      hot: 30 天（完整执行数据，含节点输入输出）
      warm: 90 天（仅统计信息，无节点细节）
      cold: 不保留
    audit_logs:
      hot: 7 天（ES 中可实时查询）
      warm: 90 天（ClickHouse 汇总）
      cold: 365 天（Parquet 归档）
    auth_data:
      licenses: 永久保留
      api_keys: 永久保留（含已吊销的）

  # 高合规策略（金融/医疗等行业）
  high_compliance:
    n8n_executions:
      hot: 90 天
      warm: 365 天
      cold: 7 年
    audit_logs:
      hot: 30 天
      warm: 365 天
      cold: 永久
    auth_data:
      licenses: 永久保留
      api_keys: 永久保留

  # 最小保留策略（个人/小团队）
  minimal:
    n8n_executions:
      hot: 7 天
      warm: 不保留
      cold: 不保留
    audit_logs:
      hot: 3 天
      warm: 不保留
      cold: 不保留
    auth_data:
      licenses: 永久保留
```

---

> **下篇**：[02-Engineering-Philosophy/01-minimal-logic-principle.md](../02-Engineering-Philosophy/01-minimal-logic-principle.md) — 最小逻辑原则
