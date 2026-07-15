# AI-API 安全审核代理深度解析

> **文档定位**：本文件面向安全架构师与技术负责人，阐述为什么需要 AI-API 网关、三层审核机制的设计细节、攻击面分析以及合规日志策略。

---

## 1. 为什么需要 AI-API 网关？

### 1.1 直接暴露 AI API 的风险矩阵

很多团队的第一版架构是这样的——n8n 工作流直接调用 OpenAI/DeepSeek 的 API：

```
n8n workflow → HTTP Request Node → https://api.openai.com/v1/chat/completions
```

这种"直连"架构在你只有 3 个工作流时没有任何问题。但当工作流扩展到 50 个、调用方扩展到不同客户时，风险开始集中暴露：

**风险 1：API Key 泄露的经济损失**

这是最直接的物理伤害。你的 API Key 嵌入在 n8n 工作流中，而 n8n 的工作流配置通过 Web UI 暴露给所有操作员。以下是真实发生过的场景：

> **Case Study**：某团队在 n8n 工作流中直接硬编码了 OpenAI API Key。一个实习生将 n8n 工作流的截图发到了公司 Slack（包含工作流配置中的 API Key）。24 小时内，该 Key 被用于 15,000 次非授权的 GPT-4 调用，产生 $7,800 的账单。

**经济预期**：对于使用 DeepSeek / OpenAI 大模型 API 的团队，单次 API Key 泄露的平均财务损失在 $500 - $5,000 之间。这个数字取决于泄露被发现的速度。

**风险 2：缺乏统一审计**

当 50 个工作流各自独立调用外部 API 时，回答以下问题需要逐个检查每个工作流：
- 上个月我们花了多少 AI API 费用？（需要从各个工作流的 n8n 执行日志中汇总）
- 哪个用户 / 客户调用了最多的 Token？（n8n 没有用户维度的统计）
- 有没有异常调用模式？（每个工作流的调用模式不同，无法统一分析）

**风险 3：无法实施统一的访问控制**

- 工作流 A 应该只能调用 GPT-4，但配置写成了 GPT-4o，客户看到了不应该看到的模型能力。
- 工作流 B 每 10 秒轮询一次 API——这在低负载时没问题，但当 10 个工作流同时轮询时，API 调用量激增 10 倍。
- 你无法对不同的 API Key 设置不同的速率限制——因为所有工作流共享一个 Key。

**风险 4：AI API 服务不稳定的冲击**

当 OpenAI 或 DeepSeek 出现故障时（这比你想的更频繁），所有直连的工作流同时失败。没有优雅的降级机制，没有 failover 方案。

### 1.2 AI-API 网关的价值量化

| 安全维度 | 无网关（直连） | 有 AI-API 网关 | 改进 |
|---------|-------------|----------------|------|
| API Key 泄露风险 | Key 嵌入工作流配置 | Key 存储在网关环境变量 | **降低 90%** |
| 统一审计 | 分散在各 n8n 执行日志 | 集中 JSON 日志 + Dashboard | **全量可查** |
| 访问控制 | 全部或全不 | 按 Key/Workflow/User 分级 | **精细化** |
| 速率限制 | 无（应用层靠 n8n 自己控） | 多级限流 + 降级 | **可量化** |
| 费用控制 | 月底出账单才知花多少 | 实时配额 + 预算告警 | **实时可控** |
| 高可用 | 单点 API 直连 | 多 API Provider 故障切换 | **SLA 提升** |
| 安全合规 | 不可审计 | 全量审计日志 | **合规** |

---

## 2. 三层审核机制

ai-gateway 的安全架构设计为三层叠加——每一层都是独立的安全防线，任何一层的突破不意味着其他层也被突破。

```
请求 → [Layer 1: 鉴权] → [Layer 2: 节流] → [Layer 3: 审计] → AI API
              │                  │                   │
              ▼                  ▼                   ▼
          API Key 验证       速率限制          全量日志记录
          Token 解析         配额检查          请求/响应快照
          签名验证           预算控制          Token 用量统计
```

### 2.1 Layer 1：鉴权（Authentication & Authorization）

**API Key 验证策略**：

