# 存续优先原则：在资源受限中活着，比在资源富足中死去更强

> **文档定位**：本文阐述"存续优先"——比功能、性能、用户体验更优先原则。在 2C4G 的硬约束下，这不是一个选择，而是一个工程哲学。

---

## 1. 定义：核心业务流程永远优先于非核心

### 1.1 存续优先的出处

存续优先原则直接源自白皮书揭示的 AI 工程的深层结构矛盾：

> "Human architect design follows the priority logic of 'system survival > task efficiency', while AI autonomous operation follows the fixed priority of 'instruction completion > system stability > long-term iteration'. The system has no subjective self-protection mechanism."（白皮书 1.3）

在白皮书的分析中，传统确定性工程遵循 **"系统生存 > 任务效率"** 的优先级逻辑，而 AI 概率工程遵循 **"指令完成 > 系统稳定 > 长期迭代"**——这正是 AI 系统天然不稳定的根源。

Form-B 的产品哲学正是在这个层面进行"工程范式再重构"——将人类架构师设计的优先逻辑硬编码到系统中。

### 1.2 什么是我们说的"存续"？

在 Form-B 的语境中，"存续"有明确的定义：

```
存续 = 以下三个条件同时满足：
  1. n8n 工作流编排引擎在运行（核心业务处理中）
  2. PostgreSQL 在对外服务（数据不丢失、可写入）
  3. auth-server 在对外服务（新请求可以被验证和路由）

允许的降级：
  - Nginx 返回 429（限流）但 auth-server 正常工作
  - Redis 离线但 AI-API 调用走直连（降速但不断联）
  - pgadmin 停止但数据库正常运行
  - 监控 Dashboard 不更新但系统在运行

不允许的降级：
  ❌ PostgreSQL 拒绝写入（数据丢失）
  ❌ n8n 工作流执行到一半异常中止（业务中断）
  ❌ auth-server 不可用（验证不通过，用户无法使用）
```

### 1.3 优先级矩阵

```yaml
survival_priority_matrix:
  level_0_critical:
    description: 系统生存依赖，必须 7×24 在线
    services:
      - n8n main process
      - PostgreSQL (read/write)
      - auth-server
    degradation_zero: 这些服务一旦停止，系统整体定义为"死亡"

  level_1_important:
    description: 核心辅助，停机对体验有重大影响
    services:
      - ai-gateway（停机则 LLM 调用中断）
      - Nginx（停机则外部请求无法进入）
    degradation_allowed: 允许短暂停机（< 15 分钟）做维护

  level_2_nice_to_have:
    description: 体验增强，停机不影响核心业务
    services:
      - Redis cache（降级为直连 PG）
      - pgadmin（停机不影响数据库）
      - monitoring（停机不影响业务处理）
    degradation_allowed: 允许长时间停机

  level_3_optional:
    description: 管理工具，停机不产生任何用户层面的影响
    services:
      - 前端管理面板（用户有 n8n 原生 UI）
      - 日志收集转发（ES/Fluentd/Loki）
      - 自动化备份脚本（错过一次备份不是灾难）
    degradation_allowed: 随时可以停机
```

---

## 2. 熔断机制

### 2.1 熔断的设计哲学

熔断不是为了"防止系统崩溃"，而是为了"让系统在崩溃边缘活下来"。

**关键原则**：熔断应该是**自发的、自动的、不需要人工判断的**。如果需要在检测到 CPU > 80% 后登录服务器执行命令，这不叫熔断，叫"人工灭火"。

### 2.2 自动熔断链条

