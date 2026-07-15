# 自研重构路线图：用 o1-preview / Claude Opus 辅助重写的完整路径

> **文档定位**：Form-B 卖的是思想，不是代码。客户购买 Form-B 后，可以用这份路线图 + AI 提示词模板，独立完成自研重构。本文展示"从买现成方案 → 理解它 → 重写它 → 超越它"的完整路径。

---

## 为什么要重构？

**直接回答这个问题**：既然 n8n + docker-compose 已经能跑，为什么还要自研重写？

买 Form-B 的客户通常处于以下三种状态之一：

1. **状态 A（创始/独狼工程师）**：你想把 n8n 替换为更轻量的 Go/Python 版工作流引擎，减少对外部开源项目的依赖。
2. **状态 B（技术负责人/CTO）**：你需要在客户现场部署一个"看起来是我们自己做的"产品，而不是给客户看 n8n 的白色界面。
3. **状态 C（企业架构师）**：n8n 的企业版授权太贵，且自研后可以将核心能力嵌入到你的产品中。

无论哪种状态，下面的路线图都是通用的。

### 重构的战术价值

```
原始形态（Form-B 交付）           目标形态（自研重构后）
┌──────────────────────┐          ┌──────────────────────┐
│ n8n（低代码编排）    │          │ 自研工作流引擎       │
│ PostgreSQL           │          │ PostgreSQL            │
│ Redis                │          │ Redis（可选）         │
│ Nginx                │          │ Nginx                 │
│ auth-server          │          │ auth-server（优化）   │
│ ai-gateway           │  ──→    │ ai-gateway（优化）    │
│ pgadmin              │          │ 自研管理面板          │
│ 监控（外部）         │          │ 内置监控              │
└──────────────────────┘          └──────────────────────┘

核心变化:
  ✅ 去掉 n8n → 自研工作流引擎（不做低代码做 API-first）
  ✅ 去掉 pgadmin → 内置在管理面板
  ✅ 去掉外部监控 → 自研轻量监控
  ❌ 保留 PG/Redis/Nginx（成熟基础设施，不要重复造轮子）
  ❌ 保留 auth-server+ai-gateway（已是轻量自研，优化即可）
```

---

## 阶段一：理解现有架构（第 1 周）

### 目标

用 AI 辅助完全理解 Form-B 的产品架构和技术选型逻辑。

### 输出物

- 技术选型报告（为什么选 n8n/为什么可能选别的）
- 组件依赖图（哪些组件必须、哪些可选）
- 数据流图（请求如何从外部进入，经过哪些组件，最终如何响应）

### AI 提示词

```
# 提示词 1：用 Claude Opus 分析现有架构

我手头有一个 AI 自动化集群系统，包含以下组件：
- n8n（工作流编排引擎，基于 Node.js）
- PostgreSQL 16（主数据库，含 pgvector 扩展）
- Redis 7（队列 + 缓存）
- Nginx（反向代理 + 限流）
- auth-server（Rust/Golang 实现的 License 和 API Key 服务）
- ai-gateway（Python/Go 实现的 AI API 代理）

请帮我回答以下问题：
1. 这个架构中，哪些组件是高内聚的？哪些是耦合过紧的？
2. 如果我要用 Go 语言自研替代 n8n，最核心需要实现的功能是什么？
3. PostgreSQL 在这个架构中承担了多个角色（OLTP 数据、JSON 存储、向量搜索），
   这种"一库多用"的风险是什么？当数据量达到什么级别时需要拆分？
4. 请输出一张 Mermaid 格式的组件依赖图。
```

### 本周实操清单

```yaml
day_1:
  - 部署 Form-B 的 docker-compose，确认所有服务正常运行
  - 用 AI 分析架构，输出技术选型报告

day_2:
  - 深入阅读 n8n 文档：理解工作流引擎的核心概念
  - 重点学习：Webhook、Node、Execution、Queue 模式
  - 标记你认为需要自研保留的核心功能

day_3:
  - 阅读 auth-server 源码（如果随产品提供）
  - 理解 License 生成/验证流程
  - 理解 API Key 的生命周期管理

day_4:
  - 阅读 ai-gateway 源码
  - 理解三层审核机制的具体实现
  - 标记出你认为可以优化的点

day_5:
  - 编写第一版技术选型报告
  - 画出系统的数据流图
  - 确定自研的范围切分
  - 输出阶段一的完整交付物
```

