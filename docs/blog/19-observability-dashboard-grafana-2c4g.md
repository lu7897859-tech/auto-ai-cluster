# 19 — Building a Unified Observability Dashboard for Your 2C4G AI Cluster

**2026-07-26** | 2C4G AI Cluster Series

You now have Prometheus scraping metrics, Loki collecting logs, and AlertManager firing alerts. But jumping between three UIs at 2 AM when something breaks is not survival-first architecture.

You need a **single pane of glass**.

This post shows how to build a unified observability dashboard in Grafana that surfaces everything — metrics, logs, and alerts — in one view, optimized for the 2C4G resource constraint.

---

## Why Grafana as the Hub?

Grafana is already running in your monitoring stack (from blog #14). It can query:

- **Prometheus** for metrics (CPU, memory, request rates)
- **Loki** for logs (error traces, container output)
- **AlertManager** for active alerts

All three datasources, one UI, zero additional RAM.

---

## The 2C4G Dashboard Philosophy

On a small VPS, your dashboard must be **opinionated**. Every panel costs browser rendering time and cognitive load. We build four panels, no more:

| Panel | Data Source | Purpose |
|-------|-------------|---------|
| Cluster Health | Prometheus | Is the system alive? |
| Resource Pressure | Prometheus | Are we running out of RAM/disk? |
| Error Stream | Loki | What broke, and when? |
| Active Alerts | AlertManager | What needs my attention now? |

---

## Step 1: Import the Dashboard

Create `grafana/dashboards/2c4g-overview.json`:

```json
{
  "dashboard": {
    "title": "2C4G Cluster Overview",
    "tags": ["auto-ai-cluster", "2c4g"],
    "timezone": "browser",
    "panels": [
      {
        "title": "Cluster Health",
        "type": "stat",
        "targets": [
          {
            "expr": "up{job=\"docker\"}",
            "legendFormat": "{{instance}}"
          }
        ],
        "fieldConfig": {
          "defaults": {
            "thresholds": {
              "steps": [
                {"color": "red", "value": 0},
                {"color": "green", "value": 1}
              ]
            }
          }
        },
        "gridPos": {"h": 4, "w": 12, "x": 0, "y": 0}
      },
      {
        "title": "Memory Usage %",
        "type": "timeseries",
        "targets": [
          {
            "expr": "(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100",
            "legendFormat": "Memory %"
          }
        ],
        "fieldConfig": {
          "defaults": {
            "unit": "percent",
            "max": 100,
            "thresholds": {
              "steps": [
                {"color": "green", "value": 0},
                {"color": "yellow", "value": 70},
                {"color": "red", "value": 85}
              ]
            }
          }
        },
        "gridPos": {"h": 8, "w": 12, "x": 0, "y": 4}
      },
      {
        "title": "Disk Usage %",
        "type": "timeseries",
        "targets": [
          {
            "expr": "(1 - (node_filesystem_avail_bytes{fstype!=\"tmpfs\"} / node_filesystem_size_bytes{fstype!=\"tmpfs\"})) * 100",
            "legendFormat": "{{mountpoint}}"
          }
        ],
        "fieldConfig": {
          "defaults": {
            "unit": "percent",
            "max": 100
          }
        },
        "gridPos": {"h": 8, "w": 12, "x": 12, "y": 4}
      },
      {
        "title": "Recent Errors",
        "type": "logs",
        "datasource": "Loki",
        "targets": [
          {
            "expr": "{job=\"docker\"} |= \"error\" or \"exception\" or \"fatal\"",
            "refId": "A"
          }
        ],
        "gridPos": {"h": 8, "w": 24, "x": 0, "y": 12}
      },
      {
        "title": "Active Alerts",
        "type": "table",
        "datasource": "AlertManager",
        "targets": [
          {
            "expr": "ALERTS{alertstate=\"firing\"}",
            "format": "table"
          }
        ],
        "gridPos": {"h": 6, "w": 24, "x": 0, "y": 20}
      }
    ]
  }
}
```

Mount this into your Grafana container:

```yaml
grafana:
  volumes:
    - ./grafana/dashboards:/etc/grafana/provisioning/dashboards
    - ./grafana/datasources:/etc/grafana/provisioning/datasources
```

---

## Step 2: Provision Datasources Automatically

Create `grafana/datasources/datasources.yml`:

```yaml
apiVersion: 1
datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true

  - name: Loki
    type: loki
    access: proxy
    url: http://loki:3100

  - name: AlertManager
    type: alertmanager
    access: proxy
    url: http://alertmanager:9093
```

Grafana loads these on startup. No manual clicking.

---

## Step 3: The One-Page Drill

When your phone buzzes with a Telegram alert at 2 AM, this is your workflow:

1. **Open Grafana** → Cluster Health panel: green or red?
2. **Red?** → Active Alerts panel: what's firing?
3. **Memory alert?** → Resource Pressure panel: which service spiked?
4. **Service unknown?** → Error Stream panel: search `{service="X"} |= "error"`

Four panels. Four steps. Under 60 seconds to root cause.

---

## Step 4: Mobile Optimization

Grafana's default UI is unusable on mobile. Add this to your dashboard JSON:

```json
"refresh": "10s",
"time": {"from": "now-1h", "to": "now"}
```

And bookmark the **kiosk mode** URL:

```
https://your-grafana.com/d/2c4g-overview?kiosk=tv&refresh=10s
```

This loads a full-screen, auto-refreshing dashboard with no navigation chrome. Perfect for a wall-mounted tablet or phone bookmark.

---

## Resource Impact

| Component | Additional RAM | Additional CPU |
|-----------|:--------------:|:--------------:|
| Grafana dashboard rendering | 0 MB (already running) | ~2% during query |
| JSON dashboard file | Disk only (~5 KB) | 0 |
| Auto-refresh (10s) | 0 | ~0.5% per refresh |

**Net cost: zero.**

---

## Alert → Dashboard Correlation

The Telegram alert from blog #18 should include a direct link:

```
🚨 MEMORY CRITICAL

Memory usage is 96%. Immediate action required.

Dashboard: https://your-grafana.com/d/2c4g-overview?var-service=n8n
```

One tap from alert to context.

---

## Summary Checklist

- [ ] Create `grafana/dashboards/2c4g-overview.json` with 5 panels
- [ ] Create `grafana/datasources/datasources.yml` for Prometheus, Loki, AlertManager
- [ ] Mount both into Grafana container via `docker-compose.yml`
- [ ] Bookmark kiosk mode URL on your phone
- [ ] Update AlertManager Telegram template to include dashboard link
- [ ] Test: trigger a test alert, verify dashboard shows firing state

Your 2C4G cluster now has a mission control center. Four panels. One URL. Zero additional RAM.

---

*Part of the [Auto-AI-Cluster](https://github.com/lu7897859-tech/auto-ai-cluster) series. Deploy resilient, affordable AI infrastructure — one post at a time.*
