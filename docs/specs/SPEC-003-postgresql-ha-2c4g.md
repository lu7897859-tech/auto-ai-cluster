# SPEC-003: PostgreSQL HA for 2C4G Infrastructure

**Status:** PROPOSED STANDARD | **Series:** Auto-AI-Cluster | **Date:** 2026-07-19

## Architecture
Patroni + etcd + 2 PG nodes. etcd co-located on primary (128MB).

## PG Config
shared_buffers=512MB, effective_cache_size=1.5GB, work_mem=32MB, maintenance_work_mem=64MB, max_connections=20, wal_buffers=4MB, random_page_cost=4.0

## Failover
PG primary crash: Patroni watchdog 10s -> promote 15s
etcd failure: static config fallback 5s
Network partition: majority stays primary 15s

## References
- SPEC-001
- https://lu7897859-tech.github.io/auto-ai-cluster/
