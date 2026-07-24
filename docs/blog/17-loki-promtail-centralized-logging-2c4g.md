# 17 — Centralized Logging for Your 2C4G AI Cluster: Loki, Promtail & Grafana

**2026-07-25** | 2C4G AI Cluster Series

You have Prometheus scraping metrics and Grafana dashboards lighting up. But when n8n throws an opaque 502 error at 3 AM, or a container crashes and restarts before you can `docker logs`, metrics alone won't tell you what happened.

Logs are the other half of observability. On a 2C4G VPS, traditional solutions like the ELK stack (Elasticsearch + Logstash + Kibana) are out of the question — Elasticsearch alone wants 4 GB RAM minimum.

Enter **Grafana Loki**: a log aggregation system designed for the resource-constrained. It doesn't index the content of logs — it indexes only metadata labels, making it dramatically lighter.

This post covers running Loki + Promtail on a 2C4G VPS alongside your existing monitoring stack, consuming under 256 MB RAM total.

---

## Why Loki Instead of ELK?

| Feature | Elasticsearch | Loki |
|---------|--------------|------|
| RAM (idle) | 1.5–4 GB | 40–80 MB |
| Disk index | Full-text inverted index | Label-only (like Prometheus) |
| Query language | ES DSL / KQL | LogQL (PromQL-like) |
| Integration | Separate stack | Bolts into existing Grafana |

For a 2C4G VPS running n8n, Postgres, and an AI gateway, Loki is the only realistic choice for centralized logging.

---

## Architecture

```
Container A (n8n)          Container B (Postgres)     Container C (AI Gateway)
     │                           │                           │
     ▼                           ▼                           ▼
  Promtail─────────────────────Promtail─────────────────────Promtail
     │                           │                           │
     └───────────────────────────┬───────────────────────────┘
                                 ▼
                              Loki
                                 │
                                 ▼
                            Grafana
                                 │
                                 ▼
                         Browser / Telegram Alert
```

Promtail runs on each node (or as a single sidecar reading Docker logs), attaches labels, and pushes structured log entries to Loki. Loki stores them cheaply. Grafana queries Loki via LogQL alongside your Prometheus metrics.

---

## Step 1: Deploy Loki (Single Binary, No Scaling)

Loki has a `single-binary` mode perfect for 2C4G. Add it to your `docker-compose.yml`:

```yaml
services:
  # … your existing services …

  loki:
    image: grafana/loki:3.0
    ports:
      - "3100:3100"
    volumes:
      - ./config/loki:/etc/loki
      - loki_data:/loki
    command: -config.file=/etc/loki/loki-config.yaml
    deploy:
      resources:
        limits:
          memory: 128M
        reservations:
          memory: 64M
    restart: unless-stopped

  promtail:
    image: grafana/promtail:3.0
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - ./config/promtail:/etc/promtail
    command: -config.file=/etc/promtail/promtail-config.yaml
    deploy:
      resources:
        limits:
          memory: 64M
        reservations:
          memory: 32M
    restart: unless-stopped

volumes:
  loki_data:
```

This adds **under 200 MB** of committed memory to your stack.

---

## Step 2: Loki Configuration

Create `config/loki/loki-config.yaml`:

```yaml
auth_enabled: false

server:
  http_listen_port: 3100
  grpc_listen_port: 9096

common:
  path_prefix: /loki
  storage:
    filesystem:
      chunks_directory: /loki/chunks
      rules_directory: /loki/rules
  replication_factor: 1
  ring:
    instance_addr: 127.0.0.1
    kvstore:
      store: inmemory

schema_config:
  configs:
    - from: 2024-01-01
      store: boltdb-shipper
      object_store: filesystem
      schema: v12
      index:
        prefix: index_
        period: 24h

limits_config:
  ingestion_rate_mb: 2
  ingestion_burst_size_mb: 4
  max_global_streams_per_user: 1000

table_manager:
  retention_deletes_enabled: true
  retention_period: 168h  # 7 days — enough for a 2C4G VPS
```

Key choices for 2C4G:
- **Filesystem storage** instead of S3/GCS — no external dependency
- **7-day retention** — keeps disk usage under 2 GB for typical traffic
- **Replication factor 1** — we're single-node; no need for replicas
- **Ingestion rate limited** — prevents a log-spamming container from OOMing Loki

---

## Step 3: Promtail Configuration

Create `config/promtail/promtail-config.yaml`:

