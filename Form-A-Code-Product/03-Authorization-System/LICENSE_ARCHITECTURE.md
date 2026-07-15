# Form-A 授权系统架构说明书

## 1. 授权模型总览

授权系统是 Form-A 产品变现的核心基础设施，采用 **三版本多层级授权模型**，兼顾免费引流、企业盈利、渠道分销三大目标。

### 1.1 版本矩阵

| 特性 | 社区版 (Community) | 企业版 (Enterprise) | 分销代理版 (Distribution) |
|------|-------------------|--------------------|--------------------------|
| **定价** | 免费 | 按节点年费 | 按分销商标记 + 自动分成 |
| **工作流数量** | ≤10 | 无限制 | 无限制 |
| **用户数** | ≤5人 | 无限制 | 按客户需求 |
| **AI 调用配额** | 100次/天 | 不限制 | 不限制 |
| **数据保留期** | 30天 | 永久 | 永久 |
| **水印** | ✅ 输出带水印 | ❌ 无水印 | ❌ 无水印 |
| **分销拆分比例** | 无 | 无 | 30% 自动拆给分销商 |
| **机器绑定** | 单一设备 | 多节点浮动许可 | 多节点浮动许可 |
| **技术支持** | 社区论坛 | 专属技术支持 | 优先技术支持 |

### 1.2 版本选择逻辑

```
用户请求激活
  ├─ 无授权文件        → 自动赋予社区版（30天试用/水印/限制）
  ├─ 企业版 License    → 全功能无限制（按节点数收费）
  └─ 分销版 License    → 全功能 + 分销商标记（收益自动拆分）
```

## 2. License 生成与分发流程

### 2.1 完整生命周期

```
┌─────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  管理后台     │    │  License管理   │    │  RSA签名服务   │    │  分销商/客户   │
│  (自研)       │───→│  (auth-server)│───→│  (auth-server)│───→│  (浏览器下载) │
└─────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
                         │                                         │
                         │ 到期/续费                               │ 部署时
                         ▼                                         ▼
                   ┌──────────────┐                     ┌──────────────────┐
                   │  验证校验     │                     │  本地客户端验证    │
                   │  (7天周期)   │                     │  (离线缓存7天)    │
                   └──────────────┘                     └──────────────────┘
```

### 2.2 License 文件格式

License 文件为 **Base64 编码的 JSON + RSA 签名**，非对称加密确保防篡改。

```json
{
  "version": "1.0",
  "license_id": "LIC-2026-XXXX-XXXX",
  "product": "form-a",
  "edition": "enterprise",
  "issued_at": "2026-07-15T00:00:00Z",
  "expires_at": "2027-07-15T00:00:00Z",
  "max_nodes": 5,
  "features": {
    "max_workflows": -1,
    "max_users": -1,
    "ai_calls_per_day": -1,
    "data_retention_days": -1,
    "watermark": false,
    "distribution_enabled": false
  },
  "machine_bindings": {
    "required": true,
    "max_bindings": 1,
    "current_bindings": []
  },
  "distributor": {
    "id": null,
    "name": null,
    "split_ratio": 0.0
  },
  "signature": "BASE64_RSA_SIGNATURE"
}
```

**重要字段说明：**
- `features.* = -1` 表示无限制
- `distributor` 仅在分销代理版非空
- `signature` 由服务端私钥签名，客户端用公钥验证

## 3. 验证机制

### 3.1 双重验证策略

| 验证类型 | 时机 | 方式 | 结果 |
|---------|------|------|------|
| **本地签名验证** | 每次启动/功能调用 | RSA 公钥验证 license 签名 | 签名无效→拒绝服务 |
| **联网校验** | 每 7 天 + 启动时 | POST /api/license/validate | 许可状态同步 |
| **离线缓存** | 断网时 | 本地存储最长 7 天 | 7 天内正常使用 |

### 3.2 验证流程

```
┌─────────────────────────────────────────────────────┐
│  客户端启动                                          │
│                                                     │
│  1. 读取本地 license.lic 文件                        │
│  2. RSA公钥验签 → 失败则停止                         │
│  3. 检查过期时间 → 已过期则停用                       │
│  4. 检查机器指纹 → 不匹配则停用                       │
│  5. 检查上次联网校验时间                             │
│     │                                                │
│     ├── 距离上次校验 < 7天 → 使用本地缓存             │
│     └── 距离上次校验 ≥ 7天 或 网络可用               │
│           → 发起联网校验                             │
│              ├── 成功 → 更新本地缓存时间              │
│              └── 失败 → 使用本地缓存（最多7天）       │
│                                                        │
│  6. 授权通过 → 加载对应版本功能边界                    │
└─────────────────────────────────────────────────────┘
```

### 3.3 版本功能边界在客户端的应用

每次验证通过后，客户端应加载对应版本的 Feature Flag：

