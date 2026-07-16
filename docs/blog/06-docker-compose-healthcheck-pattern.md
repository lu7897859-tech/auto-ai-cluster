# 06 — The Docker Compose Health Check Pattern for Autonomous Systems

**2026-07-16**

Most Docker Compose setups treat health checks as optional. For autonomous AI clusters, they're the difference between a system that runs for a year and one that dies on day three.

## The Three-Layer Health Model
```
Layer 1: Container Level   (docker healthcheck)
Layer 2: Service Level     (n8n API / PG ping)
Layer 3: System Level      (memory, disk, swap)
```

### Layer 1: Container
```yaml
healthcheck:
  test: ["CMD", "pg_isready", "-U", "n8n"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 40s
```

### Layer 2: Service
```bash
#!/bin/bash
# Check n8n API
curl -sf http://localhost:5678/healthz || exit 1
# Check PostgreSQL
pg_isready -U n8n || exit 1
```

### Layer 3: System
```bash
# Check memory
MEM=$(free -m | awk '/Mem:/ {print $3/$2 * 100}')
if (( $(echo "$MEM > 85" | bc -l) )); then
  echo "Memory critical: $MEM%"
  # Trigger graceful degradation
fi
```

## Why This Matters
A proper health check loop means your AI cluster survives OOM events, network blips, and database connection drops without human intervention. The survival-first architecture embeds this trivially in docker-compose — no orchestration platform required.

[Full health check script](https://github.com/lu7897859-tech/auto-ai-cluster/blob/main/docker-compose.yml)
[Architecture white paper](/auto-ai-cluster/white-paper.html)
