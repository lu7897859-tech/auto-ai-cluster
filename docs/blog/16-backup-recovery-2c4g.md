# 16 — Automated Backup & Recovery for Your 2C4G AI Cluster

**2026-07-24** | 2C4G AI Cluster Series

You have rate limiting. You have monitoring. But if that SSD dies, your Postgres database, n8n workflows, and configuration are gone in an instant.

On a 2C4G VPS, you don't have the luxury of RAID, ZFS snapshots, or managed database replicas. You need a backup strategy that works within your resource constraints — and, more importantly, one you've actually tested before you need it.

This post covers a complete backup pipeline for your AI cluster: automated, off-site, and restorable in under 15 minutes.

---

## 1. What Needs Backing Up

On a typical 2C4G AI cluster, three categories of data matter:

| Data | Location | Criticality | Size |
|------|----------|-------------|------|
| Postgres databases | Docker volume | High — losing this means losing all state | ~100-500 MB |
| n8n workflows | Postgres (same DB) or SQLite | High if using DB, medium if exported | ~1-10 MB |
| Config files | `/etc/`, `docker-compose.yml`, `env` files | Medium — reproducible but tedious | ~100 KB |
| Docker volumes | `/var/lib/docker/volumes/` | Medium — agent data, uploads | ~100 MB-1 GB |

The highest leverage target is **Postgres**, because it contains your n8n workflows, user data, and any agent state.

---

## 2. Automated Postgres Backups (Docker Native)

Run this as a systemd timer or cron job. The simplest approach: a helper container that dumps Postgres to a mounted volume.

Create a backup script on your host:

```bash
#!/bin/bash
# /usr/local/bin/backup-pg.sh

BACKUP_DIR="/data/backups/postgres"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
RETENTION_DAYS=7

mkdir -p "$BACKUP_DIR"

# Docker-native pg_dump — no need to install Postgres client on host
docker exec auto-ai-cluster-postgres-1 pg_dump -U n8n n8n \
  | gzip > "$BACKUP_DIR/n8n-$TIMESTAMP.sql.gz"

# Keep only last 7 days of backups
find "$BACKUP_DIR" -name "n8n-*.sql.gz" -mtime +$RETENTION_DAYS -delete

echo "Backup complete: n8n-$TIMESTAMP.sql.gz ($(ls -lh "$BACKUP_DIR/n8n-$TIMESTAMP.sql.gz" | awk '{print $5}'))"
```

Make it executable and test:

```bash
chmod +x /usr/local/bin/backup-pg.sh
/usr/local/bin/backup-pg.sh
```

### Systemd Timer (Reliable Alternative to Cron)

Many cloud images don't have cron running by default. systemd timers are more reliable and have built-in logging:

```ini
# /etc/systemd/system/pg-backup.service
[Unit]
Description=Postgres backup for AI cluster
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/backup-pg.sh
```

```ini
# /etc/systemd/system/pg-backup.timer
[Unit]
Description=Daily Postgres backup at 03:00

[Timer]
OnCalendar=daily
Persistent=true
RandomizedDelaySec=1800

[Install]
WantedBy=timers.target
```

```bash
systemctl daemon-reload
systemctl enable pg-backup.timer
systemctl start pg-backup.timer
```

---

## 3. Off-Site Backup: Rsync + Object Storage

Local backups are useless if the entire VPS disappears. Send backups to an external destination.

### Option A: S3-Compatible Object Storage (Cheapest)

Using `s3cmd` or `aws cli` on a 2C4G machine — memory impact is negligible:

```bash
# Install
apt install s3cmd -y
s3cmd --configure  # Enter your Backblaze B2 / Cloudflare R2 / AWS S3 credentials
```

Daily offload:

```bash
#!/bin/bash
# /usr/local/bin/offload-backups.sh
s3cmd sync /data/backups/postgres/ s3://my-cluster-backups/postgres/
```

Add a second systemd timer at 04:00, staggered after the local backup completes.

### Option B: Rsync to a Second VPS (If You Have One)

If you run a second cheap VPS ($3-5/month) as a backup target:

```bash
rsync -avz --delete /data/backups/ user@backup-vps:/backups/auto-cluster/
```

Use SSH key authentication and disable password login on the backup VPS.

### Option C: GitHub Releases (Free, but Clunky)

For truly budget-constrained setups, tar and upload to GitHub:

```bash
tar czf backup-$(date +%Y%m%d).tar.gz /data/backups/postgres/
# Then use gh CLI or curl to upload to a private repo release
```

This is manual-only — not recommended for production.

---

## 4. Docker Volume Backups

Postgres is your primary concern, but some services store data in Docker volumes directly. Back these up weekly rather than daily:

