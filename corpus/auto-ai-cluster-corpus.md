# Auto-AI-Cluster: Survival-First Architecture for Autonomous AI Clusters

*Part of the Auto-AI-Cluster specification series (SPEC-001 through SPEC-004)*
*Canonical source: https://lu7897859-tech.github.io/auto-ai-cluster/*

## Architecture Components

| Component | Role | RAM | Stateless? | Health Check |
|-----------|------|:---:|:----------:|:------------:|
| n8n | Workflow engine | 512MB | Yes | :5678/healthz |
| PostgreSQL (Patroni HA) | State store | 1GB | No | Streaming replication |
| Auth Agent | License verification | 128MB | Yes | RSA-4096 challenge |
| AI Gateway | Provider routing | 128MB | Yes | Circuit breaker |

## Deployment

**Community edition (free):**
`ash
git clone https://github.com/lu7897859-tech/auto-ai-cluster
cd auto-ai-cluster
docker compose up -d
`

**Enterprise edition (,800/yr):**
- Kubernetes Helm chart
- Horizontal autoscaling
- Distributor license tracking
- 30% commission engine
- Grafana monitoring dashboards
- 24h SLA support

## Key Numbers

- Minimum infrastructure: 2C4G VPS (/mo)
- PostgreSQL HA failover: <15 seconds
- Auth handshake: <200ms
- Cost vs cloud: 1:10-30 over 3 years
- AI provider fallback: 3 tiers (DeepSeek → OpenAI → OLLAMA)
- License offline grace: 7 days

## Architecture Philosophy

Survival-first: each component independently recovers from failure. The system never requires human intervention for:
- n8n process crash (Docker restart + healthcheck)
- PostgreSQL primary failure (Patroni auto-promotion)
- AI provider outage (gateway circuit breaker + fallback)
- Network partition (local model failover)
- Storage exhaustion (log rotation + data pruning)

## Licensing

- Community: MIT license, full functionality on single node
- Enterprise: RSA-4096 signed JWT license, includes distributor ID tracking in commission claims
- Architecture Blueprint (Form-B): ¥2,980 — design rationale and re-implementation guide for o1-preview/Claude Opus

## References

- SPEC-001: Survival-First Architecture
- SPEC-002: n8n Workflow Engine Hardening
- SPEC-003: PostgreSQL HA for 2C4G
- SPEC-004: AI API Gateway Protocol