```python
# 自动熔断守护进程（systemd 服务或 docker sidecar）
# 运行在宿主机上，每分钟检测一次

import psutil
import docker
import requests
import logging
from enum import Enum

class DegradationLevel(Enum):
    NORMAL = 0          # 一切正常
    WARNING = 1         # CPU > 60%，准备降级
    CRITICAL = 2        # CPU > 80%，执行降级
    EMERGENCY = 3       # CPU > 95%，紧急保护

class CircuitBreaker:
    """自动熔断控制器"""

    def __init__(self):
        self.client = docker.from_env()
        self.degradation_level = DegradationLevel.NORMAL
        self.services = {
            "critical": ["n8n", "postgres", "auth-server"],
            "important": ["ai-gateway", "nginx"],
            "optional": ["pgadmin", "redis", "monitoring", "frontend"]
        }

    def check_system_health(self):
        """全系统健康检查"""
        cpu_percent = psutil.cpu_percent(interval=1)
        memory_percent = psutil.virtual_memory().percent
        load_avg = psutil.getloadavg()[0]

        # 决策逻辑
        if cpu_percent > 95 or memory_percent > 95:
            # => 紧急情况
            new_level = DegradationLevel.EMERGENCY
        elif cpu_percent > 80 or memory_percent > 85:
            # => 临界状态
            new_level = DegradationLevel.CRITICAL
        elif cpu_percent > 60 or memory_percent > 70:
            # => 预警
            new_level = DegradationLevel.WARNING
        else:
            new_level = DegradationLevel.NORMAL

        return new_level, {"cpu": cpu_percent, "mem": memory_percent, "load": load_avg}

    def execute_degradation(self, level):
        """执行降级策略"""
        actions = []

        if level >= DegradationLevel.WARNING:
            # 1. 限制非关键流量的入站
            # （通过 Nginx API 动态调整限流阈值）
            actions.append("rate_limit: reduce nginx limit from 100r/m to 50r/m")

        if level >= DegradationLevel.CRITICAL:
            # 2. 停止可选服务，按逆优先级顺序
            for service_name in reversed(self.services["optional"]):
                try:
                    container = self.client.containers.get(service_name)
                    container.stop()
                    actions.append(f"stopped {service_name}")
                except:
                    pass

            # 3. 通知 n8n 降级工作流复杂度
            # （限制只能执行核心工作流）
            self.notify_n8n_degradation()

        if level >= DegradationLevel.EMERGENCY:
            # 4. 最后的保护：拒绝所有非核心请求
            # （Nginx 只允许 healthcheck 通过）
            self.nginx_emergency_mode()

            # 5. 限制 PostgreSQL 连接数
            # 避免新连接消耗最后的内存
            self.limit_pg_connections(5)

            # 6. 发送紧急告警
            self.alert_emergency(actions)

        return actions

    def run_cycle(self):
        """单次检测循环"""
        new_level, metrics = self.check_system_health()

        if new_level != self.degradation_level:
            logging.warning(
                f"Degradation level change: "
                f"{self.degradation_level.name} → {new_level.name}"
            )
            self.degradation_level = new_level

            if new_level != DegradationLevel.NORMAL:
                actions = self.execute_degradation(new_level)
                self.alert_degradation(new_level, metrics, actions)

        return self.degradation_level

    def alert_degradation(self, level, metrics, actions):
        """发送降级告警"""
        alert_data = {
            "level": level.name,
            "metrics": metrics,
            "actions": actions,
            "timestamp": datetime.now().isoformat()
        }
        # 发送到企业微信/钉钉/Slack
        requests.post(
            "https://your-alert-channel/webhook",
            json={"msgtype": "text", "text": json.dumps(alert_data)}
        )

    def notify_n8n_degradation(self):
        """通知 n8n 降级工作流"""
        requests.post(
            "http://n8n:5678/webhook/degradation",
            json={"mode": "survival"}
        )

    def nginx_emergency_mode(self):
        """切换 Nginx 到紧急模式"""
        requests.post(
            "http://nginx:80/_emergency",
            headers={"X-Internal-Token": "secret"}
        )

    def limit_pg_connections(self, max_conn):
        """限制 PG 连接数"""
        import subprocess
        subprocess.run([
            "docker", "exec", "postgres",
            "psql", "-U", "postgres",
            "-c", f"ALTER SYSTEM SET max_connections = {max_conn}; SELECT pg_reload_conf();"
        ])

    def recover_services(self):
        """恢复被降级的服务"""
        if self.degradation_level == DegradationLevel.NORMAL:
            # 系统恢复后，自动恢复被降级的服务
            for service_name in self.services["optional"]:
                try:
                    container = self.client.containers.get(service_name)
                    if container.status != "running":
                        container.start()
                        logging.info(f"Recovered service: {service_name}")
                except:
                    pass
```

### 2.3 熔断策略的时间线

```yaml
熔断实操时间线:

T+0 分钟: CPU 飙升到 85%
  检测: 熔断守护进程发现 CPU > 80%
  动作: 等级从 NORMAL 切换到 CRITICAL
  执行:
    1. Nginx 限流收紧（100r/m → 50r/m）
    2. 停止 pgadmin（无业务影响，回收 ~200MB 内存）
    3. 停止监控采集（回收 ~100MB，监控暂时空白）
  预期效果: 回收约 300MB 内存，CPU 下降到 ~70%

T+2 分钟: CPU 仍在 82%
  检测: 一级降级效果不足
  动作: 继续执行二级降级
  执行:
    1. Redis TTL 缩短为 60 秒（缓存频繁刷，但可用）
    2. 通知 n8n 暂停非核心工作流
    3. 清理 PG 的 idle connections
  预期效果: 释放 PG 连接池资源，减少总线竞争

T+5 分钟: CPU 回落到 65%
  检测: 恢复正常
  动作: 不再继续降级，维持当前状态
  注意: 不急于恢复被停的服务——先稳定 15 分钟

T+20 分钟: CPU 稳定在 30%
  检测: 连续 3 个周期正常
  动作: 自动恢复所有被降级的服务
  执行:
    1. 启动监控
    2. 启动 pgadmin
    3. Redis TTL 恢复
    4. Nginx 限流恢复
    5. 通知团队：自动恢复完成
```

