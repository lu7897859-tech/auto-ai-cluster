# Form-A Enterprise Helm Chart

> **Chart 名称**: ai-cluster-enterprise | **Chart 版本**: v1.0.0 | **App 版本**: 2.5.0

---

## 一、Chart 结构总览

```
ai-cluster-enterprise/
├── Chart.yaml                    # Chart 元信息
├── values.yaml                   # 全局参数配置（主入口）
├── values-example.yaml           # 生产环境样例配置
├── charts/                       # 依赖 subchart
│   ├── auth-server/              # 授权认证服务
│   │   ├── Chart.yaml
│   │   ├── values.yaml
│   │   └── templates/
│   │       ├── deployment.yaml
│   │       ├── service.yaml
│   │       ├── configmap.yaml
│   │       └── _helpers.tpl
│   ├── n8n-worker/               # 工作流引擎
│   │   ├── Chart.yaml
│   │   ├── values.yaml
│   │   └── templates/
│   │       ├── deployment.yaml
│   │       ├── service.yaml
│   │       ├── hpa.yaml
│   │       └── pdb.yaml
│   ├── ai-gateway/               # AI API 网关
│   │   ├── Chart.yaml
│   │   ├── values.yaml
│   │   └── templates/
│   │       ├── deployment.yaml
│   │       ├── service.yaml
│   │       └── configmap.yaml
│   ├── web-ui/                   # 管理控制台前端
│   │   ├── Chart.yaml
│   │   ├── values.yaml
│   │   └── templates/
│   │       ├── deployment.yaml
│   │       ├── service.yaml
│   │       └── ingress.yaml
│   ├── postgres-patroni/         # PostgreSQL 高可用
│   │   ├── Chart.yaml
│   │   ├── values.yaml
│   │   └── templates/
│   │       ├── statefulset.yaml
│   │       ├── service.yaml
│   │       ├── configmap.yaml
│   │       ├── pdb.yaml
│   │       └── svc-headless.yaml
│   ├── redis-sentinel/           # Redis 集群
│   │   ├── Chart.yaml
│   │   ├── values.yaml
│   │   └── templates/
│   │       ├── statefulset.yaml
│   │       ├── service.yaml
│   │       └── configmap.yaml
│   └── minio-storage/            # 对象存储
│       ├── Chart.yaml
│       ├── values.yaml
│       └── templates/
│           ├── deployment.yaml
│           └── service.yaml
└── templates/
    ├── namespace.yaml            # 命名空间创建
    ├── ingress.yaml              # 统一 Ingress 配置
    ├── _helpers.tpl              # 全局模板辅助函数
    └── NOTES.txt                 # 安装后提示信息
```

---

## 二、Subchart 功能说明

| Subchart | 类型 | 说明 | 必选 | 默认副本 |
|----------|------|------|------|---------|
| `auth-server` | Deployment | License 校验 + LDAP/OAuth2 认证 | ✅ | 2 |
| `n8n-worker` | Deployment | 工作流引擎，可水平扩展 | ✅ | 2 |
| `ai-gateway` | Deployment | AI API 反向代理、熔断、限流 | ✅ | 2 |
| `web-ui` | Deployment | 管理控制台前端 | ✅ | 2 |
| `postgres-patroni` | StatefulSet | Patroni 高可用 PostgreSQL | ✅ | 3 |
| `redis-sentinel` | StatefulSet | 缓存 + 任务队列 | ✅ | 3 |
| `minio-storage` | Deployment | 文件/附件对象存储 | ✅ | 1 |

---

## 三、values.yaml 关键参数说明

