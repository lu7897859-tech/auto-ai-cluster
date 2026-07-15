# Auto-AI-Cluster

**自主AI集群 · 零成本构建的生产级工程范式**

> 一个完整的自主AI集群工程产品体系 —— 从2C4G Docker Compose原型到K8s企业级部署，从架构白皮书到授权系统，全套可复现。

---

## 📦 产品矩阵

### Form-A：可部署的工程产品（源代码级）

| 产品 | 说明 | 价格 |
|------|------|------|
| **Docker-Compose-Community** | 7服务集群：n8n+Redis+PG+Nginx+AI-Gateway+Auth+pgAdmin | 免费 |
| **K8s-Enterprise** | K8s Helm Chart + 高可用PG + 自动扩缩 | ¥49,800 |
| **Authorization-System** | RSA-2048签名验证 + 机器指纹绑定 + 7天离线缓存 | 社区版内置 |

### Form-B：虚拟知识产品（架构视角）

| 产品 | 说明 | 价格 |
|------|------|------|
| **架构白皮书 PDF** | 11章完整架构解析 + 7个AI提示词模板 | ~~¥2,980~~ 免费下载 |

**白皮书下载**: [Form-B-Architecture-Paper.pdf](https://jsonproxy.3g.qq.com/urlmapper/1vwce6)

---

## 🚀 快速开始

```bash
# 克隆社区版
git clone https://github.com/lu7897859-tech/auto-ai-cluster.git
cd auto-ai-cluster/Form-A-Code-Product/01-Docker-Compose-Community

# 配置环境变量
cp .env.example .env
# 编辑 .env 填入你的 API Key

# 一键部署
bash deploy.sh
```

访问 http://localhost:5678 进入 n8n 工作流引擎。

---

## 🧱 项目结构

```
Form-A-Code-Product/
├── 01-Docker-Compose-Community/   ← 免费 · 一键部署
├── 02-K8s-Enterprise/             ← 企业版 · Helm Chart
├── 03-Authorization-System/       ← RSA授权服务 (998行, 实测通过)
└── 04-Distributor-Tools/          ← 分销商工具包

Form-B-Virtual-Product/
├── 01-Architecture-Paper/         ← 系统架构 / AI安全 / 数据库设计
├── 02-Engineering-Philosophy/     ← 最小逻辑原则 / 存续优先
└── 03-Reimplementation-Guide/     ← 自研重构路线 / 组件工时 / 提示词模板

Sales-Operations/
├── 01-Pricing/                    ← 定价表
├── 02-Distribution-Channels/      ← GitHub Release / 代理商 / 微信分销
├── 03-Legal-Templates/            ← 社区许可 / 企业授权 / 分销协议
└── 04-Money-Path.md               ← 六条资金路径
```

---

## 🧠 核心思想

**存续优先原则**：在资源受限环境下，核心业务流程永远优先于非核心。熔断机制依次释放非关键服务，确保 n8n + PostgreSQL 永不中断。

**最小逻辑原则**：每个组件必须能在 A4 纸上画完架构图。系统存活概率 ∝ 1/(模块数 × 接口数 × 状态数)。

**2C4G 约束驱动设计**：极限条件催生更好的决策。2C4G 的苛刻约束迫使每个服务只做一件事，避免了现代 AI 基础设施的膨胀。

---

## 📄 许可证

社区版使用 **AGPLv3** — n8n 的许可证友好协议。不修改源码、仅通过 API 使用，不会强制开源商业逻辑。

企业版和 Form-B 产品需单独授权，详见 [授权协议](Sales-Operations/03-Legal-Templates/)。

---

## 📬 联系

- GitHub Issues: [提交需求](https://github.com/lu7897859-tech/auto-ai-cluster/issues)
- 白皮书PDF短链: [https://jsonproxy.3g.qq.com/urlmapper/1vwce6](https://jsonproxy.3g.qq.com/urlmapper/1vwce6)

---

*用工程思维解决AI基础设施问题。*