---

## 阶段二：核心服务重写（第 2-3 周）

### 目标

用 Go 或 Python 重写系统的核心组件。

### 决策：Go vs Python？

```yaml
选择 Go 的场景:
  - 你需要高并发处理（> 1000 qps）
  - 你计划部署为独立二进制文件（不依赖运行时）
  - 你的团队有剩余 Go 开发资源
  - 你要替换 n8n（性能敏感的工作流调度）

选择 Python 的场景:
  - 你只是要在 n8n 基础上做二次开发
  - 你需要快速原型验证（团队 Python 熟练度更高）
  - 你对性能没有极端要求（< 100 qps）
  - 你的团队主要是 AI/ML 工程师（天然 Python 背景）

推荐: 混合策略
  - 核心编排层（原 n8n 替代）→ Go（性能敏感）
  - AI API 代理层（ai-gateway）→ Python FastAPI（生态优势）
  - 认证授权层（auth-server）→ Go（安全 + 高并发）
  - 管理后台 → 任意前端框架（React/Vue）
```

### 第 2 周：用 AI 生成核心代码框架

#### 目标 1：重构 auth-server

```yaml
任务: 用 Go 语言实现 RSA 签名验证的 License 授权服务
工时估算: Go 5天 / Python 3天
难度: ⭐⭐⭐
```

**AI 提示词模板（完整）**：

```
# 提示词：用 Go 语言实现 License 授权服务

请你帮我用 Go 语言实现一个 RSA 签名验证的 License 授权服务，要求如下：

## 功能需求
1. RSA-2048 密钥对生成（管理端生成 License）
2. License 验证流程：
   - 读取 License 文件（格式：自定义加密字符串）
   - RSA 公钥解密验证签名
   - 提取并验证以下字段：
     a) License 过期时间（expires_at）
     b) 机器指纹绑定（CPU 序列号 + MAC 地址的组合哈希）
     c) 分销商 ID 嵌入（distributor_id）
     d) 功能开关位图（feature_flags）
3. 7 天离线缓存机制：
   - 成功验证一次的 License，7 天内不再请求验证服务器
   - 7 天后自动过期，需要重新验证
   - 离线缓存文件存储在 /etc/license/cache.json
4. 机器指纹生成：
   - 读取 CPU 序列号（Linux: /proc/cpuinfo 中的 serial）
   - 读取主网卡 MAC 地址
   - SHA256(CPU_SERIAL + ":" + MAC) 作为指纹
5. RESTful API：
   - POST /api/v1/activate — 激活 License（上传 License Key，返回验证结果）
   - GET /api/v1/status — 查询 License 状态（是否激活/过期/绑定机器）
   - POST /api/v1/renew — 更新 License（传入新 Key）

## 技术约束
- Go 1.22+
- 仅使用标准库 + 以下依赖：
  - github.com/gin-gonic/gin（HTTP 框架）
  - github.com/google/uuid（请求 ID）
- 编译为单二进制文件，无外部运行时依赖
- 配置文件为环境变量 + YAML 文件双来源

## 安全性要求
- License Key 在内存中被使用后立即清零（敏感数据安全）
- 验证失败 5 次后 1 小时的退避策略
- 所有 API 端点需要 API Key 验证（内网服务间认证）

## 输出格式
请输出完整的 Go 源码，包含：
1. main.go
2. internal/license/license.go（License 生成与验证）
3. internal/auth/middleware.go（认证中间件）
4. internal/fingerprint/fingerprint.go（机器指纹采集）
5. internal/cache/cache.go（7 天离线缓存）
6. config/config.go（配置读取）
7. go.mod
8. Dockerfile（多阶段构建）

附上每个文件的单元测试示例。
```

#### 目标 2：重构 ai-gateway

```yaml
任务: 用 Python FastAPI 实现 AI API 安全代理
工时估算: Go 7天 / Python 4天
难度: ⭐⭐⭐⭐
```

**AI 提示词模板（完整）**：