```python
# ai-gateway 核心鉴权逻辑（类 Python 伪代码）
class AuthServer:
    def __init__(self):
        self.api_keys = {}  # 从数据库或环境变量加载

    def verify_api_key(self, api_key: str) -> dict:
        """
        验证 API Key 的完整生命周期：
        1. 存在性检查（Key 是否在系统中注册）
        2. 有效期限检查（Key 是否过期）
        3. 配额检查（本月用量是否超限）
        4. 权限检查（Key 是否有权调用目标模型）
        5. 来源检查（请求 IP 是否在白名单中）
        """

        # Step 1: Key 存在性
        key_info = self.api_keys.get(api_key)
        if not key_info:
            raise AuthError("Invalid API Key", code=40101)

        # Step 2: 有效期
        if datetime.now() > key_info.expires_at:
            raise AuthError("API Key expired", code=40102)

        # Step 3: 配额
        if key_info.monthly_usage >= key_info.monthly_quota:
            raise AuthError("Monthly quota exceeded", code=40201)

        # Step 4: 权限
        if request.model not in key_info.allowed_models:
            raise AuthError(f"Model {request.model} not allowed", code=40301)

        # Step 5: 来源
        if key_info.allowed_ips and request.ip not in key_info.allowed_ips:
            raise AuthError(f"IP {request.ip} not whitelisted", code=40302)

        return key_info
```

**Token 级鉴权**：
对于需要细粒度授权的场景（如不同用户使用不同的 AI 能力），ai-gateway 支持 JWT 二级鉴权：

- **Master API Key**：用于系统管理，可以创建/撤销子 Key
- **Sub Key**：绑定到具体工作流或客户，可设置独立的配额和权限
- **临时 Token**：用于会话级授权，有效期 15-60 分钟

**签名验证**：
对于企业级客户，可以使用 HMAC-SHA256 对请求体签名，防止中间人篡改：

```bash
# 客户端签名示例
SECRET="shared_hmac_secret"
TIMESTAMP=$(date +%s)
BODY='{"model":"deepseek-chat","messages":[...]}'
SIGNATURE=$(echo -n "$TIMESTAMP.$BODY" | openssl dgst -sha256 -hmac "$SECRET" | awk '{print $NF}')

curl -X POST https://ai-gateway/api/v1/chat/completions \
  -H "X-Api-Key: your_key" \
  -H "X-Timestamp: $TIMESTAMP" \
  -H "X-Signature: $SIGNATURE" \
  -d "$BODY"
```

### 2.2 Layer 2：节流（Rate Limiting & Quota Control）

**多层级限流**：

```python
# 限流策略配置（YAML 格式）
rate_limits:
  # 全局限流：所有请求的总上限
  global:
    requests_per_minute: 1000
    tokens_per_day: 10000000  # 约 500 万汉字

  # 按 API Key 限流
  per_key:
    requests_per_minute: 100
    tokens_per_hour: 500000
    concurrent_requests: 5

  # 按 IP 限流（防止 Key 泄露后被滥用）
  per_ip:
    requests_per_minute: 30
    burst: 5

  # 按模型限流（不同模型成本不同）
  per_model:
    gpt-4:
      requests_per_minute: 20
      tokens_per_minute: 100000
    deepseek-chat:
      requests_per_minute: 60
      tokens_per_minute: 300000
    gpt-4o-mini:
      requests_per_minute: 200
      tokens_per_minute: 1000000
```

**限流算法选择**：

```
Token Bucket（推荐）
  优点：允许短时突发，平滑长期速率
  适用：AI API 调用天然有突发性（用户提问高峰）
  实现：in-memory 或 Redis

Sliding Window Log
  优点：精确控制时间窗口内的请求数
  适用：需要严格遵约的 SLA 场景
  实现：Redis Sorted Set（ZADD + ZREMRANGEBYSCORE）

Leaky Bucket
  优点：完全平滑输出，适合处理后端
  适用：AI API 后端有固定吞吐能力
  注意：会导致突发请求被丢掉而非排队
```

**预算控制**：

预算控制是 ai-gateway 中最容易被忽略但实际价值最高的功能：

```yaml
# 预算告警链
budget_alerts:
  - threshold: 50%
    action: notify_admin(wechat)
  - threshold: 80%
    action: notify_admin(sms) + slowdown_noncritical(rate_limit * 0.5)
  - threshold: 95%
    action: block_all_nonessential() + notify_admin(call)
  - threshold: 100%
    action: block_all() + CEO_notification()
```

### 2.3 Layer 3：审计（Full Audit Logging）

