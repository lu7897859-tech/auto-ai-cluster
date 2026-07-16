# 04 — Disaster Recovery for Edge AI Clusters: When the VPS Goes Down

**2026-07-16**

A 2C4G VPS is cheap and effective, but it's also a single point of failure. Here's how we handle disaster recovery at zero cost.

## Automated Health Check Loop
The survival-first architecture includes a watchdog that runs every 60 seconds:

```
1. Check PostgreSQL responsiveness (SELECT 1)
2. Check n8n API health (HTTP 200)
3. Check system memory usage (< 85%)
4. Check disk space (< 90%)
5. Check nginx reverse proxy
→ If any fails: auto-restart service
→ If 3 consecutive failures: reboot container stack
→ If 5 consecutive failures: notify admin (optional)
```

## Backup Strategy (0-cost)
```bash
# PostgreSQL daily dump (cron)
pg_dump -U n8n n8n_db | gzip > /backups/n8n_daily.sql.gz
# Retention: 7 days
find /backups -name "*.sql.gz" -mtime +7 -delete
```

## Key Insight
Most disaster recovery tools cost more than the VPS itself. Our approach: **keep it simple, keep it restartable**. A properly configured Docker-Compose stack can recover from failure in under 30 seconds — no orchestration platform required.

[Full deployment guide](https://github.com/lu7897859-tech/auto-ai-cluster)
[Survival-first architecture](/auto-ai-cluster/white-paper.html)