---

## 3. 零无效开销

### 3.1 跑不动的功能不要开

这是实战经验中血泪教训的总结：

```yaml
无效开销检查清单（每添加一个功能前必须回答）:

  问题 1: 这个功能在 2C4G 环境下能顺畅运行吗？
    - 如果是: 加入
    - 如果否: 使用替代方案或跳过

  问题 2: 这个功能如果不运行，用户会感知到吗？
    - 如果会: 必须优化到能运行
    - 如果不会: 默认不开启

  问题 3: 这个功能每个月被使用几次？
    - 如果 > 100 次: 值得部署
    - 如果 < 10 次: 放在手册中，按需启动
    - 如果 < 1 次: 删除

  问题 4: 这个功能的资源消耗是否值得？
    - 计算 ROI: (功能带来的收益) ÷ (消耗的资源)
    - 如果 ROI < 1: 不合理，放弃
    - 如果 ROI 1-3: 可考虑，但要优化
    - 如果 ROI > 3: 值得投入
```

**实例**：

```yaml
❌ 不应该开启的功能:
  - n8n 的执行数据自动清理 → 核心功能，但应在 docker 外部用 cron 完成
  - n8n 的 Webhook 测试界面 → 开发环境使用即可，生产环境关闭
  - PostgreSQL 的 auto-analyze 的过高频率 → 调整 autovacuum 参数降低 I/O
  - n8n 企业版功能 → 如果你不需要 RBAC，不要花 $20+/月

✅ 应该开启的核心功能:
  - PostgreSQL WAL 归档 → 备份的生命线
  - n8n healthcheck → 确保容器状态可监控
  - 核心工作流的 Error Workflow → 失败时自动降级
```

### 3.2 不用的容器不要跑

这是一个极其简单但极其容易被违背的原则。

```yaml
# docker-compose.yml 中的无效容器检查

# ❌ 反例：容器的"餐馆菜单"设计
services:
  elasticsearch:   # 3GB+ — 日请求量 2000 需要 ES？不需要！
    image: elasticsearch:8.x   # docker-compose pull 6 次就 5GB 下载量

  kibana:          # 1GB+ — ES 有了，没 Kibana 你怎么看？
    image: kibana:8.x           # 配套的又 1GB

  grafana:         # 500MB — 你确实需要图表吗？
    image: grafana/grafana      # 但 n8n 自带监控页面

  prometheus:      # 500MB — 监控是基础设施？
    image: prom/prometheus      # 是的，但 2C4G 时值得吗？

  redis-commander: # 100MB — 可视化 Redis 管理器
    image: rediscommander/redis-commander  # 你真的需要可视化地看 Redis 吗？

# ✅ 正例：最小服务集
services:
  n8n:             # 核心 - 工作流引擎
  postgres:        # 核心 - 数据库
  redis:           # 辅助 - 队列 + 缓存
  nginx:           # 入口 - 反向代理
  auth-server:     # 辅助 - 认证授权
  ai-gateway:      # 辅助 - AI API 网关

# 以上 6 个服务，就是全部。不需要更多。
```

**每多一个容器，你的运维债务就增加一分**：

```
容器数量的运维成本公式：

运行成本 = Σ(部署时间 + 调试时间 + 学习时间 + 安全更新时间 + 配置审查时间)

3 个容器:  约 10 小时 / 月
6 个容器:  约 20 小时 / 月
10 个容器: 约 50 小时 / 月
20 个容器: 约 200 小时 / 月（一人月）

结论：
  每多加一个不必要的容器，就是对你个人时间的清晰量化消耗
```

---

## 4. 自恢复设计

### 4.1 docker-compose 的自恢复三件套

**restart: always + healthcheck + 外部监督**是自恢复设计的三个支柱。

```yaml
versions: "3.8"
services:
  n8n:
    image: n8nio/n8n:latest
    restart: always
    healthcheck:
      test: ["CMD", "wget", "--spider", "http://localhost:5678/healthz"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    stop_grace_period: 30s  # 给 n8n 30 秒完成正在执行的工作流

  postgres:
    image: postgres:16-alpine
    restart: always
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U n8n_user -d n8n"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 60s  # PG 启动较慢，给 60 秒

  redis:
    image: redis:7-alpine
    restart: always
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 30s
      timeout: 5s
      retries: 3

  ai-gateway:
    build: ./ai-gateway
    restart: always
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    depends_on:
      postgres:
        condition: service_healthy
```

