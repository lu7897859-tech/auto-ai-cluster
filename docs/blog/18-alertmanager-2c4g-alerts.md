# 18 — Alerting on a Shoestring: Prometheus AlertManager for 2C4G Clusters

**2026-07-25**

You have Prometheus scraping metrics. You have Grafana dashboards. But when your n8n workflow silently fails at 2 AM, you wake up to a broken pipeline and angry users.

The missing piece: **AlertManager**.

This guide shows how to run Prometheus AlertManager on your 2C4G VPS with near-zero memory overhead, integrate it with your existing Prometheus setup, and route critical alerts to Telegram, Email, or Slack without pulling in heavyweight notification systems.

---

## Why AlertManager?

Metrics without alerts are just charts. AlertManager transforms your Prometheus data into actionable notifications:

- **Route-based alerting**: Send critical alerts to PagerDuty, warnings to Slack, everything else to email
- **Deduplication & grouping**: No more 500 identical alerts when a service goes down
- **Inhibition**: Silence related alerts (e.g., don't alert on downstream services when the database is down)
- **Silences**: Schedule maintenance windows without alert noise

And it runs in **under 30 MB RAM**.

---

## Memory Footprint: The 2C4G Reality

| Component | RAM Usage |
|-----------|-----------|
| Prometheus | 80-120 MB |
| AlertManager | 20-30 MB |
| Grafana | 60-80 MB |
| n8n | 150-250 MB |
| PostgreSQL | 40-60 MB |
| **Total** | ~350-540 MB |

AlertManager is the lightest component in your observability stack. If you can run Prometheus, you can run AlertManager.

---

## Docker Compose Setup

Add AlertManager to your existing `docker-compose.yml`:

```yaml
  alertmanager:
    image: prom/alertmanager:v0.27.0
    container_name: alertmanager
    command:
      - '--config.file=/etc/alertmanager/alertmanager.yml'
      - '--storage.path=/alertmanager'
      - '--web.external-url=http://localhost:9093'
    volumes:
      - ./alertmanager/alertmanager.yml:/etc/alertmanager/alertmanager.yml
      - alertmanager_data:/alertmanager
    ports:
      - "9093:9093"
    restart: unless-stopped
    networks:
      - monitoring
    deploy:
      resources:
        limits:
          memory: 64M
        reservations:
          memory: 16M

volumes:
  alertmanager_data:
```

**Key resource constraint**: 64 MB limit is generous; typical usage is 20-30 MB.

---

## AlertManager Configuration

Create `alertmanager/alertmanager.yml`:

```yaml
global:
  resolve_timeout: 5m
  # Slack integration (optional)
  slack_api_url: 'https://hooks.slack.com/services/YOUR/WEBHOOK/URL'

route:
  group_by: ['alertname', 'severity']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h
  receiver: 'telegram-critical'
  routes:
    - match:
        severity: critical
      receiver: 'telegram-critical'
    - match:
        severity: warning
      receiver: 'email-warnings'

receivers:
  - name: 'telegram-critical'
    webhook_configs:
      - url: 'http://n8n:5678/webhook/alert-critical'
        send_resolved: true
  
  - name: 'email-warnings'
    email_configs:
      - to: 'admin@yourdomain.com'
        from: 'alertmanager@yourdomain.com'
        smarthost: 'smtp.example.com:587'
        auth_username: 'alertmanager@yourdomain.com'
        auth_password: 'your-app-password'

inhibit_rules:
  - source_match:
      severity: 'critical'
    target_match:
      severity: 'warning'
    equal: ['alertname', 'instance']
```

**Telegram via n8n webhook**: The cleanest approach on 2C4G. Create an n8n workflow that receives the AlertManager webhook and forwards to Telegram Bot API.

---

## Prometheus Alert Rules

Add to `prometheus/alert_rules.yml`:

```yaml
groups:
  - name: node_alerts
    rules:
      - alert: HighMemoryUsage
        expr: (1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100 > 85
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High memory usage on {{ $labels.instance }}"
          description: "Memory usage is {{ $value }}%"

      - alert: MemoryCritical
        expr: (1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100 > 95
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Memory critical on {{ $labels.instance }}"
          description: "Memory usage is {{ $value }}%. Immediate action required."

      - alert: DiskSpaceWarning
        expr: (1 - (node_filesystem_avail_bytes{fstype!="tmpfs"} / node_filesystem_size_bytes{fstype!="tmpfs"})) * 100 > 80
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Disk space warning on {{ $labels.instance }}"
          description: "Disk {{ $labels.mountpoint }} is {{ $value }}% full"

      - alert: ContainerDown
        expr: container_last_seen{name!=""} < time() - 60
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Container {{ $labels.name }} is down"
          description: "Container has been missing for more than 2 minutes."

  - name: n8n_alerts
    rules:
      - alert: N8NWorkflowFailed
        expr: increase(n8n_workflow_executions_failed_total[5m]) > 0
        for: 1m
        labels:
          severity: warning
        annotations:
          summary: "n8n workflow execution failed"
          description: "{{ $value }} workflow execution(s) failed in the last 5 minutes"

      - alert: N8NHighLatency
        expr: histogram_quantile(0.95, rate(n8n_workflow_execution_duration_seconds_bucket[5m])) > 30
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "n8n workflow latency high"
          description: "95th percentile latency is {{ $value }}s"
```

Update `prometheus.yml`:

```yaml
alerting:
  alertmanagers:
    - static_configs:
        - targets:
          - alertmanager:9093

rule_files:
  - /etc/prometheus/alert_rules.yml
```

---

## n8n Telegram Alert Workflow

Create a simple n8n workflow for the Telegram webhook:

```
[Webhook] → [Set] → [HTTP Request → Telegram Bot API]
```

Webhook node:
- Method: POST
- Path: `/alert-critical`
- Authentication: None (or add header auth)

Set node (convert AlertManager payload):
```json
{
  "text": "🚨 {{ $json.status.toUpperCase() }}\n\n{{ $json.alerts[0].annotations.summary }}\n\n{{ $json.alerts[0].annotations.description }}\n\nStarted: {{ $json.alerts[0].startsAt }}"
}
```

HTTP Request node:
- URL: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/sendMessage`
- Method: POST
- Body: `{"chat_id": "<YOUR_CHAT_ID>", "text": "{{ $json.text }}", "parse_mode": "HTML"}`

**Memory impact**: This workflow runs only when triggered. Zero baseline overhead.

---

## Testing Your Alerts

### 1. Verify AlertManager is reachable

```bash
curl http://localhost:9093/-/healthy
# Should return: OK
```

### 2. Check Prometheus → AlertManager connection

```bash
curl http://localhost:9090/api/v1/alertmanagers
# Should show your alertmanager in "activeAlertmanagers"
```

### 3. Trigger a test alert

```bash
curl -X POST http://localhost:9093/api/v1/alerts -d '[
  {
    "labels": {
      "alertname": "TestAlert",
      "severity": "critical"
    },
    "annotations": {
      "summary": "This is a test alert",
      "description": "If you see this, AlertManager is working"
    }
  }
]'
```

You should receive the Telegram message within 30 seconds.

---

## Silences: Maintenance Without Noise

Before planned maintenance:

```bash
amtool silence add \
  --alertmanager.url=http://localhost:9093 \
  --author="admin" \
  --comment="Planned n8n update" \
  duration=2h \
  alertname=ContainerDown