```
# 提示词：用 Python FastAPI 实现 AI API 安全代理

请帮我用 Python FastAPI 实现一个 AI API 安全代理网关，功能如下：

## 核心功能
1. 统一 AI API 入口：
   - 接收来自 n8n 或其他客户端的请求
   - 将请求转发到对应的 AI 服务提供商（OpenAI、DeepSeek、Anthropic）
   - 返回统一格式的响应

2. 三层安全审查：
   a) 鉴权层：
      - API Key 验证（支持主 Key + 子 Key 两级）
      - Key 有效期、可用模型白名单、IP 白名单检查
      - JWT 二级鉴权（可选）
   b) 节流层：
      - 全局限流（Token Bucket 算法）
      - 按 Key 限流
      - 按 IP 限流
      - 按模型限流（不同模型设置不同 TPM）
      - 月度配额检查 + 预算告警
   c) 审计层：
      - 全量请求/响应元数据记录（不含敏感内容）
      - Token 用量统计
      - 失败原因分类记录

3. Provider 动态路由：
   - 从请求中选择 model，自动路由到对应 Provider
   - 支持多 Provider 故障切换（Primary → Secondary → Fallback）
   - 支持流量百分比分发（如 70% DeepSeek + 30% OpenAI）

## 技术栈
- Python 3.12+
- FastAPI（Web 框架）
- Redis（限流计数、缓存）
- PostgreSQL（审计日志、用户配置）
- prometheus_client（指标暴露）
- httpx（异步 HTTP 客户端）

## 性能要求
- P50 延迟增加 < 50ms（相对直连 API）
- P99 延迟增加 < 200ms
- 支持 1000+ 并发请求
- 内存: < 256MB idle

## 关键设计点
1. 限流算法使用令牌桶，令牌在 Redis 中维护
2. 审计日志使用异步批量写入，不阻塞请求处理
3. Provider 健康检查使用被动检测（请求超时标记不可用）
4. 支持优雅降级（Redis 不可用时退化为内存缓存）

## 输出格式
输出完整的 Python 项目结构，包含：
- main.py
- app/config.py（配置管理）
- app/auth.py（认证模块）
- app/rate_limiter.py（限流器）
- app/audit.py（审计模块）
- app/router.py（路由模块）
- app/providers/（各 AI 服务提供商的适配器）
- requirements.txt
- Dockerfile
- docker-compose.yml（集成测试用）
```

### 第 3 周：集成测试

#### 测试策略

```yaml
integration_test_week:

  day_1: 模块内集成
    - 将 AI 生成的所有模块组合在一起
    - 运行编译/类型检查
    - 修复 AI 生成的代码中的 bug（通常在接口定义不匹配上）

  day_2: 服务级集成
    - 用 docker-compose 启动所有重写的服务
    - 测试 auth-server → ai-gateway → n8n 的完整调用链
    - 验证限流（发送超量请求看是否被正确拒绝）
    - 验证鉴权（用错误 Key 看返回什么）

  day_3: 端到端测试
    - 用 n8n 工作流调用完整的重写后的系统
    - 测试所有关键路径：成功、失败、超时、限流
    - 验证审计日志是否正确写入

  day_4: 压力测试
    - 模拟生产流量对系统施压
    - 记录 P50/P95/P99 延迟
    - 验证熔断机制在资源耗尽时自动触发
    - 验证自恢复机制

  day_5: 安全测试 + 修复
    - 测试 API Key 泄露场景（模拟 Key 泄漏后的调用）
    - 测试 Prompt 注入
    - 测试 DoS 场景
    - 所有发现的 bug 编写修复（AI 辅助）

  day_6~7: 文档 + 部署脚本
    - 编写部署文档
    - 编写运维手册
    - 编写恢复 SOP
    - 更新 docker-compose.yml
```

#### AI 辅助修复 Bug 的提示词

```
# 提示词：调试并修复集成测试中的问题

这是我的 Go 代码中 License 验证函数的测试输出：

```
=== RUN   TestLicenseVerification
    license_test.go:42: Expected true, got false
    license_test.go:43: Error: signature verification failed