```yaml
# ============================================================
# 全局配置
# ============================================================
global:
  imageRegistry: "registry.form-a.io/enterprise"
  imageTag: "2.5.0"
  imagePullPolicy: "IfNotPresent"
  licenseSecretName: "form-a-license"   # License Secret 名称

  # 域名配置
  domain: "form-a.example.com"

  # 存储类（需支持 ReadWriteOnce/RWM）
  storageClass: "standard"

# ============================================================
# auth-server：授权认证
# ============================================================
auth-server:
  enabled: true
  replicaCount: 2
  image:
    repository: "auth-server"
    tag: ""
  service:
    type: ClusterIP
    port: 8080

  # LDAP 集成（可选）
  ldap:
    enabled: false
    url: "ldap://ldap.example.com:389"
    baseDN: "dc=example,dc=com"
    adminDN: "cn=admin,dc=example,dc=com"

  # OAuth2 集成（可选）
  oauth2:
    enabled: false
    provider: "keycloak"    # keycloak / azure-ad / okta / custom
    clientId: ""
    issuerUrl: ""

  resources:
    requests:
      cpu: "500m"
      memory: "512Mi"
    limits:
      cpu: "1"
      memory: "1Gi"

# ============================================================
# n8n-worker：工作流引擎
# ============================================================
n8n-worker:
  enabled: true
  replicaCount: 2
  image:
    repository: "n8n-worker"
    tag: ""

  # 水平扩缩容（HPA）
  autoscaling:
    enabled: true
    minReplicas: 2
    maxReplicas: 10
    targetCPUUtilizationPercentage: 70

  resources:
    requests:
      cpu: "1"
      memory: "1Gi"
    limits:
      cpu: "2"
      memory: "2Gi"

# ============================================================
# ai-gateway：AI API 网关
# ============================================================
ai-gateway:
  enabled: true
  replicaCount: 2
  image:
    repository: "ai-gateway"
    tag: ""

  # 限流配置
  rateLimit:
    enabled: true
    requestsPerSecond: 100

  # 熔断配置
  circuitBreaker:
    enabled: true
    failureThreshold: 5
    recoveryTimeout: 30s

# ============================================================
# web-ui：管理控制台
# ============================================================
web-ui:
  enabled: true
  replicaCount: 2

# ============================================================
# postgres-patroni：PostgreSQL 高可用集群
# ============================================================
postgres-patroni:
  enabled: true
  replicaCount: 3           # 固定 3 节点
  image:
    repository: "patroni"
    tag: "3.0.0"

  patroni:
    etcd:
      hosts:
        - "etcd-0.etcd.form-a-data.svc.cluster.local:2379"
        - "etcd-1.etcd.form-a-data.svc.cluster.local:2379"
        - "etcd-2.etcd.form-a-data.svc.cluster.local:2379"
    scope: "form-a-pg-cluster"
    superuserPassword: ""    # 自动生成或从 Secret 读取

  persistence:
    size: "50Gi"
    storageClass: ""

# ============================================================
# redis-sentinel：缓存与队列
# ============================================================
redis-sentinel:
  enabled: true
  replicaCount: 3
  persistence:
    size: "10Gi"

# ============================================================
# minio-storage：对象存储
# ============================================================
minio-storage:
  enabled: true
  replicaCount: 1
  persistence:
    size: "100Gi"
  bucket:
    name: "form-a-workspace"

# ============================================================
# Ingress 配置
# ============================================================
ingress:
  enabled: true
  className: "nginx"
  annotations:
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
    nginx.ingress.kubernetes.io/proxy-body-size: "100m"
  tls:
    enabled: true
    secretName: "form-a-tls"

# ============================================================
# 全局资源限制
# ============================================================
globalResources:
  requests:
    cpu: "6"
    memory: "12Gi"
  limits:
    cpu: "12"
    memory: "24Gi"
```

---

## 四、安装命令

### 4.1 添加 Helm 仓库

```bash
helm repo add form-a https://helm.form-a.io/enterprise
helm repo update
```

### 4.2 准备自定义配置

```bash
# 复制样例配置
cp values-example.yaml form-a-values.yaml

# 编辑关键参数
# - global.domain: 替换为您的实际域名
# - global.licenseSecretName: License Secret 名称
# - postgres-patroni.patroni.superuserPassword: 数据库超管密码
# - ingress.tls.secretName: TLS 证书
```

### 4.3 部署企业版

```bash
# 标准安装（推荐）
helm install form-a-enterprise form-a/ai-cluster-enterprise \
  --namespace form-a-system \
  --create-namespace \
  --values form-a-values.yaml

# 带阿里云镜像加速（中国区用户）
helm install form-a-enterprise form-a/ai-cluster-enterprise \
  --namespace form-a-system \
  --create-namespace \
  --values form-a-values.yaml \
  --set global.imageRegistry=registry.cn-hangzhou.aliyuncs.com/form-a-enterprise

# 仅安装部分组件（如仅安装数据层）
helm install form-a-data form-a/ai-cluster-enterprise \
  --namespace form-a-data \
  --create-namespace \
  --values form-a-values.yaml \
  --set auth-server.enabled=false \
  --set n8n-worker.enabled=false \
  --set ai-gateway.enabled=false \
  --set web-ui.enabled=false
```

### 4.4 部署后验证

```bash
# 查看 Pod 状态
kubectl -n form-a-system get pods -o wide
kubectl -n form-a-data get pods -o wide

# 查看 Service
kubectl -n form-a-system get svc

# 查看 Ingress
kubectl -n form-a-system get ingress

# 查看 Helm Release
helm list -n form-a-system
```

### 4.5 升级

```bash
# 升级到新版本
helm upgrade form-a-enterprise form-a/ai-cluster-enterprise \
  --namespace form-a-system \
  --values form-a-values.yaml

# 回滚
helm rollback form-a-enterprise 1 -n form-a-system
```

---

## 五、卸载

```bash
# 卸载企业版（注意：PVC 中的数据需要手动清理）
helm uninstall form-a-enterprise -n form-a-system
helm uninstall form-a-data -n form-a-data
helm uninstall form-a-workflows -n form-a-workflows

# 清理 PVC（数据不可恢复！）
kubectl delete pvc -n form-a-data --all
kubectl delete pvc -n form-a-system --all
```

---

> 相关文档：[Helm 最佳实践](https://helm.sh/docs/chart_best_practices/) · [完整部署脚本](../deploy-enterprise.sh)