**全量日志的内容决策**——什么该记，什么不该记：

```yaml
audit_log:
  # ✅ 必须记录（合规要求）
  always_record:
    - timestamp: ISO8601 时间戳（精确到毫秒）
    - request_id: 全局唯一请求 ID（UUID v4）
    - api_key_hash: API Key 的 SHA256 哈希（**不是明文**）
    - client_ip: 来源 IP 地址
    - model: 调用的模型名（如 deepseek-chat）
    - prompt_tokens: 输入 Token 数
    - completion_tokens: 输出 Token 数
    - total_tokens: 总 Token 数
    - wall_time_ms: 请求总耗时
    - http_status: 响应状态码
    - error_code: 错误码（如果有）

  # ✅ 建议记录（安全审计需要）
  recommended:
    - request_summary: 请求体的摘要（前 100 个字符的 hash）
    - response_summary: 响应体摘要
    - workflow_id: n8n 工作流 ID（如已知）
    - customer_id: 客户标识
    - rate_limit_hits: 本次请求的限流命中信息

  # ❌ 不能记录（隐私与合规）
  never_record:
    - raw_api_key: 禁止明文记录 API Key
    - full_prompt: 禁止记录完整的用户 Prompt（除非客户同意）
    - full_completion: 禁止记录完整的 AI 输出（知识产权）
    - user_password: 认证过程中的任何密码
    - credit_card: 任何支付信息

  # ⚠️ 仅按需记录（需要客户明确同意）
  on_demand:
    - full_request_body: 完整请求体（调试模式）
    - full_response_body: 完整响应体（质量分析）
```

---

## 3. 攻击面分析

### 3.1 API Key 泄露与补救

**泄露渠道**：
1. Git 仓库误提交（最常见）—— `.env` 文件、配置文件中硬编码
2. 日志泄露——n8n 执行日志包含了 HTTP Request 节点的全部 Header
3. 截图/录屏——团队协作中的无意识泄露
4. 网络嗅探——内部网络中没有使用 TLS 的服务间通信
5. 第三方依赖——npm package 在 CI 过程中读取环境变量并发送到外网

**检测与补救措施**：

```
检测方法：
  1. API Key 在非正常时间段（比如凌晨 3 点）的大量调用
  2. 来自非预期地理区域的请求
  3. 单个 Key 的调用模式突然改变

即时补救（SOP）：
  1. 立即在 ai-gateway 中吊销该 Key（几秒内生效）
  2. 生成新 Key 并更新工作流配置
  3. 导出自吊销时刻起 7 天的审计日志（取证用）
  4. 检查账单确认损失范围
  5. 建立 Key 轮换机制（建议每 90 天轮换一次）
```

### 3.2 注入攻击

AI API 存在两种注入攻击：

**Prompt 注入（Prompt Injection）**：
攻击者通过在用户输入中嵌入指令，绕过 AI 的安全限制。

```python
# ai-gateway 的 prompt 注入检测（简化版）
class PromptInjectionDetector:
    """注入检测：基于规则 + 模型的双重检测"""

    # 规则层：快速扫描已知的注入模式
    RULES = [
        r"(?i)ignore\s+(previous|above|all)\s+(instructions|directions)",
        r"(?i)system\s+(prompt|message|instruction)",
        r"(?i)you\s+are\s+(now|not)\s+(a\s+)?(assistant|ai|chatbot)",
        r"(?i)reset\s+(conversation|session|memory)",
        r"(?i)输出\s+你的\s+(系统|初始化)\s+(提示词|指令|设定)",
    ]

    def detect(self, messages: list) -> bool:
        """返回 True 表示检测到注入"""
        for msg in messages:
            content = msg.get("content", "")
            for rule in self.RULES:
                if re.search(rule, content):
                    self.alert(f"Rule hit: {rule}")
                    return True
        return False
```

**建议**：在生产环境中，ai-gateway 不应做过于激进的 Prompt 过滤（会误伤正常业务）。正确的设计是**标记可疑请求但不阻止**，同时将标记结果写入审计日志，供后续安全分析使用。

### 3.3 滥用调用

**常见的滥用模式**：