### 4.2 healthcheck 的设计哲学

**healthcheck 不是"保你不死"——它是"确认你死了然后让你重启"**。

很多人在 healthcheck 上犯的错误：

```yaml
# ❌ 错误 1: healthcheck 太频繁
healthcheck:
  test: ["CMD", "curl", "http://localhost:5678/healthz"]
  interval: 5s    # 每 5 秒检查一次 → 消耗资源并产生大量日志
  timeout: 3s
  retries: 3       # 15 秒无响应就触发重启 → 误杀频繁

# ✅ 正确做法
healthcheck:
  interval: 30s    # 30 秒一次足够了
  timeout: 10s
  retries: 3       # 连续失败 3 次才重启，即 30 + (30+10)*3 ≈ 150 秒
  start_period: 40s  # 启动前 40 秒不检查

# ❌ 错误 2: healthcheck 没有区分 liveness 和 readiness
# K8s 原生支持区分这两种探针，docker-compose 不支持，但可以在应用层模拟：
#
# liveness: "服务本身是否存活"
# readiness: "服务是否可以接受请求"
#
# 对于 n8n：liveness 检查 /healthz，readiness 需要等数据库就绪

# ❌ 错误 3: healthcheck 命令本身有副作用
# 例如检查 PG 时用 SELECT 1 FROM large_table 会消耗资源
# 应该用 pg_isready（轻量级检查）
```

### 4.3 外部监督：systemd 兜底

当 docker 本身挂了怎么办？这时候需要 systemd 兜底：

```ini
# /etc/systemd/system/ai-cluster.service
[Unit]
Description=AI Cluster Auto Recovery
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/local/bin/docker-compose -f /opt/ai-cluster/docker-compose.yml up -d
ExecStop=/usr/local/bin/docker-compose -f /opt/ai-cluster/docker-compose.yml down
ExecReload=/usr/local/bin/docker-compose -f /opt/ai-cluster/docker-compose.yml restart

[Install]
WantedBy=multi-user.target
```

```ini
# /etc/systemd/system/ai-cluster-watchdog.service
# 每 30 秒检查一次，如果 ai-cluster 没运行就启动
[Unit]
Description=AI Cluster Watchdog
After=ai-cluster.service

[Service]
Type=simple
ExecStart=/usr/local/bin/watchdog.sh
Restart=always
RestartSec=10s

[Install]
WantedBy=multi-user.target
```

```bash
#!/bin/bash
# /usr/local/bin/watchdog.sh
# 守护进程：自动恢复 docker-compose 服务

while true; do
  # 检查 docker daemon 是否运行
  if ! docker info > /dev/null 2>&1; then
    echo "Docker daemon is down, attempting restart..."
    systemctl restart docker
    sleep 10
    continue
  fi

  # 检查关键容器是否运行
  for service in n8n postgres auth-server ai-gateway; do
    if ! docker ps --filter "name=${service}" --filter "status=running" --format "{{.Names}}" | grep -q "${service}"; then
      echo "${service} is not running, attempting restart..."
      docker-compose -f /opt/ai-cluster/docker-compose.yml up -d ${service}
    fi
  done

  sleep 30
done
```

### 4.4 自恢复的测试

自恢复设计不是写了就完事的——它需要在 CI/CD 中测试：

```bash
#!/bin/bash
# test-self-recovery.sh
# 验证自恢复机制的测试套件

echo "=== Test 1: 模拟 n8n 崩溃 ==="
docker kill n8n
sleep 60  # 给自恢复时间
if docker ps --filter "name=n8n" --filter "status=running" --format "{{.Names}}" | grep -q "n8n"; then
    echo "✅ n8n 自恢复成功"
else
    echo "❌ n8n 自恢复失败"
    exit 1
fi

echo "=== Test 2: 模拟 PostgreSQL 崩溃 ==="
docker kill postgres
sleep 90
if docker ps --filter "name=postgres" --filter "status=running" --format "{{.Names}}" | grep -q "postgres"; then
    echo "✅ PostgreSQL 自恢复成功"
else
    echo "❌ PostgreSQL 自恢复失败"
    exit 1
fi

echo "=== Test 3: 模拟全部服务崩溃 ==="
docker-compose -f /opt/ai-cluster/docker-compose.yml down
sleep 120
if docker ps --format "{{.Names}}" | grep -q "n8n"; then
    echo "✅ 全系统自恢复成功"
else
    echo "❌ 全系统自恢复失败"
    exit 1
fi

echo "=== ALL TESTS PASSED ==="
```

---

> **下篇**：[03-Reimplementation-Guide/01-rebuild-roadmap.md](../03-Reimplementation-Guide/01-rebuild-roadmap.md) — 自研重构路线图
