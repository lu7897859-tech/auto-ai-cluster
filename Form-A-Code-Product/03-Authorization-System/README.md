# Form-A 授权控制系统 (Authorization System)

## 概述

Form-A 授权系统是产品变现的核心基础设施，提供 License 签发、验签、激活、续期、分销追踪的全链路能力。

### 核心能力

| 能力 | 说明 |
|------|------|
| 🛡️ **RSA 签名保护** | RSA-2048 + SHA-256 非对称签名，私钥签名公钥验证 |
| 💻 **机器指纹绑定** | CPU序列号 + MAC地址 + 主板序列号 + 磁盘序列号，多指纹容错比对 |
| 🌐 **联网+离线双模** | 每7天联网校验，离线缓存最多7天 |
| 📊 **三版授权** | 社区版（免费限制）、企业版（无限制）、分销代理版（含分成） |
| 📈 **分销追踪** | License 嵌入分销商ID，激活自动上报，分成报表 |
| 🔒 **安全审计** | 所有授权变更全量审计日志 |

## 快速开始

### 本地运行

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 启动服务
python auth-server.py
```

服务默认监听 `http://localhost:5000`，首次运行会自动生成 RSA 密钥对和 SQLite 数据库。

### Docker 部署

```bash
# 构建镜像
docker build -t form-a-auth-server .

# 运行容器
docker run -d \
  --name auth-server \
  -p 5000:5000 \
  -v auth-data:/app/data \
  form-a-auth-server
```

## API 接口

### 授权验证

| 方法 | 路径 | 说明 | 认证方式 |
|------|------|------|---------|
| `GET` | `/health` | 健康检查 | 无 |
| `POST` | `/api/license/validate` | 验证 License 有效性 | `X-License-Token` |
| `POST` | `/api/license/activate` | 首次激活（绑定指纹） | 请求体传 License |
| `GET` | `/api/license/status` | 查询授权状态 | `X-License-Token` |
| `GET` | `/api/license/generate-endpoint` | 获取公钥 | 无 |
| `POST` | `/api/license/renew` | 续期 | `X-Admin-Key` |

### 管理员接口

| 方法 | 路径 | 说明 | 认证方式 |
|------|------|------|---------|
| `GET` | `/api/admin/licenses` | 查询所有 License | `X-Admin-Key` |
| `POST` | `/api/admin/generate` | 生成新 License | `X-Admin-Key` |
| `POST` | `/api/admin/revoke` | 吊销 License | `X-Admin-Key` |
| `GET` | `/api/admin/audit-log` | 查询审计日志 | `X-Admin-Key` |

### 获取管理员密钥

启动时日志会输出 Admin Key，或自行计算：

```python
import hashlib
# 其中 SECRET_KEY 在启动日志中
admin_key = hashlib.sha256((SECRET_KEY + "admin").encode()).hexdigest()[:32]
```

## CLI 快速测试

```bash
# 1. 生成企业版 License（管理员）
ADMIN_KEY=$(python3 -c "import hashlib; print(hashlib.sha256(b'$(python3 -c 'import hashlib; print(hashlib.sha256(os.urandom(64)).hexdigest())' 2>/dev/null || echo "demo")admin').hexdigest()[:32])" 2>/dev/null)
# 实际从服务端启动日志获取

curl -s -X POST http://localhost:5000/api/admin/generate \
  -H "Content-Type: application/json" \
  -H "X-Admin-Key: YOUR_ADMIN_KEY" \
  -d '{"edition":"enterprise","expires_in_days":365,"max_nodes":5}' | python3 -m json.tool

# 2. 激活 License
curl -s -X POST http://localhost:5000/api/license/activate \
  -H "Content-Type: application/json" \
  -d '{"license":"BASE64_LICENSE_TOKEN"}' | python3 -m json.tool

# 3. 验证 License
curl -s -X POST http://localhost:5000/api/license/validate \
  -H "X-License-Token: BASE64_LICENSE_TOKEN" | python3 -m json.tool
```

## 版本功能边界

```python
EDITION_FEATURES = {
    "community": {
        "max_workflows": 10, "max_users": 5,
        "ai_calls_per_day": 100, "data_retention_days": 30,
        "watermark": True,
    },
    "enterprise": {
        "max_workflows": -1, "max_users": -1,  # -1 = 无限制
        "ai_calls_per_day": -1, "data_retention_days": -1,
        "watermark": False,
    },
    "distribution": {
        "max_workflows": -1, "max_users": -1,
        "ai_calls_per_day": -1, "data_retention_days": -1,
        "watermark": False,
    },
}
```

## 防盗版架构

```
┌───────────── RSA-2048 签名 ─────────────┐
│                                          │
│  服务端私钥 ──签名──→ License 文件        │
│  客户端公钥 ──验签──→ 验证合法性          │
│                                          │
│  机器指纹绑定：CPU + MAC + 主板 + 磁盘     │
│  4中匹配3即通过，防硬件小变动误锁          │
│                                          │
│  离线缓存7天 + 7天一联网校验              │
│  断网超过7天 → 降级社区版或停用           │
└──────────────────────────────────────────┘
```

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DB_PATH` | `/app/data/auth.db` | SQLite 数据库路径 |
| `PRIVATE_KEY_PATH` | `/app/data/private.pem` | RSA 私钥 PEM 路径 |
| `PUBLIC_KEY_PATH` | `/app/data/public.pem` | RSA 公钥 PEM 路径 |
| `SECRET_KEY` | 自动生成 | Flask Secret Key |
| `HOST` | `0.0.0.0` | 监听地址 |
| `PORT` | `5000` | 监听端口 |

## 文件结构

```
03-Authorization-System/
├── LICENSE_ARCHITECTURE.md   # 授权系统架构说明书
├── auth-server.py            # Flask 授权验证服务（完整可运行）
├── requirements.txt          # Python 依赖
├── Dockerfile                # Docker 构建文件
├── entrypoint.sh             # Docker 启动入口脚本
└── README.md                 # 本说明文件
```

## 生产部署建议

- 使用 **HTTPS** 加密（反向代理 Nginx/Caddy）
- 数据库使用 **MySQL/PostgreSQL**（替换 SQLite）
- 添加 **Rate Limiting**（建议 10次/分钟/IP）
- RSA 私钥定期轮换（建议 12 个月）
- 使用 **gunicorn + gevent** 作为 WSGI 服务器
- 部署监控和告警