| 模式 | 描述 | 检测方法 |
|------|------|---------|
| 暴力调用 | 同一 Key 在短时间内的极高频率请求 | 速率限制自动拦截 |
| 批量枚举 | 遍历参数尝试不同组合（如不同 Prompt 测试边界） | 请求熵分析 + 相似度检测 |
| 异常 Token 消耗 | 单次请求使用异常大的 Token 数（如数百万 Token） | Token 上限硬限制 |
| 模型降级 | 尝试用低价模型（deepseek-chat）冒充高价模型（gpt-4） | 模型名白名单验证 |
| 并发滥用 | 创建大量并发连接绕过限流 | 并发连接数限制 |

### 3.4 拒绝服务（DoS）

**AI-API 网关特有的 DoS 风险**：

```
攻击向量：
  1. 慢速攻击：发送极慢的 HTTP 流，占用连接池
  2. Token 消耗攻击：用超长 Prompt（如 32K Token）故意消耗配额
  3. 高并发攻击：短时间内发起大量并行请求
  4. 失败重试攻击：发送大量会失败的请求，消耗鉴权和节流逻辑

防御策略：
  - Nginx 层面：连接超时 + 请求体大小限制（如 5MB）
    client_max_body_size 5m;
    proxy_read_timeout 30s;

  - ai-gateway 层面：
    Token 上限（单次请求 ≤ 128K tokens）
    并发请求限制（每个 Key ≤ 5 并发）
    失败的请求不计入配额（但计入限流统计，防止恶意重试）

  - 应用层面：
    IP 黑名单动态更新（连续 10 次 401 后封禁 1 小时）
```

---

## 4. 日志审计策略

### 4.1 合规要求（密评三级 / 等保三级映射）

在中国地区运营的 AI 系统，有明确的合规要求。以下是密评三级的关键要求与我们的实现映射：

| 合规要求 | 等保要求 | 我们的实现 |
|---------|---------|-----------|
| 操作日志记录 | 对所有用户操作进行日志记录 | ai-gateway 全量审计日志 |
| 日志保护 | 日志不可被篡改 | 日志写入后追加模式 + 每日 hash 链 |
| 日志存储周期 | ≥ 180 天 | 180 天滚动（可按客户需求延长） |
| 用户标识 | 日志应记录用户身份 | API Key 哈希 + 请求来源标识 |
| 权限管理 | 最小权限原则 | 三级授权体系（服务级 Key/工作流级 Key/用户级 Token） |
| 安全审计 | 定期审计日志 | 自动化审计报告 + 异常检测 |

### 4.2 审计日志存储方案

```yaml
# 审计日志存储策略
storage:
  # 热数据：实时查询
  hot:
    engine: Elasticsearch / OpenSearch
    retention: 7 天
    shards: 3
    replicas: 1

  # 温数据：可查询但延迟可接受
  warm:
    engine: ClickHouse / Loki
    retention: 30 天
    compression: zstd

  # 冷数据：归档存储，用于合规审计
  cold:
    engine: S3 / MinIO (Parquet 格式)
    retention: 180 天（或按客户要求延长至 1 年）
    encryption: AES-256

# 自动化审计报告
reporting:
  daily:
    - API 调用量统计（按 Key/模型/时间维度）
    - Token 消耗统计
    - 异常调用检测报告
    - 费用预估
  weekly:
    - 安全事件汇总
    - 合规审计报告
    - Key 轮换提醒
  monthly:
    - 费用对账报告
    - 趋势分析与容量规划
    - 安全策略优化建议
```

### 4.3 审计数据脱敏

在安全合规与隐私保护之间找到平衡：

```python
# 审计日志脱敏器
class AuditSanitizer:
    """确保写入审计日志的数据不含敏感信息"""

    SENSITIVE_PATTERNS = {
        "api_key": r"sk-[a-zA-Z0-9]{20,}",
        "email": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
        "phone": r"1[3-9]\d{9}",
        "id_card": r"\d{18}[\dXx]?",
        "credit_card": r"\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}",
    }

    def sanitize(self, log_entry: dict) -> dict:
        """对日志条目中的敏感字段进行脱敏"""

        # 对整个 JSON 做字符串替换
        log_str = json.dumps(log_entry)
        for field_name, pattern in self.SENSITIVE_PATTERNS.items():
            log_str = re.sub(
                pattern,
                lambda m: m.group(0)[:4] + "*" * (len(m.group(0)) - 8) + m.group(0)[-4:],
                log_str
            )

        return json.loads(log_str)
```

---

> **下篇**：[03-database-design.md](./03-database-design.md) — 数据库设计深度解析
