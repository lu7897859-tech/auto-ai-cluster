# 08 — n8n Workflow Optimization for Low-Memory Environments

**2026-07-16**

n8n is surprisingly memory-efficient for what it does — but one badly designed workflow can OOM the entire cluster.

## The Golden Rules
1. **One workflow at a time**: Set concurrency to 1
2. **Prune execution data**: 72h max retention
3. **Batch API calls**: Avoid parallel HTTP requests
4. **Clean up large payloads**: Delete temp data immediately

## n8n Config for 2C4G
```yaml
N8N_EXECUTIONS_TIMEOUT: 120       # Kill long-running workflows
N8N_EXECUTIONS_DATA_PRUNE: true
N8N_EXECUTIONS_DATA_MAX_AGE: 72
N8N_MULTI_MAIN_SETUP_ENABLED: false  # Single main only
EXECUTIONS_DATA_PRUNE_TIMEOUT: 3600000
N8N_PAYLOAD_SIZE_MAX: 16          # Limit webhook payloads to 16MB
N8N_METRICS: false                # Disable metrics exporter
```

## The Cost of One Mistake
A single n8n workflow that polls every 5 seconds with a 1MB payload will consume:
- CPU: ~15% of one core continuously
- Memory: ~80MB resident
- Network: ~17GB/month egress on a 2TB plan

Fix: use webhook triggers instead of polling, clean up JSON before storing.

[Source code + config](https://github.com/lu7897859-tech/auto-ai-cluster)
[White paper](/auto-ai-cluster/white-paper.html)