```python
EDITION_FEATURES = {
    "community": {
        "max_workflows": 10,
        "max_users": 5,
        "ai_calls_per_day": 100,
        "data_retention_days": 30,
        "watermark": True,
        "export_disabled": False,
    },
    "enterprise": {
        "max_workflows": -1,      # 无限制
        "max_users": -1,
        "ai_calls_per_day": -1,
        "data_retention_days": -1,
        "watermark": False,
        "export_disabled": False,
    },
    "distribution": {
        "max_workflows": -1,
        "max_users": -1,
        "ai_calls_per_day": -1,
        "data_retention_days": -1,
        "watermark": False,
        "export_disabled": False,
    },
}
```

## 4. 防盗版机制

### 4.1 RSA 非对称签名

```text
服务端私钥签名 license → 客户端公钥验签
私钥：服务端保存，绝不泄露
公钥：嵌入客户端二进制
算法：RSA-2048 + SHA-256
```

### 4.2 机器指纹绑定

验证时收集以下硬件指纹信息，与 license 绑定：

| 指纹字段 | 获取方式 | 级别 |
|---------|---------|------|
| CPU 序列号 | `wmic cpu get processorid` (Windows) / `dmidecode` (Linux) | 高 |
| MAC 地址 | 主要网卡的物理地址 | 中 |
| 主板序列号 | `wmic baseboard get serialnumber` | 中 |
| 磁盘序列号 | `wmic diskdrive get serialnumber` | 中 |

**指纹判定策略：** 4 个指纹中至少匹配 3 个即为同一机器，避免因硬件变更导致的误锁定。

### 4.3 防篡改加固

| 攻击面 | 防护措施 |
|-------|---------|
| 伪造 License | RSA 签名验证，无私钥无法伪造 |
| 盗用 License | 机器指纹绑定，换机失效 |
| 逆向工程绕过 | 公钥做混淆/分段存储 + 完整性校验 |
| 日期回拨 | 联网校验 + 本地不可逆的时间戳记录 |
| 暴力破解验证 | 验证失败 5 次锁定 30 分钟 |

## 5. 分销追踪

### 5.1 License 分销商嵌入

分销代理版 License 会在 license 中嵌入分销商信息：

```json
"distributor": {
    "id": "DIST-00123",
    "name": "上海某某科技",
    "split_ratio": 0.30
}
```

### 5.2 激活上报流程

```
客户激活分销版 License
  → auth-server 记录：license_id + 分销商ID + 客户机器指纹 + 激活时间
  → 分销报表定时生成（每月）
  → 自动计算分销商应得分成
```

### 5.3 分销报表字段

| 字段 | 说明 |
|------|------|
| 分销商ID | DIST-XXXXX |
| 分销商名称 | 注册时填写 |
| License ID | 分配的许可编号 |
| 客户名 | 激活时注册 |
| 激活时间 | 首次激活时间戳 |
| 到期时间 | License 过期时间 |
| 续费次数 | 续期操作次数 |
| 分成金额 | 按比例自动计算 |

## 6. 部署架构

### 6.1 最小部署

```
┌─────────────┐      ┌────────────────┐
│  MySQL/SQLite │────→│  auth-server    │
│  (持久化)     │      │  Flask REST API │
└─────────────┘      └───────┬────────┘
                             │
                      ┌──────▼──────┐
                      │  RSA Key Pair │
                      │  (服务端私钥)  │
                      └─────────────┘
```

### 6.2 Docker 部署

```bash
docker build -t form-a-auth-server .
docker run -d \
  --name auth-server \
  -p 5000:5000 \
  -v /data/auth:/app/data \
  -e DB_PATH=/app/data/auth.db \
  -e PRIVATE_KEY_PATH=/app/data/private.pem \
  -e PUBLIC_KEY_PATH=/app/data/public.pem \
  form-a-auth-server
```

### 6.3 环境变量配置

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DB_PATH` | SQLite 数据库路径 | `/app/data/auth.db` |
| `PRIVATE_KEY_PATH` | RSA 私钥路径 | `/app/data/private.pem` |
| `PUBLIC_KEY_PATH` | RSA 公钥路径 | `/app/data/public.pem` |
| `SECRET_KEY` | Flask Secret Key | 自动生成 |
| `HOST` | 监听地址 | `0.0.0.0` |
| `PORT` | 监听端口 | `5000` |

## 7. API 接口总览

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|------|
| POST | `/api/license/validate` | 验证 License 有效性 | 机器指纹 |
| POST | `/api/license/activate` | 首次激活（绑定机器指纹） | 机器指纹 |
| GET  | `/api/license/status` | 查询当前授权状态 | 机器指纹 |
| POST | `/api/license/renew` | 续期/更新 License | Admin Key |
| GET  | `/api/admin/licenses` | 管理员查看所有 License | Admin Key |

## 8. 安全与合规

- **通信加密**：所有 API 通过 HTTPS 传输（生产环境强制）
- **密钥轮换**：RSA 密钥对建议每 12 个月轮换一次
- **数据合规**：仅存储必要授权数据，不采集用户业务数据
- **审计日志**：所有授权变更操作记录审计日志
- **速率限制**：验证 API 限制 10 次/分钟/IP

---

*文档版本：v1.0 | 最后更新：2026-07-15 | 所属项目：Form-A 授权控制系统*
