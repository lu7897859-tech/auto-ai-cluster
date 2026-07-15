# Form-A 企业版生产上线检查清单

> **文档版本**: v1.0 | **更新日期**: 2026-07-15

---

## 一、概述

本检查清单用于确保 Form-A 企业版在生产环境上线前满足安全、监控、备份、日志和 SLA 要求。以下所有检查项均针对 **Kubernetes 集群 + form-a-system/form-a-data 命名空间**。

---

## 二、安全（Security）

### 2.1 TLS/SSL 证书

| # | 检查项 | 状态 | 备注 |
|---|--------|------|------|
| 1 | Ingress 配置了有效的 TLS 证书（非自签名） | ☐ | 推荐 cert-manager + Let's Encrypt |
| 2 | 证书即将到期有自动续期机制 | ☐ | cert-manager ClusterIssuer |
| 3 | 内部服务间通信启用 mTLS | ☐ | 可选，推荐 Service Mesh |
| 4 | 数据库连接启用 TLS | ☐ | Patroni 端开启 SSL 模式 |
| 5 | 所有外部 API 域名配置了 HTTPS 重定向 | ☐ | nginx-ingress annotation |

```yaml
# Ingress TLS 配置示例
ingress:
  annotations:
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    nginx.ingress.kubernetes.io/force-ssl-redirect: "true"
  tls:
    enabled: true
    secretName: form-a-tls
```

### 2.2 网络策略（NetworkPolicy）

| # | 检查项 | 状态 | 备注 |
|---|--------|------|------|
| 1 | 默认 deny-all 入站流量 | ☐ | 防止未授权访问 |
| 2 | 仅放行必要的入站端口和来源 | ☐ | 参照 architecture-overview.md |
| 3 | 数据库命名空间仅 system 命名空间可访问 | ☐ | 5432/2379/6379 端口限制 |
| 4 | 禁止 Pod 直接出站互联网（如有合规要求） | ☐ | egress 策略 |

```yaml
# 基线 NetworkPolicy
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-all
  namespace: form-a-data
spec:
  podSelector: {}
  policyTypes:
  - Ingress
  - Egress
```

### 2.3 密钥管理（Secrets）

| # | 检查项 | 状态 | 备注 |
|---|--------|------|------|
| 1 | 数据库密码使用 K8s Secret 管理，非 ConfigMap | ☐ | |
| 2 | License 文件存储为 K8s Secret | ☐ | |
| 3 | API Key 和 OAuth2 Client Secret 使用 K8s Secret | ☐ | |
| 4 | 使用 Sealed Secrets 或 External Secrets 加密 | ☐ | 推荐对接 Vault / AWS Secrets Manager |
| 5 | Secret 未硬编码在 YAML/values 文件中 | ☐ | 使用 !reference 或 Helm values 模板 |
| 6 | Secret 审计：定期轮换数据库和 API 密钥 | ☐ | |

### 2.4 RBAC 权限控制

| # | 检查项 | 状态 | 备注 |
|---|--------|------|------|
| 1 | 服务账户使用最小权限原则 | ☐ | 每个组件独立的 ServiceAccount |
| 2 | 用户 RBAC 按角色隔离（admin/editor/viewer） | ☐ | |
| 3 | 禁止容器以 root 运行 | ☐ | `runAsNonRoot: true` |
| 4 | PodSecurityPolicy / Pod Security Admission 已配置 | ☐ | Kubernetes ≥ 1.23 推荐 PSA |

---

## 三、监控（Monitoring）

### 3.1 Prometheus 集成

| # | 检查项 | 状态 | 备注 |
|---|--------|------|------|
| 1 | Prometheus Operator / kube-prometheus-stack 已部署 | ☐ | |
| 2 | 企业版组件已暴露 Prometheus 指标端点 | ☐ | auth-server :9100, n8n-worker :9100 |
| 3 | 采集配置已入库（ServiceMonitor / PodMonitor） | ☐ | |
| 4 | 关键告警规则已配置并启用 | ☐ | 见下方告警规则表 |

```yaml
# ServiceMonitor 示例
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: form-a-monitor
  namespace: form-a-system
spec:
  selector:
    matchLabels:
      app.kubernetes.io/component: n8n-worker
  endpoints:
  - port: metrics
    interval: 15s
```

