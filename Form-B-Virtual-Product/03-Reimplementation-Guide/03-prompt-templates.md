# AI 提示词模板

> **使用说明**：以下提示词是为 o1-preview 或 Claude Opus 设计的"一次性交付"提示词。核心原则是：**输入的质量决定输出的质量**。越详细、越具体、越有约束的 Prompt，AI 输出的代码就越好用。
> 
> 每个模板都是完整的、可直接使用的。你只需要复制粘贴到对应的 AI 对话窗口，修改尖括号（`<...>`）内的占位符即可。
> 
> **建议的策略**：
> 1. 将完整的提示词一次性输入到 AI 对话
> 2. 等待 AI 输出完整代码
> 3. 不要修改代码，先在测试环境跑通
> 4. 迭代时，逐模块追问优化建议

---

## 目录

- [1. RSA License 授权服务（Go）](#1-rsa-license-授权服务go)
- [2. AI API 安全代理网关（Python FastAPI）](#2-ai-api-安全代理网关python-fastapi)
- [3. PostgreSQL 高可用方案设计](#3-postgresql-高可用方案设计)
- [4. n8n 替代引擎核心框架（Go）](#4-n8n-替代引擎核心框架go)
- [5. 工作流引擎 Webhook 模块](#5-工作流引擎-webhook-模块)
- [6. 数据库分区 + 归档方案](#6-数据库分区--归档方案)
- [7. 前端管理面板 API 设计](#7-前端管理面板-api-设计)

---

## 1. RSA License 授权服务（Go）

```
# Role: 高级 Go 后端开发工程师
# Task: 实现一个完整的 RSA 签名验证的 License 授权服务

## 业务背景
这是 AI 自动化集群系统的授权组件。系统通过 License Key 控制功能使用权限，
支持机器指纹绑定和离线缓存。客户购买的 License 通过这个服务进行验证。

## 功能需求

### 1.1 RSA-2048 密钥对
- 管理端支持生成 RSA-2048 密钥对（私钥加密存储，公钥分发给服务端）
- 服务端使用公钥验证 License 签名
- 使用标准 PEM 格式存储密钥

### 1.2 License 数据结构
```go
type License struct {
    LicenseKey    string   `json:"license_key"`     // 格式: AAAA-BBBB-CCCC-DDDD
    CustomerID    string   `json:"customer_id"`      // 客户标识
    DistributorID string   `json:"distributor_id"`   // 分销商 ID
    ExpiresAt     int64    `json:"expires_at"`       // Unix 时间戳
    MaxWorkflows  int      `json:"max_workflows"`    // 最大工作流数 (默认50)
    FeatureFlags  []string `json:"feature_flags"`    // 功能开关列表
    Fingerprint   string   `json:"fingerprint"`      // 机器指纹 (SHA256)
    CreatedAt     int64    `json:"created_at"`
    Signature     []byte   `json:"signature"`        // RSA-2048 签名
}
```

### 1.3 API 端点
```
POST /api/v1/license/activate
    请求体: {"license_key": "AAAA-BBBB-CCCC-DDDD", "machine_id": "<fingerprint>"}
    响应:   {"status": "ok", "expires_at": 1735689600, "features": ["basic", "advanced"]}

GET /api/v1/license/status
    响应:   {"active": true, "expires_at": 1735689600, "days_remaining": 30}

POST /api/v1/license/renew
    请求体: {"license_key": "EEEE-FFFF-GGGG-HHHH", "machine_id": "<fingerprint>"}
    响应:   {"status": "ok", "previous_expired_at": 1735689600, "new_expires_at": 1767225600}

POST /api/v1/license/validate  (内部微服务间使用)
    请求体: {"license_key": "AAAA-BBBB-CCCC-DDDD", "feature": "workflow_ai"}
    响应:   {"valid": true, "reason": ""} 或 {"valid": false, "reason": "license_expired"}
```

### 1.4 机器指纹采集
- Linux 环境: 从 /proc/cpuinfo 读取 Serial，从 /sys/class/net/<eth>/address 读取 MAC
- macOS 环境: 使用 sysctl 获取硬件 UUID，使用 networksetup 获取 MAC
- 组合方式: SHA256( <CPU_Serial> + ":" + <MAC> )
- 指纹应该缓存到内存中，避免每次 API 调用都重新计算

### 1.5 7 天离线缓存机制
- 成功验证后，将 License 信息加密写入 /var/lib/license/cache
- 缓存使用 AES-256-GCM 加密，密钥由机器指纹派生
- 每次请求优先检查缓存，缓存有效期内不请求验证服务器
- 缓存过期前 1 天自动后台刷新（如果在线）
- 缓存文件格式：
  ```json
  {
    "license_key_hash": "...",
    "status": "active",
    "verified_at": "ISO8601",
    "expires_at": "ISO8601",
    "encrypted_payload": "<AES-256-GCM encrypted blob>"
  }
  ```

### 1.6 安全要求
- 失败验证 5 次后 1 小时退避（写入 /tmp/license_backoff_<key_hash>）
- 所有 API 端点需要 X-API-Key Header 验证（内部服务间认证）
- License Key 在内存处理完后使用 memguard 清空
- 日志中记录的是 Key 的 SHA256 哈希，不是明文 Key

### 1.7 技术约束
- Go 1.22+
- 依赖: gin-gonic/gin, google/uuid, awnumar/memguard
- 配置来源: 环境变量优先，config.yaml 后备
- 编译为目标单一二进制

## 输出要求
请输出完整的 Go 项目，包括：
1. main.go — 启动入口 + 路由注册
2. config/config.go — 配置结构体 + 加载逻辑
3. internal/license/license.go — License 生成（管理端工具）和验证（服务端）
4. internal/auth/middleware.go — API Key 认证中间件
5. internal/fingerprint/fingerprint.go — 机器指纹采集（Linux + macOS）
6. internal/cache/cache.go — 7 天离线缓存
7. internal/handler/activate.go — API 处理器
8. go.mod
9. Dockerfile（多阶段构建，最终镜像 < 20MB）

每个 .go 文件附带完整的单元测试（使用标准 testing 包）。
请在一个回复中输出所有文件。
```

---

## 2. AI API 安全代理网关（Python FastAPI）

```
# Role: 高级 Python 后端开发工程师
# Task: 实现一个 AI API 安全代理网关

## 业务背景
这是 AI 自动化集群的 API 网关层。所有对 OpenAI/DeepSeek/Anthropic 的 API 调用
都经过这个网关，实现统一鉴权、限流、审计。

## 核心功能

### 2.1 统一入口
```python
# 单一入口端点，所有 AI 请求都发到这里
POST /api/v1/chat/completions
请求体 (OpenAI 兼容格式):
{
    "model": "deepseek-chat",
    "messages": [{"role": "user", "content": "你好"}],
    "stream": false
}
响应: OpenAI 兼容格式

POST /api/v1/health
响应: {"status": "ok", "uptime": 3600}
```

### 2.2 鉴权层 (Authentication Layer)

API Key 设计方案：
- Master Key（管理员用）：可以创建/吊销子 Key，查看所有审计日志
- Sub Key（工作流用/客户用）：只能调用 AI API，可限制允许的模型和配额

鉴权逻辑：
```python
class AuthLayer:
    async def verify(self, api_key: str) -> AuthResult:
        # 1. 从缓存中查找 Key
        key_info = await cache.get(f"api_key:{sha256(api_key)}")
        if not key_info:
            # 2. 从数据库查找
            key_info = await db.get_api_key(sha256(api_key))
            if not key_info:
                raise AuthError("invalid_api_key", 401)
            await cache.set(f"api_key:{sha256(api_key)}", key_info, ttl=300)

        # 3. 检查是否过期
        if key_info.expires_at < time.now():
            raise AuthError("key_expired", 401)

        # 4. 检查模型权限
        if request.model not in key_info.allowed_models:
            raise AuthError("model_not_allowed", 403)

        # 5. 检查 IP 白名单
        if key_info.allowed_ips and request.ip not in key_info.allowed_ips:
            raise AuthError("ip_not_allowed", 403)

        return AuthResult(key_info)
```

### 2.3 限流层 (Rate Limiter)

使用 Redis + 令牌桶算法实现分布式限流：

```python
# 限流配置（YAML）
rate_limits:
  global:
    requests_per_minute: 1000
    tokens_per_day: 10000000

  per_api_key:
    requests_per_minute: 60
    tokens_per_hour: 500000
    concurrent_limit: 5

  per_ip:
    requests_per_minute: 30
    burst: 10

  per_model:
    gpt-4: { rpm: 20, tpm: 100000 }
    deepseek-chat: { rpm: 60, tpm: 300000 }
    gpt-4o-mini: { rpm: 200, tpm: 1000000 }
```

令牌桶的 Redis Lua 脚本：
```lua
-- rate_limit.lua
-- KEYS[1] = rate_limit key
-- ARGV[1] = max_tokens
-- ARGV[2] = refill_rate (tokens per second)
-- ARGV[3] = current_time
-- ARGV[4] = request_cost (通常为 1)

local bucket = redis.call('HMGET', KEYS[1], 'tokens', 'last_refill')
local tokens = tonumber(bucket[1]) or tonumber(ARGV[1])
local last_refill = tonumber(bucket[2]) or tonumber(ARGV[3])

-- 计算应补充的令牌数
local elapsed = tonumber(ARGV[3]) - last_refill
local refill = elapsed * tonumber(ARGV[2])
tokens = math.min(tokens + refill, tonumber(ARGV[1]))
local cost = tonumber(ARGV[4])

if tokens >= cost then
    tokens = tokens - cost
    redis.call('HMSET', KEYS[1], 'tokens', tokens, 'last_refill', ARGV[3])
    return 1  -- 允许
else
    return 0  -- 拒绝
end
```

### 2.4 审计层 (Audit Logger)

```python
# 审计日志条目结构
{
    "request_id": "uuid-v4",
    "timestamp": "ISO8601",
    "api_key_hash": "sha256 of api key (NOT plaintext)",
    "client_ip": "x.x.x.x",
    "model": "deepseek-chat",
    "prompt_tokens": 150,
    "completion_tokens": 200,
    "total_tokens": 350,
    "latency_ms": 2450,
    "http_status": 200,
    "error_code": null,
    "provider": "deepseek",       # 实际处理请求的 Provider
    "provider_latency_ms": 2350,   # Provider 响应时间
    "cost_usd": 0.007,            # 本次调用的估算费用
    "cached": false,
    "streaming": false,
}

# 审计日志写入策略
# - 使用异步批量写入（批量大小 100 或间隔 5 秒）
# - 写入到 PostgreSQL（热数据保留 7 天）
# - 写入到本地 JSON 文件（备份，保留 30 天）
# - 使用队列 + worker 模式，不阻塞请求处理
```

### 2.5 Provider 路由与故障切换

```python
# Provider 配置
providers:
  - name: deepseek_primary
    base_url: https://api.deepseek.com
    api_key: ${DEEPSEEK_API_KEY}
    models: [deepseek-chat, deepseek-coder]
    weight: 100          # 流量权重
    timeout: 30
    max_retries: 2

  - name: openai_fallback
    base_url: https://api.openai.com
    api_key: ${OPENAI_API_KEY}
    models: [gpt-4o-mini]
    weight: 0             # 仅当 primary 不可用时使用
    timeout: 60
    max_retries: 1

# 故障切换逻辑（被动检测）
# 1. 请求 primary Provider
# 2. 如果 primary 在 timeout 内无响应 → 标记为"降级"
# 3. 请求 fallback Provider
# 4. 响应客户端
# 5. 后台定期检查 primary 是否恢复（每 30 秒一次）
```

### 2.6 技术约束
- Python 3.12+
- FastAPI + uvicorn
- Redis (redis-py, async)
- PostgreSQL (asyncpg)
- httpx (异步 HTTP)
- prometheus_client

## 输出要求
请输出完整的 Python 项目，包含：
1. main.py — FastAPI 应用入口
2. app/config.py — 配置管理（YAML + 环境变量）
3. app/auth/__init__.py — 鉴权模块
4. app/rate_limiter/__init__.py — 限流器（Redis Lua 脚本）
5. app/audit/logger.py — 审计日志记录
6. app/audit/sanitizer.py — 日志脱敏器
7. app/router.py — Provider 路由与故障切换
8. app/providers/base.py — Provider 抽象基类
9. app/providers/openai.py — OpenAI 适配器
10. app/providers/deepseek.py — DeepSeek 适配器
11. app/middleware/__init__.py — 中间件（鉴权、限流、审计）
12. app/models.py — 数据模型
13. requirements.txt
14. Dockerfile
15. docker-compose.yml (用于本地测试)
```

---

## 3. PostgreSQL 高可用方案设计

```
# Role: 高级数据库架构师 / DBA
# Task: 设计一个基于 Patroni + etcd 的 PostgreSQL 高可用方案

## 环境约束
- 资源: 3 台服务器，每台 4C/8GB（或云服务商等价配置）
- 存储: 每台 200GB SSD，建议使用云盘（支持快照）
- OS: Ubuntu 22.04 LTS
- PostgreSQL 16
- etcd 3.5+

## 架构要求

### 3.1 节点分配
```
Node A: Patroni Primary + etcd member
Node B: Patroni Replica + etcd member
Node C: Patroni Replica + etcd member
```

### 3.2 同步模式
- 默认: 异步复制（性能优先）
- 关键业务: 同步复制（半同步，至少 1 个 standby 确认）
- 切换触发: 自动（Patroni 检测 Primary 失联后触发选举）

### 3.3 Patroni 配置

```yaml
# /etc/patroni/patroni.yml
scope: ai-cluster
namespace: /db/
name: pg-node-<A|B|C>

restapi:
  listen: 0.0.0.0:8008
  connect_address: <node_ip>:8008
  authentication:
    username: patroni_api
    password: <strong_password>

etcd:
  host: <node_ip>:2379
  protocol: http

bootstrap:
  dcs:
    ttl: 30
    loop_wait: 10
    retry_timeout: 10
    maximum_lag_on_failover: 1048576  # 1MB
    postgresql:
      use_pg_rewind: true
      use_slots: true
      parameters:
        max_connections: 200
        shared_buffers: 2GB
        effective_cache_size: 4GB
        work_mem: 16MB
        maintenance_work_mem: 256MB
        wal_level: replica
        wal_buffers: 64MB
        max_wal_senders: 5
        max_replication_slots: 5
        checkpoint_completion_target: 0.9
        archive_mode: on
        archive_command: '/usr/bin/pgbackrest --stanza=ai-cluster archive-push %p'
        hot_standby: on
        random_page_cost: 1.1
        effective_io_concurrency: 200
        synchronous_commit: on
        synchronous_standby_names: 'ANY 1 (*)'

postgresql:
  listen: 0.0.0.0:5432
  connect_address: <node_ip>:5432
  data_dir: /var/lib/postgresql/16/main
  bin_dir: /usr/lib/postgresql/16/bin
  pgpass: /tmp/pgpass
  authentication:
    replication:
      username: replicator
      password: <replication_password>
    superuser:
      username: postgres
      password: <postgres_password>
    rewind:
      username: rewind_user
      password: <rewind_password>
  parameters:
    unix_socket_directories: /var/run/postgresql
  pg_hba:
    - host replication replicator <node_ip>/32 md5
    - host all all <ip_range>/24 md5
```

### 3.4 etcd 集群配置

```yaml
# /etc/etcd/etcd.conf.yml
name: 'etcd-node-<A|B|C>'
data-dir: /var/lib/etcd
listen-peer-urls: http://<node_ip>:2380
listen-client-urls: http://<node_ip>:2379,http://127.0.0.1:2379
advertise-client-urls: http://<node_ip>:2379
initial-advertise-peer-urls: http://<node_ip>:2380
initial-cluster: etcd-node-A=http://<node_a_ip>:2380,etcd-node-B=http://<node_b_ip>:2380,etcd-node-C=http://<node_c_ip>:2380
initial-cluster-token: 'ai-cluster-etcd'
initial-cluster-state: new
```

### 3.5 切换 SOP

```bash
# 健康切换（计划内维护）
patronictl -c /etc/patroni.yml list
patronictl -c /etc/patroni.yml switchover --master node_a --candidate node_b
# 确认:
patronictl -c /etc/patroni.yml list

# 故障切换（自动或手动）
patronictl -c /etc/patroni.yml failover --master node_a --candidate node_b

# 检查集群一致性
patronictl -c /etc/patroni.yml check

# 恢复有故障的节点（节点修复后加入集群）
systemctl start patroni
```

### 3.6 数据备份策略

```bash
# 使用 pgBackrest
# 全量备份: 每日 03:00
pgbackrest --stanza=ai-cluster --type=full backup

# WAL 归档: 连续
pgbackrest --stanza=ai-cluster archive-push

# 恢复测试: 每周自动执行
pgbackrest --stanza=ai-cluster --db-path=/tmp/pg_restore_test restore
```

### 3.7 脑裂处理 SOP

```yaml
脑裂处理步骤:
  1. 停止发生冲突的节点的 Patroni 服务
     systemctl stop patroni

  2. 检查两个 primary 的数据差异
     - 时间戳比较
     - 事务 ID 比较
     - 关键表行数比较

  3. 保留数据较新的 primary
  4. 对另一个 primary 执行 pg_rewind 同步
  5. 启动 Patroni 服务，确认加入集群
     systemctl start patroni
     patronictl -c /etc/patroni.yml list

  6. 检查数据一致性
     patronictl -c /etc/patroni.yml check

防止脑裂的核心措施:
  - 设置合理的 TTL（建议 30 秒）
  - 使用同步复制模式
  - 多数派写入确认（至少 2/3 节点确认）
  - 上层应用幂等设计
```

### 3.8 性能基准测试

```sql
-- 验证高可用部署后的性能
-- 测试 1: 写入延迟
\timing
INSERT INTO perf_test (data) SELECT generate_series(1, 10000);
-- 预期: < 2ms per row (异步), < 10ms per row (同步)

-- 测试 2: 切换耗时
-- 在 Node A 上执行 kill -9 $(pgrep -f postgres)
-- 监控从 kill 到新 primary 接受请求的时间
-- 预期: < 30 秒

-- 测试 3: 故障恢复后数据一致性
SELECT count(*) FROM main_table;
-- 在切换前后的值应该完全一致
```

## 输出要求
请输出以下内容：
1. 完整的架构设计文档（含 Mermaid 图）
2. 3 台机器的部署步骤（逐条命令）
3. 日常巡检脚本（patroni_healthcheck.sh）
4. 灾备切换 SOP
5. 恢复演练步骤
```

---

## 4. n8n 替代引擎核心框架（Go）

```
# Role: 高级 Go 后端开发工程师
# Task: 实现一个最小化的工作流执行引擎（n8n 替代品）

## 设计哲学
不做可视化编辑器，不做 400+ 预制节点。
只做一件事：**接收 Webhook 触发，按 DAG 顺序执行节点，返回结果**。

## 核心概念

```go
// 工作流定义
type Workflow struct {
    ID          string           `json:"id" yaml:"id"`
    Name        string           `json:"name" yaml:"name"`
    Active      bool             `json:"active" yaml:"active"`
    Nodes       []Node           `json:"nodes" yaml:"nodes"`
    Connections []Connection     `json:"connections" yaml:"connections"`
    Settings    WorkflowSettings `json:"settings" yaml:"settings"`
    CreatedAt   time.Time        `json:"created_at" yaml:"created_at"`
    UpdatedAt   time.Time        `json:"updated_at" yaml:"updated_at"`
}

// 工作流的节点（最小化，只包含核心类型）
type Node struct {
    ID         string            `json:"id" yaml:"id"`
    Name       string            `json:"name" yaml:"name"`
    Type       NodeType          `json:"type" yaml:"type"`
    Parameters map[string]any    `json:"parameters" yaml:"parameters"`
    Position   struct{ X, Y int} `json:"position" yaml:"position"`
}

type NodeType string
const (
    NodeWebhook       NodeType = "webhook"         // HTTP 入口
    NodeHTTPRequest   NodeType = "http_request"     // HTTP 调用
    NodeCode          NodeType = "code"             // 代码执行 (JavaScript/Go)
    NodeSwitch        NodeType = "switch"           // 条件分支
    NodeMerge         NodeType = "merge"            // 合并多个路径
    NodeFunction      NodeType = "function"         // 数据转换
    NodePostgres      NodeType = "postgres"         // 数据库操作
    NodeRedis         NodeType = "redis"            // Redis 操作
    NodeAI            NodeType = "ai"               // AI API 调用
    NodeWait          NodeType = "wait"             // 延迟执行
)

// 节点间的连接关系
type Connection struct {
    SourceNodeID string `json:"source_node_id" yaml:"source_node_id"`
    SourceOutput string `json:"source_output" yaml:"source_output"` // "main" / "true" / "false"
    TargetNodeID string `json:"target_node_id" yaml:"target_node_id"`
    TargetInput  string `json:"target_input" yaml:"target_input"`   // "main" / "json" / "binary"
}

// 执行上下文
type ExecutionContext struct {
    WorkflowID   string
    ExecutionID  string
    InputData    map[string]any
    NodeResults  map[string]NodeResult
    StartTime    time.Time
    MaxDuration  time.Duration
    StopOnError  bool
    Logger       *slog.Logger
}

type NodeResult struct {
    NodeID     string
    Status     string  // "success" / "error" / "skipped"
    OutputData map[string]any
    Error      string
    Duration   time.Duration
}
```

## 核心接口

```go
// NodeExecutor 接口——所有节点类型实现
type NodeExecutor interface {
    Type() NodeType
    Execute(ctx *ExecutionContext, node *Node) (*NodeResult, error)
    Validate(node *Node) error
}

// 执行引擎
type Engine struct {
    executors map[NodeType]NodeExecutor
}

func (e *Engine) ExecuteWorkflow(workflow *Workflow, input map[string]any) (*ExecutionContext, error) {
    // 1. 构建执行 DAG（基于 connections 确定执行顺序）
    // 2. 拓扑排序
    // 3. 按序执行节点
    // 4. 收集结果
}
```

## DAG 执行引擎核心逻辑

```go
// 拓扑排序（基于 Kahn 算法）
func (e *Engine) topologicalSort(nodes []Node, connections []Connection) ([]Node, error) {
    // 1. 构建入度表和邻接表
    // 2. 从入度为 0 的节点开始
    // 3. 每执行一个节点，更新邻居的入度
    // 4. 如果还有剩余节点但无一入度为 0，说明有环
    inDegree := make(map[string]int)
    adjacency := make(map[string][]string)

    for _, node := range nodes {
        inDegree[node.ID] = 0
    }

    for _, conn := range connections {
        adjacency[conn.SourceNodeID] = append(adjacency[conn.SourceNodeID], conn.TargetNodeID)
        inDegree[conn.TargetNodeID]++
    }

    var sorted []Node
    queue := []Node{}
    for _, node := range nodes {
        if inDegree[node.ID] == 0 {
            queue = append(queue, node)
        }
    }

    for len(queue) > 0 {
        current := queue[0]
        queue = queue[1:]
        sorted = append(sorted, current)

        for _, neighborID := range adjacency[current.ID] {
            inDegree[neighborID]--
            if inDegree[neighborID] == 0 {
                for _, n := range nodes {
                    if n.ID == neighborID {
                        queue = append(queue, n)
                        break
                    }
                }
            }
        }
    }

    if len(sorted) != len(nodes) {
        return nil, fmt.Errorf("workflow contains a cycle")
    }
    return sorted, nil
}

// 如果节点支持条件分支（Switch 节点）
// 在拓扑排序基础上，执行时动态决定走哪个分支
func (e *Engine) executeConditionalBranch(ctx *ExecutionContext, node *Node, connections []Connection) error {
    // 1. 执行当前节点
    result, err := e.getExecutor(node.Type).Execute(ctx, node)
    if err != nil {
        return err
    }

    // 2. 根据节点的输出决定走哪个分支
    //    Switch 节点输出 true/false，对应不同的 connections
    var outputType string
    if result.OutputData["condition"] == true {
        outputType = "true"
    } else {
        outputType = "false"
    }

    // 3. 找到对应分支的连接和目标节点
    for _, conn := range connections {
        if conn.SourceNodeID == node.ID && conn.SourceOutput == outputType {
            // 递归执行目标节点
            var targetNode *Node
            // ... 查找 targetNode
            return e.executeConditionalBranch(ctx, targetNode, connections)
        }
    }

    return nil
}
```

## API 设计

```go
// REST API (Gin)
func RegisterRoutes(r *gin.Engine, engine *Engine) {
    v1 := r.Group("/api/v1")
    {
        // 工作流 CRUD
        v1.GET("/workflows", ListWorkflows)
        v1.POST("/workflows", CreateWorkflow)
        v1.GET("/workflows/:id", GetWorkflow)
        v1.PUT("/workflows/:id", UpdateWorkflow)
        v1.DELETE("/workflows/:id", DeleteWorkflow)

        // 工作流执行
        v1.POST("/workflows/:id/execute", ExecuteWorkflow)
        v1.GET("/executions/:id", GetExecutionResult)

        // Webhook 触发（外部系统通过这个端点触发工作流）
        v1.POST("/webhook/:workflow_id/:hook_name", HandleWebhook)
        v1.GET("/webhook/:workflow_id/:hook_name", HandleWebhookQuery)

        // 健康检查
        v1.GET("/health", HealthCheck)
    }
}
```

## 存储设计

```go
// PostgreSQL 存储
type WorkflowStore interface {
    List() ([]Workflow, error)
    Get(id string) (*Workflow, error)
    Create(workflow *Workflow) error
    Update(workflow *Workflow) error
    Delete(id string) error
}

// 执行记录存储
type ExecutionStore interface {
    Save(ctx *ExecutionContext) error
    Get(id string) (*ExecutionContext, error)
    List(workflowID string, limit, offset int) ([]*ExecutionContext, error)
}
```

## 输出要求
输出完整的 Go 项目源代码，包含：
1. engine.go — 执行引擎核心
2. engine/scheduler.go — 拓扑排序 + DAG 执行
3. engine/executors/ — 各节点类型实现
4. webhook/handler.go — Webhook 处理
5. api/router.go — API 路由
6. api/handlers/ — 各 API handler
7. store/postgres.go — PostgreSQL 存储实现
8. store/redis.go — Redis 队列（可选）
9. types/ — 所有数据结构定义
10. config/config.go — 配置管理
11. cmd/server/main.go — 启动入口
12. go.mod
13. Dockerfile
```

---

## 5. 工作流引擎 Webhook 模块

```
# Role: Go 后端开发工程师 
# Task: 实现工作流引擎的 Webhook 触发模块

Webhook 是引擎的入口。外部系统（如用户的应用、第三方服务）通过 HTTP 请求
触发一个工作流，传入数据，等待执行结果。

## 功能需求

### Webhook 注册
```go
// 工作流定义中包含 Webhook 节点
// Webhook 节点参数:
{
    "path": "/chat/incoming",        // Webhook 路径
    "method": "POST",                // HTTP 方法
    "auth_type": "none",             // auth_type: none / basic / header
    "auth_header_name": "X-Webhook-Token",  // auth_type=header 时使用
    "auth_token": "optional-token",   // 验证 token
    "response_mode": "last_node",    // 响应模式: last_node / manual / empty
    "options": {                     // CORS 配置
        "enabled": true,
        "origin": "*",
        "methods": ["GET", "POST"]
    }
}
```

### 执行流程
```
1. 外部请求 POST /webhook/chat/incoming
2. Webhook 处理器解析请求体（支持 JSON、Form、Raw）
3. 验证 Webhook Token（如果配置了）
4. 创建工作流 ExecutionContext（含 ExecutionID 和时间戳）
5. 启动工作流执行（异步或同步，由参数决定）
6. 等待结果并返回
```

### 响应格式
```go
// 成功响应
{
    "execution_id": "exec-uuid-123",
    "status": "success",
    "data": {
        // 最后一个节点的输出
    },
    "execution_time_ms": 1234
}

// 错误响应
{
    "execution_id": "exec-uuid-123",
    "status": "error",
    "error": {
        "message": "...",
        "node_id": "node-5",
        "node_name": "LLM 调用"
    },
    "execution_time_ms": 567
}
```

### 并发控制
- 同一工作流 ID 的串行执行（锁在 Redis 中，TTL 30s）
- 不同工作流 ID 之间的并行执行
- 全局并发上限（由引擎配置决定）

### 超时处理
- Webhook 请求超时: 30 秒
- 工作流执行超时: 由工作流的 settings.max_execution_time 决定
- 超时后返回 408 状态码

## 输出要求
输出完整的 webhook 处理模块代码：
1. webhook/registry.go — Webhook 注册和管理
2. webhook/handler.go — HTTP handler
3. webhook/validator.go — 请求验证
4. webhook/response.go — 响应构建
5. 单元测试
```

---

## 6. 数据库分区 + 归档方案

```
# Role: 高级 DBA / 数据库工程师
# Task: 为 AI 自动化集群设计 PostgreSQL 数据分区和归档方案

## 业务数据特点
- 执行记录表（execution_entity）：每天约 10,000 条新记录
- 审计日志表（audit_log）：每天约 100,000 条新记录
- 业务数据增长：~500MB/月
- 数据需要保留 30 天热数据可在线查询
- 30-90 天温数据可归档查询，延迟可接受
- 超过 90 天的数据需要压缩归档到对象存储

## 分区设计

### execution_entity 表分区
```sql
-- 主表（分区父表）
CREATE TABLE execution_entity (
    id BIGSERIAL,
    workflow_id INTEGER NOT NULL,
    execution_id VARCHAR(64) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    input_data JSONB,
    output_data JSONB,
    error_message TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    duration_ms INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (id, created_at)
) PARTITION BY RANGE (created_at);

-- 2025 年各月分区
CREATE TABLE execution_2025_01 PARTITION OF execution_entity
    FOR VALUES FROM ('2025-01-01') TO ('2025-02-01');
CREATE TABLE execution_2025_02 PARTITION OF execution_entity
    FOR VALUES FROM ('2025-02-01') TO ('2025-03-01');
CREATE TABLE execution_2025_03 PARTITION OF execution_entity
    FOR VALUES FROM ('2025-03-01') TO ('2025-04-01');
CREATE TABLE execution_2025_04 PARTITION OF execution_entity
    FOR VALUES FROM ('2025-04-01') TO ('2025-05-01');
CREATE TABLE execution_2025_05 PARTITION OF execution_entity
    FOR VALUES FROM ('2025-05-01') TO ('2025-06-01');
CREATE TABLE execution_2025_06 PARTITION OF execution_entity
    FOR VALUES FROM ('2025-06-01') TO ('2025-07-01');
CREATE TABLE execution_2025_07 PARTITION OF execution_entity
    FOR VALUES FROM ('2025-07-01') TO ('2025-08-01');
CREATE TABLE execution_2025_08 PARTITION OF execution_entity
    FOR VALUES FROM ('2025-08-01') TO ('2025-09-01');
CREATE TABLE execution_2025_09 PARTITION OF execution_entity
    FOR VALUES FROM ('2025-09-01') TO ('2025-10-01');
CREATE TABLE execution_2025_10 PARTITION OF execution_entity
    FOR VALUES FROM ('2025-10-01') TO ('2025-11-01');
CREATE TABLE execution_2025_11 PARTITION OF execution_entity
    FOR VALUES FROM ('2025-11-01') TO ('2025-12-01');
CREATE TABLE execution_2025_12 PARTITION OF execution_entity
    FOR VALUES FROM ('2025-12-01') TO ('2026-01-01');

-- 索引（在每个分区上创建）
CREATE INDEX idx_execution_2025_01_status ON execution_2025_01(status);
CREATE INDEX idx_execution_2025_01_workflow ON execution_2025_01(workflow_id);
-- ... 每月分区重复
```

### 审计日志表分区
```sql
CREATE TABLE audit_log (
    id BIGSERIAL,
    request_id VARCHAR(64) NOT NULL,
    api_key_hash VARCHAR(64),
    client_ip INET,
    model VARCHAR(64),
    prompt_tokens INTEGER DEFAULT 0,
    completion_tokens INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    latency_ms INTEGER DEFAULT 0,
    http_status SMALLINT DEFAULT 200,
    error_code VARCHAR(32),
    cost_usd DECIMAL(10,6) DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (id, created_at)
) PARTITION BY RANGE (created_at);

-- 按月分区
CREATE TABLE audit_log_2025_01 PARTITION OF audit_log
    FOR VALUES FROM ('2025-01-01') TO ('2025-02-01');
-- ... 后续分区
```

## 归档策略

### PostgreSQL 自动清理
```sql
-- 删除超过 30 天的完成记录
-- 在 pg_cron 中每 3 小时执行一次
SELECT cron.schedule('cleanup-executions', '0 */3 * * *',
    $$DELETE FROM execution_entity
      WHERE created_at < NOW() - INTERVAL '30 days'
        AND status IN ('success', 'error', 'crashed');
    $$);
```

### 对象存储归档脚本
```bash
#!/bin/bash
# archive-to-s3.sh
# 每月 1 日 04:00 执行

set -euo pipefail

TARGET_MONTH=$(date -d "last month" +%Y_%m)
TABLE_NAME="execution_${TARGET_MONTH}"
ARCHIVE_BUCKET="s3://your-bucket/db-archive/"

echo "=== Archiving table: $TABLE_NAME ==="

# 1. 将分区导出为 CSV 并压缩
psql -h $PGHOST -U $PGUSER -d $PGDATABASE -c "\COPY ${TABLE_NAME} TO '/tmp/${TABLE_NAME}.csv' CSV HEADER"
gzip /tmp/${TABLE_NAME}.csv

# 2. 上传到对象存储
aws s3 cp /tmp/${TABLE_NAME}.csv.gz ${ARCHIVE_BUCKET}${TABLE_NAME}.csv.gz \
  --storage-class STANDARD_IA

# 3. 验证上传
aws s3 ls ${ARCHIVE_BUCKET}${TABLE_NAME}.csv.gz

# 4. 删除分区表
psql -h $PGHOST -U $PGUSER -d $PGDATABASE -c "DROP TABLE IF EXISTS ${TABLE_NAME};"

# 5. 清理临时文件
rm /tmp/${TABLE_NAME}.csv.gz

echo "=== Archival complete: $TABLE_NAME ==="
```

## 恢复操作
```bash
# restore-from-archive.sh
# 从对象存储恢复归档数据
ARCHIVE_FILE="execution_2025_01.csv.gz"
TARGET_TABLE="execution_entity"

# 1. 从 S3 下载
aws s3 cp s3://your-bucket/db-archive/${ARCHIVE_FILE} /tmp/

# 2. 解压
gunzip /tmp/${ARCHIVE_FILE}

# 3. 恢复临时表（避免影响当前表的索引）
CSV_FILE="/tmp/${ARCHIVE_FILE%.gz}"
psql -h $PGHOST -U $PGUSER -d $PGDATABASE <<EOF
CREATE TABLE ${TARGET_TABLE}_restore_202501 (LIKE ${TARGET_TABLE} INCLUDING ALL);
\COPY ${TARGET_TABLE}_restore_202501 FROM '${CSV_FILE}' CSV HEADER;
EOF

# 4. 验证数据完整性
psql -h $PGHOST -U $PGUSER -d $PGDATABASE -c "SELECT count(*) FROM ${TARGET_TABLE}_restore_202501;"
```

## 输出要求
1. 完整的 SQL 分区创建脚本
2. 自动清理的 pg_cron 配置
3. 归档脚本（bash）
4. 恢复脚本（bash）
5. 定期的数据一致性检查脚本
```

---

## 7. 前端管理面板 API 设计

```
# Role: 全栈工程师（React + Go/Python）
# Task: 设计 AI 自动化集群的前端管理面板的 API

## 页面清单

### 1. 仪表盘 (Dashboard)
```
GET /api/v1/dashboard/stats
响应:
{
    "total_workflows": 42,
    "active_workflows": 15,
    "executions_today": 1250,
    "executions_this_month": 28500,
    "tokens_today": 350000,
    "tokens_this_month": 8500000,
    "cost_today_usd": 1.75,
    "cost_this_month_usd": 42.50,
    "active_keys": 8,
    "error_rate_24h": 0.023,
    "avg_latency_ms_24h": 1850,
    "trends": {
        "executions": [/* 近7天每日执行数 */],
        "tokens": [/* 近7天每日Token消耗 */],
        "cost": [/* 近7天每日费用 */],
        "latency": [/* 近7天每日延迟P50/P95 */]
    },
    "top_workflows": [
        {"id": 1, "name": "Customer Q&A", "executions": 500, "tokens": 120000}
    ],
    "recent_errors": [
        {"execution_id": "...", "workflow_name": "...", "error": "...", "time": "..."}
    ]
}
```

### 2. 工作流管理
```
GET /api/v1/workflows?page=1&page_size=20&status=active&search=customer
响应:
{
    "total": 42,
    "page": 1,
    "page_size": 20,
    "items": [
        {
            "id": 1,
            "name": "Customer Q&A",
            "active": true,
            "node_count": 8,
            "executions_24h": 350,
            "error_rate_24h": 0.01,
            "avg_latency_ms": 1200,
            "last_execution": "2025-01-15T14:30:00Z",
            "created_at": "2024-12-01T00:00:00Z"
        }
    ]
}

PUT /api/v1/workflows/:id/toggle
请求体: {"active": false}
响应: {"id": 1, "active": false}

DELETE /api/v1/workflows/:id
响应: 204 No Content
```

### 3. 执行记录查询
```
GET /api/v1/executions?workflow_id=1&status=error&start=2025-01-01&end=2025-01-15&page=1
响应:
{
    "total": 34,
    "page": 1,
    "page_size": 20,
    "items": [
        {
            "id": 1001,
            "execution_id": "exec-uuid-xxx",
            "workflow_name": "Customer Q&A",
            "status": "error",
            "error_message": "OpenAI API timeout",
            "duration_ms": 30250,
            "tokens_used": 450,
            "cost_usd": 0.002,
            "started_at": "2025-01-15T14:30:00Z",
            "finished_at": "2025-01-15T14:30:30Z"
        }
    ]
}

GET /api/v1/executions/:id
响应:
{
    "execution_id": "exec-uuid-xxx",
    "workflow": { "id": 1, "name": "Customer Q&A" },
    "status": "error",
    "error_message": "OpenAI API timeout at node 'LLM Call'",
    "input_data": {"message": "你好"},
    "output_data": null,
    "nodes": [
        {
            "node_id": "n1",
            "node_name": "Webhook",
            "type": "webhook",
            "status": "success",
            "duration_ms": 5,
            "input": {},
            "output": {"body": "..."}
        },
        {
            "node_id": "n2",
            "node_name": "LLM Call",
            "type": "http_request",
            "status": "error",
            "duration_ms": 30200,
            "error": "timeout",
            "input": {"url": "https://api.openai.com/..."},
            "output": null
        }
    ],
    "duration_ms": 30250,
    "tokens_used": 450,
    "cost_usd": 0.002,
    "started_at": "2025-01-15T14:30:00Z"
}
```

### 4. API Key 管理
```
GET /api/v1/keys
响应:
{
    "total": 8,
    "items": [
        {
            "id": 1,
            "name": "Master Key (admin)",
            "key_prefix": "sk-adm...",
            "is_master": true,
            "is_active": true,
            "allowed_models": ["gpt-4", "deepseek-chat"],
            "usage_24h": 12000,
            "monthly_quota": 10000000,
            "monthly_usage": 3500000,
            "created_at": "2024-10-01T00:00:00Z",
            "last_used": "2025-01-15T14:28:00Z"
        }
    ]
}

POST /api/v1/keys
请求体:
{
    "name": "Customer A Production",
    "type": "sub",
    "allowed_models": ["deepseek-chat"],
    "monthly_quota": 1000000,
    "rate_limit_rpm": 60,
    "allowed_ips": ["192.168.1.0/24"],
    "expires_in_days": 365
}
响应:
{
    "id": 9,
    "name": "Customer A Production",
    "api_key": "sk-live-a1b2c3d4...",
    "key_prefix": "sk-live...",
    "warning": "请立即保存此 Key，它只会显示一次"
}

DELETE /api/v1/keys/:id
响应: 204 No Content

POST /api/v1/keys/:id/renew
请求体: {"expires_in_days": 365}
响应: {"id": 9, "expires_at": "2026-01-15T00:00:00Z"}

POST /api/v1/keys/:id/revoke
响应: {"id": 9, "is_active": false, "revoked_at": "2025-01-15T14:30:00Z"}
```

### 5. 系统配置
```
GET /api/v1/settings
响应:
{
    "providers": [
        {"name": "deepseek", "base_url": "https://api.deepseek.com", "models": ["deepseek-chat"]}
    ],
    "rate_limits": {
        "global_rpm": 1000,
        "global_tpd": 10000000
    },
    "retention": {
        "executions_hot_days": 30,
        "audit_hot_days": 7
    },
    "backup": {
        "pg_full_backup_time": "03:00",
        "wal_archive_interval_seconds": 300,
        "backup_retention_days": 30
    },
    "alerts": {
        "email": "admin@example.com",
        "webhook": "https://hooks.example.com/alert"
    }
}

PUT /api/v1/settings
请求体: 同上（修改部分字段）
响应: 更新后的全部配置
```

## 输出要求
1. 完整的 OpenAPI 3.0 规格文件（openapi.yaml）
2. 每个 API 端点对应的 Go/Python handler 框架代码
3. 前端数据模型 TypeScript 类型定义
4. React Query / Vue Query 的 API hooks 示例
```

---

> *以上所有提示词模板均已包含完整的上下文、数据类型、API 规格和约束条件。复制后即可直接使用。根据你的实际场景调整参数和细节。*
