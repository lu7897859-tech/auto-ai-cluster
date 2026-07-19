# SPEC-002: n8n Workflow Engine Hardening

**Status:** PROPOSED STANDARD | **Series:** Auto-AI-Cluster | **Date:** 2026-07-19

## Resource Optimization
EXECUTIONS_DATA_PRUNE=true, EXECUTIONS_DATA_MAX_AGE=168, EXECUTIONS_DATA_PRUNE_MAX_COUNT=10000, N8N_PAYLOAD_SIZE_MAX=16

## Connection Pooling
DB_POSTGRESDB_POOL_SIZE=3, DB_POSTGRESDB_CONNECTION_TIMEOUT=30000

## Health Check
wget --spider http://localhost:5678/healthz, interval 15s, timeout 5s, retries 3

## References
- SPEC-001: Survival-First Architecture
- https://lu7897859-tech.github.io/auto-ai-cluster/