```

List active silences:

```bash
amtool silence query --alertmanager.url=http://localhost:9093
```

---

## Dashboard Integration

Add AlertManager alerts to your Grafana dashboard:

1. Install the **AlertManager** Grafana datasource plugin
2. Add AlertManager as a data source (URL: `http://alertmanager:9093`)
3. Create a panel with the **AlertList** visualization

Now you see firing alerts alongside your metrics.

---

## Common Pitfalls

| Issue | Cause | Fix |
|-------|-------|-----|
| Alerts not firing | `for` duration not met | Check Prometheus `/alerts` endpoint |
| No notifications | Wrong receiver routing | Check AlertManager `/routes` UI at port 9093 |
| Duplicate alerts | Missing `group_by` | Add `alertname` to `group_by` |
| High memory | Too many active alerts | Increase `group_interval`, reduce alert cardinality |

---

## The 2C4G Bottom Line

AlertManager on 2C4G:

- **RAM**: 20-30 MB baseline, 50 MB peak with heavy alert volume
- **CPU**: Negligible (< 1%)
- **Disk**: ~10 MB for silence storage
- **Network**: Only when alerts fire

If your VPS can run Prometheus, it can run AlertManager. The marginal cost is essentially zero. The marginal value is catching issues before users notice.

---

## Summary Checklist

- [ ] Add AlertManager container to `docker-compose.yml` with 64 MB limit
- [ ] Create `alertmanager.yml` with routing to Telegram (via n8n webhook) and email
- [ ] Add alert rules to Prometheus for memory, disk, containers, n8n
- [ ] Create n8n Telegram notification workflow
- [ ] Test with `amtool` or curl
- [ ] Add AlertManager panel to Grafana
- [ ] Document silences for scheduled maintenance

Your 2C4G cluster now has eyes that blink when things go wrong. Sleep better.
