# 10 — Deploying Production-Grade AI Clusters Without Kubernetes

**2026-07-16**

The industry assumption is that production = Kubernetes. For autonomous AI clusters at the edge, this is wrong.

## Kubernetes at 2C4G
| Component | Memory | CPU |
|-----------|:------:|:---:|
| kubelet | 200-500MB | 0.1 core |
| kube-proxy | 50-100MB | 0.05 core |
| etcd (if control plane) | 500MB-1GB | 0.2 core |
| CoreDNS | 20-50MB | 0.01 core |
| **K8s overhead alone** | **~1-1.5GB** | **~0.4 core** |
| Remaining for AI workloads | **~2.5GB** | **~1.6 core** |

## Docker Compose at 2C4G
| Component | Memory | CPU |
|-----------|:------:|:---:|
| docker engine | 50-100MB | 0.02 core |
| compose (if running) | 20MB | negligible |
| Nginx | 30-50MB | 0.01 core |
| **Overhead total** | **~150MB** | **~0.05 core** |
| Remaining for AI workloads | **~3.8GB** | **~3.95 core** |

## The Argument
Docker Compose is not "less production" than Kubernetes — it's **production for a different scale class**. For single-node autonomous systems, Compose provides:
- Declarative infrastructure (YAML)
- Health checks + auto-restart
- Network isolation between containers
- Volume persistence
- **95% more available resources** for actual workloads

## When to Graduate to K8s
Only when you need multi-node orchestration. The Auto-AI-Cluster enterprise version includes K8s migration paths for this exact scenario.

[Community Edition (Docker Compose)](https://github.com/lu7897859-tech/auto-ai-cluster)
[Enterprise Edition (K8s)](https://github.com/lu7897859-tech/auto-ai-cluster/blob/main/k8s-enterprise)
[Read the white paper](/auto-ai-cluster/white-paper.html)
