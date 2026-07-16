# 07 — PostgreSQL Survival Tuning for 2C4G: A Practical Guide

**2026-07-16**

PostgreSQL at 2C4G is like tuning a race car for city streets. The default config assumes abundant resources. Here's what to change.

## The Config
```ini
shared_buffers = 512MB       # 25% of RAM
effective_cache_size = 1536MB # 75% of RAM - OS will cache the rest
work_mem = 16MB              # Keep low: 16MB × max_connections = total
maintenance_work_mem = 128MB # For vacuum, index creation
wal_buffers = 8MB            # Minimal for low-write workloads
random_page_cost = 1.1       # SSD optimization (default 4.0)
effective_io_concurrency = 200
max_parallel_workers_per_gather = 1  # No parallelism on 2 cores
max_worker_processes = 2
```

## The Query That Tells You If Your PG Is Healthy
```sql
SELECT
  sum(blks_read) as total_reads,
  sum(blks_hit) as total_hits,
  sum(blks_hit)::float / (sum(blks_hit) + sum(blks_read))::float * 100 as cache_hit_ratio,
  numbackends
FROM pg_stat_database;
-- Cache hit ratio should be > 99%
```

## The Trap
On 2C4G, the most common PostgreSQL failure is not a crash — it's **silent swapping**. When PG + n8n + OS exceed 4GB, the kernel swaps, and query latency spikes from 2ms to 5000ms. The survival-first health check catches this before users notice.

[View the full docker-compose](https://github.com/lu7897859-tech/auto-ai-cluster)
[Read the survival-first white paper](/auto-ai-cluster/white-paper.html)