```yaml
server:
  http_listen_port: 9080
  grpc_listen_port: 0

positions:
  filename: /tmp/positions.yaml

clients:
  - url: http://loki:3100/loki/api/v1/push

scrape_configs:
  - job_name: docker
    docker_sd_configs:
      - host: unix:///var/run/docker.sock
        refresh_interval: 5s
    relabel_configs:
      - source_labels: ['__meta_docker_container_name']
        regex: '/(.*)'
        target_label: 'container'
      - source_labels: ['__meta_docker_container_log_stream']
        target_label: 'stream'
      - source_labels: ['__meta_docker_container_label_com_docker_compose_service']
        target_label: 'service'
      - action: labelmap
        regex: '__meta_docker_container_label_(.+)'
```

This auto-discovers all Docker containers and labels logs with `container`, `service`, and any Docker labels you've set.

---

## Step 4: Add Grafana Loki Datasource

In Grafana (already deployed from blog #14), add a Loki datasource:

**URL**: `http://loki:3100`

Then you can query logs alongside metrics. The killer feature: **correlate a metrics spike with log context**.

Example LogQL query — find errors in the last hour:

```logql
{service="n8n"} |= "error" |= "exception"
```

Or — count errors per container:

```logql
sum by (container) (count_over_time({job="docker"} |= "error"[5m]))
```

---

## Step 5: Structured Logging — Make Your Logs Useful

Loki is powerful only if your logs have structure. Add structured logging to your containers.

### n8n (via environment variable)

```yaml
services:
  n8n:
    environment:
      - N8N_LOG_LEVEL=info
      - N8N_LOG_OUTPUT=json
```

PostgreSQL emits structured logs by default. Your AI gateway should use a JSON-formatted logger (pino, winston, or similar).

### Example: structured log entry

```json
{
  "level": "error",
  "service": "ai-gateway",
  "request_id": "req_abc123",
  "duration_ms": 3050,
  "error": "upstream_timeout",
  "model": "deepseek-chat",
  "timestamp": "2026-07-25T03:00:00Z"
}
```

Query this directly:

```logql
{service="ai-gateway"} | json | duration_ms > 2000 | model="deepseek-chat"
```

This single query would have saved me three hours of debugging last month.

---

## Step 6: Disk Budget — Loki on a 2C4G SSD

On a 20 GB VPS, every gigabyte matters. Here's a realistic budget:

| Component | Daily Growth | 7-Day Total |
|-----------|-------------|-------------|
| n8n logs | ~80 MB | 560 MB |
| Postgres logs | ~30 MB | 210 MB |
| AI gateway logs | ~120 MB | 840 MB |
| System (journald) | ~40 MB | 280 MB |
| **Total** | **~270 MB** | **~1.9 GB** |

To stay safe, monitor disk usage with a Prometheus alert:

```yaml
groups:
  - name: loki
    rules:
      - alert: LokiDiskUsageHigh
        expr: (loki_ingester_memory_streams / 1000) > 800
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Loki approaching stream limit on 2C4G VPS"
```

---

## Putting It Together: Observability Stack on 2C4G

```
           ┌─────────────────────────────────┐
           │        2C4G VPS Total            │
           │                                   │
           │  Prometheus    (64 MB)            │
           │  Grafana       (64 MB)            │
           │  Loki          (128 MB)           │
           │  Promtail      (64 MB)            │
           │  cAdvisor      (32 MB)            │
           │  ─────────────────────            │
           │  Total monitor: 352 MB            │
           │                                   │
           │  n8n         (256 MB)             │
           │  Postgres    (512 MB)             │
           │  AI Gateway  (1024 MB)            │
           │  ─────────────────────            │
           │  Total app:   1792 MB             │
           │                                   │
           │  Headroom:     ~1.8 GB            │
           └─────────────────────────────────┘
```

Metrics (Prometheus) tell you *what* broke. Logs (Loki) tell you *why*. With both on your 2C4G VPS consuming under 400 MB combined, there's no excuse not to run the full observability stack.

---

## Quick-Start: Run This Now

```bash
# Create config directories
mkdir -p config/loki config/promtail

# Copy the configs above into place, then
docker compose up -d loki promtail

# Verify Loki is receiving logs
curl -s http://localhost:3100/loki/api/v1/tail?query=%7Bjob%3D%22docker%22%7D

# In Grafana, add Loki datasource → http://loki:3100
# Query: {service="n8n"} |= "error"
```

If you see log lines streaming in the tail response, your centralized logging pipeline is live. Now go break something — your logs will tell you exactly why.

---

*Part of the [Auto-AI-Cluster](https://github.com/lu7897859-tech/auto-ai-cluster) series. Deploy resilient, affordable AI infrastructure — one post at a time.*