### 3.2 Grafana 仪表盘

| # | 检查项 | 状态 | 备注 |
|---|--------|------|------|
| 1 | Grafana 已部署并配置数据源（Prometheus + Loki） | ☐ | |
| 2 | 导入企业版默认仪表盘（Form-A Overview） | ☐ | 安装包内置 dashboard JSON |
| 3 | 配置关键面板：工作流执行数/延迟/错误率 | ☐ | |
| 4 | 配置告警通知渠道（钉钉/企微/Slack/邮件） | ☐ | |

### 3.3 关键告警规则

| 告警名称 | 指标 | 阈值 | 严重度 |
|---------|------|------|--------|
| Pod CrashLoopBackOff | `kube_pod_status_phase{phase="pending"}` | > 0 for 5min | critical |
| PG 集群异常 | `patroni_cluster_unlocked` | = 1 | critical |
| 数据库复制延迟 | `pg_replication_lag` | > 100MB | warning |
| 磁盘使用率 > 80% | `node_filesystem_avail_bytes` | < 20% | warning |
| n8n-worker 错误率 | `n8n_workflow_execution_error_total` | > 5% for 5min | critical |
| 证书即将到期 | `certmanager_certificate_expiration_timestamp_seconds` | < 30 days | warning |

---

## 四、备份（Backup）

### 4.1 备份策略

| # | 检查项 | 状态 | 备注 |
|---|--------|------|------|
| 1 | PostgreSQL 定时全量备份（pg_dump / pgBackRest） | ☐ | 建议每日凌晨 |
| 2 | WAL 归档已启用（支持时间点恢复 PITR） | ☐ | |
| 3 | 备份文件存储在集群外部（MinIO/S3/NFS） | ☐ | 集群故障也能恢复 |
| 4 | 备份文件加密（服务端加密 / GPG） | ☐ | |
| 5 | K8s 资源清单定期导出备份 | ☐ | kubectl get all --all-namespaces -o yaml |
| 6 | License 文件外部安全存储（离线备份） | ☐ | 丢失需联系销售重新签发 |
| 7 | MinIO 工作流文件定期备份 | ☐ | |

```yaml
# CronJob 备份配置（参考 postgres-high-availability.md）
backup:
  enabled: true
  schedule: "0 2 * * *"          # 每天凌晨 2:00
  retention:
    full: 7                      # 全量备份保留 7 天
    wal: 7                       # WAL 保留 7 天
  storage:
    type: "s3"                   # s3 / minio / nfs
    bucket: "form-a-backup"
    endpoint: "s3.amazonaws.com"
  encryption:
    enabled: true
    keySecretName: "backup-encryption-key"
```

### 4.2 备份验证

| # | 检查项 | 状态 | 备注 |
|---|--------|------|------|
| 1 | 每周执行一次恢复演练 | ☐ | 验证备份可恢复 |
| 2 | 恢复演练记录（RTO/RPO 实测值） | ☐ | 预期 RTO < 30min, RPO < 1min |
| 3 | 备份失败告警已配置 | ☐ | CronJob 失败触发 |

---

## 五、日志（Logging）

### 5.1 集中日志方案

| # | 检查项 | 状态 | 备注 |
|---|--------|------|------|
| 1 | Loki 或 Elasticsearch 已部署 | ☐ | 推荐 Loki（轻量） |
| 2 | Promtail / Fluentd / Filebeat 日志采集 DaemonSet | ☐ | 采集 `/var/log/containers/*.log` |
| 3 | 日志保留策略已配置 | ☐ | 建议 30 天（合规场景 180 天） |
| 4 | 关键日志已打标签便于检索 | ☐ | namespace / pod / component 标签 |
| 5 | 审计日志单独存储（不可篡改） | ☐ | 合规审计需求 |

```yaml
# Loki 日志保留配置（示例）
loki:
  config:
    table_manager:
      retention_deletes_enabled: true
      retention_period: 720h   # 30 天
```

### 5.2 日志关键字段

所有企业版组件均输出结构化 JSON 日志，便于集中采集和检索：

```json
{
  "timestamp": "2026-07-15T16:30:00.123Z",
  "level": "error",
  "component": "n8n-worker",
  "workflow_id": "wf_abc123",
  "execution_id": "exec_xyz789",
  "message": "Failed to execute AI agent step",
  "error": {
    "type": "LLMTimeoutError",
    "detail": "provider=openai, model=gpt-4, timeout=120s"
  }
}
```

