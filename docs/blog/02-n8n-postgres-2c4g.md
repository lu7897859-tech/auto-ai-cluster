# Auto-AI-Cluster 技术文章

## 02 — Deploying n8n with PostgreSQL on 2C4G VPS: A Production Setup

**2026-07-16**

Setting up n8n with PostgreSQL on a 2C4G VPS requires careful resource allocation. Here's the exact configuration we use in production.

### Memory Budget Breakdown
| Service | Memory | Percentage |
|---------|--------|------------|
| PostgreSQL | 768MB | 24% |
| n8n (main) | 256MB | 8% |
| n8n worker | 128MB | 4% |
| Nginx reverse proxy | 48MB | 1.5% |
| Health check agent | 32MB | 1% |
| OS + buffers | ~2GB | 61.5% |

### PostgreSQL Tuning for 2C4G
```sql
shared_buffers = 512MB
effective_cache_size = 1GB
work_mem = 32MB
maintenance_work_mem = 128MB
effective_io_concurrency = 200
wal_buffers = 16MB
max_worker_processes = 4
max_parallel_workers = 2
```

### n8n Configuration
```yaml
environment:
  - N8N_PORT=5678
  - DB_TYPE=postgresdb
  - DB_POSTGRESDB_HOST=postgres
  - N8N_EXECUTIONS_TIMEOUT=120
  - N8N_EXECUTIONS_DATA_PRUNE=true
  - N8N_EXECUTIONS_DATA_MAX_AGE=72
```

### Why This Works
At 2C4G, PostgreSQL consumes ~3.7% of total available compute cycles per query. With proper indexing and the survival-first health loop, this setup runs continuously for months without intervention.

→ [Full docker-compose.yml](https://github.com/lu7897859-tech/auto-ai-cluster)
→ [Architecture white paper](/auto-ai-cluster/white-paper.html)