--- FAIL: TestLicenseVerification (0.01s)
```

错误发生在以下代码块：
```go
func verifySignature(licenseData []byte, signature []byte, publicKey *rsa.PublicKey) bool {
    hashed := sha256.Sum256(licenseData)
    err := rsa.VerifyPKCS1v15(publicKey, crypto.SHA256, hashed[:], signature)
    return err == nil
}
```

License 生成端的签名代码（为了对比）：
```go
func signLicense(licenseData []byte, privateKey *rsa.PrivateKey) ([]byte, error) {
    hashed := sha256.Sum256(licenseData)
    return rsa.SignPKCS1v15(rand.Reader, privateKey, crypto.SHA256, hashed[:])
}
```

错误分析：
1. 签名和验证都使用 SHA256，看起来没问题
2. 问题可能出在 LicenseData 的序列化方式上——两端是否使用相同的格式？
3. 让我检查一下序列化逻辑...

请帮我分析 Bug 原因并修复。
```

---

## 阶段三：持续优化（第 4 周 及以后）

### 优化方向

```yaml
phase_3_optimization:

  week_4: 核心替换
    - 如果目标是替换 n8n，这周开始用 Go 实现最小工作流引擎
    - 核心能力：Webhook 监听 + 节点链式执行 + 条件分支
    - 不需要完整复制 n8n，只复制你需要的那 20% 功能

  week_5~6: 管理面板
    - 如果目标是前端管理面板，这周开始开发
    - 核心页面：工作流管理、调用统计、Key 管理、日志查看
    - 建议使用 React/Vue + TailwindCSS + shadcn/ui

  week_7~8: 监控与告警
    - 集成 Prometheus 指标采集
    - 核心告警规则：服务中断、CPU 超限、API 调用失败率
    - 告警通道：企业微信 / 钉钉 / Slack / Email
    - 日志聚合：Loki（轻量）或 生产级 ELK

  month_3: 性能优化
    - 对高频调用路径做性能分析
    - 优化 n8n 替换引擎的并行执行能力
    - 优化 ai-gateway 的连接池和超时策略
    - 优化 PostgreSQL 查询性能（索引优化 + 查询分析）

  month_6: 高可用升级
    - 如果不是必须，强烈建议保持在 docker-compose 层面
    - 如果必须：迁移到 K8s（参考 01-system-architecture.md）
    - 部署 Patroni + etcd 高可用 PG
    - 实现跨机房灾备
```

### AI 驱动迭代优化的闭环

```yaml
optimization_loop:
  步骤:
    1. 从监控中获取性能数据
    2. 使用 AI 分析性能瓶颈
       Prompt: "分析以下 Prometheus 指标数据，找出性能瓶颈..."

    3. AI 提出优化方案
       Prompt: "基于 Go pprof 输出，优化 api-gateway 的请求处理性能..."

    4. 实施优化（AI 辅助代码生成）
    5. 部署到预发布环境
    6. 重复 1-5 直到达到目标

  关键指标:
    - API 请求 P99 延迟
    - PostgreSQL 查询延迟
    - 内存使用率趋势
    - CPU 使用率趋势
    - 错误率
```

---

## 时间线总览

```
Week 1: 理解
  ┌─────────────────────────────────────────────────────┐
  │ 部署 → AI 分析 → 源码阅读 → 技术报告 → 范围切分     │
  └─────────────────────────────────────────────────────┘

Week 2-3: 重写
  ┌─────────────────────────────────────────────────────┐
  │ auth-server 重写 → ai-gateway 重写 → 集成测试      │
  │ (AI 生成代码框架 + 人工审查)                         │
  └─────────────────────────────────────────────────────┘

Week 4: 替换
  ┌─────────────────────────────────────────────────────┐
  │ n8n 最小替代 → 后端核心逻辑实现                      │
  │ (仅实现你需要的那 20% 功能)                          │
  └─────────────────────────────────────────────────────┘

Week 5-6: 面板
  ┌─────────────────────────────────────────────────────┐
  │ 管理面板开发 → 管理 API 集成 → Beta 发布             │
  └─────────────────────────────────────────────────────┘

Week 7+: 持续迭代
  ┌─────────────────────────────────────────────────────┐
  │ 监控 → 告警 → 性能优化 → 高可用 → 生产稳定          │
  └─────────────────────────────────────────────────────┘
```

---

> **下篇**：[02-component-estimates.md](./02-component-estimates.md) — 各组件开发工时估算
