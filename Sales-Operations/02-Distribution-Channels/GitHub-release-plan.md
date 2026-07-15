# GitHub 分发策略

## 仓库配置

| 项目 | 配置 |
|------|------|
| 可见性 | **public** |
| 仓库名 | form-a（业务名）+ form-a-community（技术仓库名） |
| 主题标签 | `ai-cluster` `k8s` `n8n` `docker-compose` `ai-orchestration` |
| License | 自定义社区许可（详见法务文件） |
| 首页 | https://github.com/{org}/form-a-community |

## README 架构

README 遵循「AIDA 模型」：

```
# Form-A - AI 集群编排引擎

> 像管理一台机器一样管理你的 AI 集群

[一行 GIF 演示 / 架构图]

## ✨ Features（3 秒看出价值）
- 一键部署到 Docker / K8s
- 内置 n8n 工作流引擎
- 多模型统一网关
- 实时监控面板

## 🚀 Quick Start（30 秒跑起来）
```bash
git clone https://github.com/{org}/form-a-community
cd form-a-community
docker-compose up -d
```

## 📖 文档
- [社区版文档](link)
- [企业版文档](link)

## 💼 企业版
需要 K8s 集群部署、License 授权、运维支持？

👉 **[免费申请 14 天企业版体验](https://your-domain.com/trial?source=github)**

⭐ **Star 本项目后，截图发给客服可优先审核企业版资格**

## 📊 项目看板
![GitHub Stars](https://img.shields.io/github/stars/...)
![Docker Pulls](https://img.shields.io/docker/pulls/...)

## 🤝 贡献指南
[CONTRIBUTING.md](link)

## 📄 许可
社区版采用 Form-A Community License —— **免费使用，商用受限**。
```

## Release 策略

| 阶段 | 频率 | 内容 |
|------|------|------|
| Alpha | 按需 | 内部测试 |
| Beta | 双周 | 社区公测，收集反馈 |
| Stable | 月度 | 正式 Release，含 changelog |
| Patch | 按需 | 紧急修复 |

每个 Release 包含：
- 源码压缩包（Source code zip/tar.gz）
- Docker Image（Push to GitHub Container Registry）
- Release Notes（中文 + English）
- 迁移指南（如果涉及 breaking change）

## CI/CD（GitHub Actions）

| Workflow | 触发条件 | 动作 |
|----------|---------|------|
| `build.yml` | PR / push to main | 构建 docker 镜像，运行单元测试 |
| `release.yml` | Tag push (v*) | 构建镜像 → Push to GHCR → 创建 GitHub Release |
| `docs.yml` | push to main | 构建文档站点 → Deploy to GitHub Pages |
| `security-scan.yml` | 每日 03:00 UTC | Dependabot + Trivy 安全扫描 |

## 裂变 & 增长机制

| 策略 | 执行方式 | 预期效果 |
|------|---------|---------|
| **Star 换体验** | README 引导 Star → 截图联系客服 → 获得企业版试用优先审核 | 低成本的社交证明积累 |
| **Issue 贡献激励** | 提交有价值的 Issue/PR → 赠送企业版 1 个月 | 活跃社区，降低维护成本 |
| **GitHub Pages 展示** | 用 GitHub Pages 搭建案例展示站 | SEO 自然流量 |
| **Shields.io 徽章** | 所有 README 顶部展示 star/build/docker pull 数据 | 社交证明，降低信任成本 |

## 运营节奏

| 阶段 | 时长 | 目标 Stars | 关键动作 |
|------|------|-----------|---------|
| 冷启动 | 第 1~2 周 | 50+ | 技术媒体投稿、知乎/掘金发文、开发者社群分享 |
| 增长期 | 第 3~8 周 | 500+ | 企业版试用转化、社区贡献者招募 |
| 稳定期 | 第 9 周起 | 1000+ | 案例征集、KOL 评测视频、海外推广 |

## 注意事项

1. **绝对不要**在公开仓库中包含 License Key、API Key 或敏感配置
2. 社区版的 Docker Compose 配置应该包含 **内置的试用 License 校验**（到期弹提示引导购买）
3. GitHub Issues 模板要区分：Bug Report / Feature Request / Question / Security
4. 每周至少回复一次 Issue，超过 7 天未回复的 Issue 需要运营预警
5. Release Notes 必须包含兼容性说明和升级步骤