### 5.3 日志查询示例（Loki LogQL）

```logql
# 查询某个工作流的执行日志
{namespace="form-a-system", component="n8n-worker"} |= `wf_abc123`

# 查询过去 1 小时内的错误日志
{namespace="form-a-system"} |= `"level":"error"` |= `timestamp > "2026-07-15T15:00:00Z"`

# 查询 API 网关的慢请求
{namespace="form-a-system", component="ai-gateway"} |= `"latency_ms":` | pattern `"latency_ms":<latency>` | latency > 5000
```

---

## 六、企业版 SLA 承诺

Form-A 企业版提供 **7×24 小时技术支持**，响应时间如下：

| 严重级别 | 定义 | 响应时间 | 目标恢复时间 |
|---------|------|---------|-------------|
| **P0** — 严重 | 系统完全不可用，所有用户无法访问 | ≤ 15 分钟 | ≤ 2 小时 |
| **P1** — 高 | 核心功能严重受损，部分用户不可用 | ≤ 30 分钟 | ≤ 4 小时 |
| **P2** — 中 | 非核心功能故障，有可用替代方案 | ≤ 2 小时 | ≤ 24 小时 |
| **P3** — 低 | 咨询类、功能建议、非关键缺陷 | ≤ 8 小时 | 下个版本修复 |

### SLA 支持渠道

| 渠道 | 联系方式 | 工作时间 |
|------|---------|---------|
| 紧急电话 | +86 400-XXX-XXXX | 7×24 |
| 在线工单 | https://support.form-a.io | 7×24 |
| 企业微信群 | 交付时建立的专属群 | 7×24 |
| 邮件 | support@form-a.io | 工作时间 1h 内响应 |

---

## 七、上线最终检查清单

```markdown
### ☐ 部署前
  1. ☐ K8s 集群 ≥ 3 节点，所有节点 Ready
  2. ☐ 集群资源充足（kubectl top nodes 无瓶颈）
  3. ☐ StorageClass 已部署并设置为默认
  4. ☐ nginx-ingress 已部署
  5. ☐ cert-manager 已部署（自动 TLS）
  6. ☐ Prometheus + Grafana 已部署（包含关键告警）
  7. ☐ Loki + Promtail 已部署（日志采集）
  8. ☐ License 文件已就绪并创建为 K8s Secret
  9. ☐ 域名 DNS 已配置指向集群 Ingress IP

### ☐ 部署中
  10. ☐ 使用 deploy-enterprise.sh 完成安装
  11. ☐ 所有 Pod 正常 Running（kubectl get pods -A | grep -v Running 无输出）
  12. ☐ 数据库 Patroni 集群状态正常（3 节点 Ready）
  13. ☐ Ingress 可通过域名正常访问管理控制台
  14. ☐ 默认管理员账号可登录
  15. ☐ License 验证通过（管理页面 → 系统设置 → 授权信息显示正常）

### ☐ 部署后
  16. ☐ 创建测试工作流并成功运行
  17. ☐ 验证备份 CronJob 已正常运行
  18. ☐ 验证告警通知渠道可用
  19. ☐ 修改默认管理员密码
  20. ☐ TLS 证书 HTTPS 正常
  21. ☐ 网络安全策略（NetworkPolicy）生效
  22. ☐ 保存部署日志和初始配置快照
  23. ☐ 通知运维团队完成上线
```

---

## 八、附录：推荐组件版本

| 组件 | 推荐版本 | 说明 |
|------|---------|------|
| Kubernetes | 1.30+ | EKS / AKS / 自建 |
| nginx-ingress | 1.10+ | 社区版 / 企业版均可 |
| cert-manager | 1.14+ | 自动 TLS |
| Prometheus | 2.50+ | kube-prometheus-stack |
| Grafana | 10.4+ | 含告警模块 |
| Loki | 3.0+ | 日志聚合 |
| Longhorn（可选） | 1.6+ | 分布式存储 |
| Istio（可选） | 1.21+ | Service Mesh |

---

> 相关文档：`README.md` · `deploy-enterprise.sh` · `postgres-high-availability.md`
