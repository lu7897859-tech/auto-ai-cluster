# Form-A 产品总README

## 一句话

> **docker-compose一键部署的自主AI分析集群 — 社区版免费裂变，企业版授权收费。**

## 产品矩阵

```
Form-A Code Product
├── 01-Docker-Compose-Community/   ← 免费 · 社区裂变版
│   ├── docker-compose.yml         一键启动所有服务
│   ├── .env.example               环境变量模板
│   ├── deploy.sh                  一键部署脚本
│   ├── healthcheck.sh             健康检查脚本
│   └── README.md                  使用说明
│
├── 02-K8s-Enterprise/             ← 付费 · 企业商用版
│   ├── k8s-manifests/             K8s编排文件
│   ├── helm-chart/                Helm图表
│   └── README.md                  部署说明
│
├── 03-Authorization-System/       ← 授权控制核心
│   ├── auth-server.py             Flask授权服务
│   ├── Dockerfile                 容器化
│   ├── LICENSE_ARCHITECTURE.md    授权架构说明
│   └── README.md
│
└── 04-Distributor-Tools/          ← 分销工具
    └── (待完善)
```

## 谁该用

| 角色 | 版本 | 理由 |
|------|------|------|
| 个人开发者/小团队 | 社区版 | 免费，本地docker-compose跑起来体验 |
| 企业/集成商 | 企业版 | 授权系统+K8s集群+售后支持 |
| 代理商 | 分销版 | 拿30%佣金，卖给你的企业客户 |

## 快速体验

```bash
git clone https://github.com/xxx/ai-cluster
cd ai-cluster
cp .env.example .env
# 编辑 .env 改密码
./deploy.sh
```

## 授权说明

社区版在GitHub上完全公开，含水印和功能限制。
企业版购买license后解锁全部功能。
详情见 `03-Authorization-System/README.md`