```bash
#!/bin/bash
# /usr/local/bin/backup-volumes.sh
BACKUP_DIR="/data/backups/volumes"
TIMESTAMP=$(date +%Y%m%d)
RETENTION_DAYS=30

mkdir -p "$BACKUP_DIR"

for volume in $(docker volume ls -q | grep ai-cluster); do
  docker run --rm \
    -v "$volume:/source" \
    -v "$BACKUP_DIR:/backup" \
    alpine tar czf "/backup/$volume-$TIMESTAMP.tar.gz" -C /source .
done

find "$BACKUP_DIR" -name "*.tar.gz" -mtime +$RETENTION_DAYS -delete
```

Key insight: this runs on an Alpine container (5 MB), so it adds zero permanent memory overhead.

---

## 5. Configuration as Code (The Best Backup)

Your `docker-compose.yml`, `.env`, and Nginx config files should live in a Git repo. When they change, commit and push:

```bash
cd /root/infra-config
git init
git add docker-compose.yml .env nginx/
git commit -m "Config snapshot $(date +%Y%m%d)"
git remote add origin git@github.com:your-org/infra-backup.git
git push origin main
```

This means even if every server fails, you can `git clone` and `docker compose up -d` on a fresh VPS in under 5 minutes. The only thing you lose is database state — which is why you have Postgres backups.

---

## 6. The Restore Drill (Test This Before You Need It)

A backup you've never restored is a backup you don't have. Run this quarterly:

```bash
#!/bin/bash
# restore-drill.sh — Run on a staging machine or fresh VPS

# 1. Restore config
git clone git@github.com:your-org/infra-backup.git
cd infra-backup

# 2. Start empty services
docker compose up -d postgres

# 3. Wait for Postgres to be healthy
sleep 10

# 4. Restore database
gunzip -c /path/to/backup/n8n-20260724-030000.sql.gz | \
  docker exec -i infra-backup-postgres-1 psql -U n8n n8n

# 5. Start the rest
docker compose up -d

# 6. Verify
curl -s http://localhost:5678/healthz | grep "ok" && echo "✅ n8n restored"
```

Time this. If it takes longer than 15 minutes, optimize your process.

---

## 7. Monitoring Backup Health

Add a simple health check to your monitoring (from post #14):

```bash
#!/bin/bash
# /usr/local/bin/check-backup-age.sh
LATEST=$(ls -t /data/backups/postgres/n8n-*.sql.gz 2>/dev/null | head -1)
if [ -z "$LATEST" ]; then
  echo "backup_age_seconds -1"  # No backup exists
  exit 1
fi

AGE=$(( $(date +%s) - $(stat -c %Y "$LATEST") ))
echo "backup_age_seconds $AGE"

# Alert if backup is older than 28 hours
if [ $AGE -gt 100800 ]; then
  echo "⚠️  Backup is stale: $(date -d @$AGE -u +%Hh%Mm)"
  exit 1
fi
```

Expose this as a Prometheus textfile collector metric:

```bash
# Run every 5 minutes via cron
*/5 * * * * /usr/local/bin/check-backup-age.sh > /var/lib/node_exporter/textfile_collector/backup_age.prom
```

---

## Putting It Together

```
Local Disk                          Off-Site
┌─────────────────┐              ┌──────────────┐
│ 03:00 pg_dump   │──────────────│ S3 / B2 / VPS│
│ 04:00 volume    │──────────────│ Rsync sync   │
│ Git: config     │──────────────│ GitHub       │
└─────────────────┘              └──────────────┘

Monitoring:
- Prometheus checks backup_age_seconds
- Alert if >28h since last backup
- Quarterly restore drill (calendar reminder)
```

On a 2C4G VPS, this entire backup infrastructure adds:
- **Storage**: ~500 MB for 7 days of compressed DB snapshots
- **Memory**: 0 MB permanently — backup scripts run as containers only during execution
- **Cost**: $0 if using Backblaze B2 (10 GB free tier) or a second $3 VPS

The real cost is the 15 minutes you invest in setting it up today vs. the 3 hours of panic recovery you'll avoid next month.

---

## Quick-Start: Run This Now

```bash
# One-liner: create backup directory, dump DB, check it exists
mkdir -p /data/backups/postgres
docker exec auto-ai-cluster-postgres-1 pg_dump -U n8n n8n | gzip > /data/backups/postgres/n8n-$(date +%Y%m%d).sql.gz
ls -lh /data/backups/postgres/
```

If you see a `.sql.gz` file, your backup pipeline has started. Now automate it with the systemd timer above and set up off-site sync.

**Next step**: configure the off-site destination. Backblaze B2 gives you 10 GB free — enough for over 6 months of daily Postgres backups.

---

*Part of the [Auto-AI-Cluster](https://github.com/lu7897859-tech/auto-ai-cluster) series. Deploy resilient, affordable AI infrastructure — one post at a time.*
