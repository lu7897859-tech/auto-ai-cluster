# 13 — Zero-Downtime CI/CD for Self-Hosted AI Clusters: GitHub Actions → 2C4G VPS

> **Published:** 2026-07-19  
> **Tags:** CI/CD, GitHub Actions, Docker, 2C4G, DevOps, Deployment  
> **Read time:** 14 min

## The Problem

You've built the perfect AI cluster on your 2C4G VPS. n8n workflows are running. Telegram bot is responding. Postgres is tuned. Now how do you update it without downtime?

On a Kubernetes cluster, you'd `kubectl rollout`. On a 2C4G VPS with Docker Compose, you need something leaner. This tutorial shows you exactly that — a **zero-downtime CI/CD pipeline** using GitHub Actions that fits in 512 MB of overhead.

## Architecture

```
Git Push (main branch)
      │
      ▼
GitHub Actions Runner
      │
      ├── 1. Build (nothing to build — Docker images pulled)
      ├── 2. Test (validate docker-compose, config files)
      ├── 3. Deploy (SSH → VPS → docker compose up -d)
      └── 4. Health Check (curl endpoints, verify services)
              │
              ▼
        Your 2C4G VPS
        (zero-downtime via rolling
         container replacement)
```

## Prerequisites

Before starting, make sure you have:

| Item | Check |
|------|:-----:|
| Docker Compose v2.24+ on VPS | ✅ |
| SSH key pair (no passphrase) | ✅ |
| GitHub repository with `main` branch | ✅ |
| Existing docker-compose.yml in repo root | ✅ |
| CI/CD-friendly Docker images (no build step on VPS) | ✅ |

## Step 1: Structure Your Repository

```
auto-ai-cluster/
├── docker-compose.yml          # Main compose file
├── .github/
│   └── workflows/
│       └── deploy.yml          # CI/CD pipeline
├── scripts/
│   ├── health-check.sh         # Post-deploy verification
│   └── rollback.sh             # Emergency rollback
├── config/
│   ├── .env.prod               # Prod env vars (gitignored)
│   └── .env.example            # Template
└── docs/
    └── blog/
        └── 13-cicd-vps-autodeploy.md
```

## Step 2: Add SSH Deploy Key to GitHub

Generate a dedicated deploy key:

```bash
ssh-keygen -t ed25519 -C "cicd@auto-ai-cluster" -f ~/.ssh/cicd_deploy_key -N ""
```

Add the **public key** to VPS `~/.ssh/authorized_keys`:

```bash
cat ~/.ssh/cicd_deploy_key.pub >> ~/.ssh/authorized_keys
```

Add the **private key** to GitHub Secrets:

| Secret Name | Value |
|-------------|-------|
| `VPS_SSH_KEY` | Full private key content |
| `VPS_HOST` | Your VPS IP or domain |
| `VPS_USER` | `root` or your sudo user |
| `VPS_PORT` | `22` (or custom SSH port) |

Clean up your local copy:

```bash
rm ~/.ssh/cicd_deploy_key*
```

## Step 3: The CI/CD Workflow

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy AI Cluster

on:
  push:
    branches: [main]
    paths-ignore:
      - 'docs/**'
      - 'README.md'
      - '**.md'
  workflow_dispatch:  # Manual trigger

env:
  COMPOSE_FILE: docker-compose.yml
  DEPLOY_DIR: /opt/auto-ai-cluster
  HEALTH_RETRIES: 30
  HEALTH_INTERVAL: 5  # seconds

jobs:
  deploy:
    runs-on: ubuntu-latest
    timeout-minutes: 15

    steps:
      - name: Checkout Repository
        uses: actions/checkout@v4

      - name: Validate docker-compose.yml
        run: |
          docker compose config > /dev/null
          echo "✅ docker-compose.yml is valid"

      - name: Setup SSH Connection
        uses: webfactory/ssh-agent@v0.9.0
        with:
          ssh-private-key: ${{ secrets.VPS_SSH_KEY }}

      - name: Add VPS to known_hosts
        run: |
          ssh-keyscan -p ${{ secrets.VPS_PORT || 22 }} \
            ${{ secrets.VPS_HOST }} >> ~/.ssh/known_hosts

      - name: Sync Files to VPS
        run: |
          rsync -avz --delete \
            -e "ssh -p ${{ secrets.VPS_PORT || 22 }}" \
            --exclude '.git' \
            --exclude '.github' \
            --exclude 'docs' \
            --exclude 'node_modules' \
            --exclude '.env' \
            ./ \
            ${{ secrets.VPS_USER }}@${{ secrets.VPS_HOST }}:${{ env.DEPLOY_DIR }}/

      - name: Deploy with Zero Downtime
        run: |
          ssh -p ${{ secrets.VPS_PORT || 22 }} \
            ${{ secrets.VPS_USER }}@${{ secrets.VPS_HOST }} \
            "cd ${{ env.DEPLOY_DIR }} && \
             docker compose pull && \
             docker compose up -d --remove-orphans && \
             docker image prune -f"

      - name: Health Check
        run: |
          ssh -p ${{ secrets.VPS_PORT || 22 }} \
            ${{ secrets.VPS_USER }}@${{ secrets.VPS_HOST }} \
            "cd ${{ env.DEPLOY_DIR }} && \
             chmod +x scripts/health-check.sh && \
             ./scripts/health-check.sh"
```

## Step 4: Health Check Script

Create `scripts/health-check.sh`:

```bash
#!/bin/bash
# health-check.sh — Verify all services are running after deploy

set -euo pipefail

DEPLOY_DIR="${DEPLOY_DIR:-/opt/auto-ai-cluster}"
MAX_RETRIES="${HEALTH_RETRIES:-30}"
SLEEP_SEC="${HEALTH_INTERVAL:-5}"

declare -A SERVICES=(
  ["n8n"]     "http://localhost:5678/healthz"
  ["postgres"] "pg_isready -U n8n -d n8n"
  ["ai-gateway"] "http://localhost:3456/health"
)

echo "=== Post-Deploy Health Check ==="
echo "Started at: $(date -u '+%Y-%m-%dT%H:%M:%SZ')"

cd "$DEPLOY_DIR"

for SERVICE in "${!SERVICES[@]}"; do
  CHECK="${SERVICES[$SERVICE]}"
  echo -n "Checking $SERVICE ... "
  RETRIES=0
  OK=false

  while [ $RETRIES -lt $MAX_RETRIES ]; do
    if eval "$CHECK" > /dev/null 2>&1; then
      OK=true
      break
    fi
    RETRIES=$((RETRIES + 1))
    sleep "$SLEEP_SEC"
  done

  if [ "$OK" = true ]; then
    echo "✅ (alive after ${RETRIES}s)"
  else
    echo "❌ FAILED after ${MAX_RETRIES} retries"
    docker compose logs --tail=20 "$SERVICE"
    exit 1
  fi
done

echo "=== All services healthy ==="
docker compose ps
```

Make it executable:

```bash
chmod +x scripts/health-check.sh
```

## Step 5: Rollback Script

Create `scripts/rollback.sh`:

```bash
#!/bin/bash
# rollback.sh — Revert to previous Docker Compose state

set -euo pipefail

DEPLOY_DIR="${DEPLOY_DIR:-/opt/auto-ai-cluster}"
ROLLBACK_BRANCH="${1:-HEAD~1}"

cd "$DEPLOY_DIR"

echo "=== Emergency Rollback ==="
echo "Rolling back to: $ROLLBACK_BRANCH"
echo "Current state:"
git log --oneline -3

git stash
git checkout "$ROLLBACK_BRANCH"

docker compose pull
docker compose up -d --remove-orphans

echo "Rollback complete. Running health check..."
bash scripts/health-check.sh
```

## Step 6: Zero-Downtime Trick — Graceful Container Swap

The key insight: Docker Compose's `up -d` replaces containers one at a time when `docker-compose.yml` uses explicit container names and `depends_on`. But for **true zero-downtime**, add this to your n8n service:

```yaml
services:
  n8n:
    image: n8nio/n8n:latest
    restart: unless-stopped
    ports:
      - "127.0.0.1:5678:5678"
    healthcheck:
      test: ["CMD", "node", "-e", "require('http').get('http://localhost:5678/healthz',r=>process.exit(r.statusCode===200?0:1))"]
      interval: 10s
      timeout: 5s
      retries: 3
      start_period: 20s
    stop_grace_period: 30s
    stop_signal: SIGTERM
```

The critical setting is **`stop_grace_period: 30s`**. This gives n8n 30 seconds to finish in-flight requests before being killed. Combined with `restart: unless-stopped` and healthchecks, new n8n containers become healthy before the old ones are fully removed.

## Step 7: Test It

Test locally first:

```bash
# Dry-run the workflow locally
docker compose config > /dev/null && echo "✅ Config valid"
bash scripts/health-check.sh
```

Then trigger a real deploy:

```bash
git add .
git commit -m "feat: add CI/CD pipeline for zero-downtime deployment"
git push origin main
```

Watch it in real-time:

```bash
# On the VPS, tail the deploy log
journalctl -u docker -f
```

## Resource Cost on 2C4G

| Component | RAM | CPU | Notes |
|-----------|:---:|:---:|-------|
| GitHub Actions runner | 0 MB | 0% | Runs on GitHub, not your VPS |
| SSH session (active) | ~2 MB | <1% | Only during deploy |
| Docker image prune | ~50 MB temp | 5-10% | Runs once, cleans old images |
| **Total during deploy** | **~52 MB** | **5-10%** | Temporary spike, then drops |
| **Normal operation** | **0 MB** | **0%** | Zero ongoing overhead |

**The CI/CD pipeline costs you nothing on the VPS when it's not actively deploying.** No monitoring agent, no runner daemon, no Kubernetes control plane — just SSH when you push.

## Production Checklist

- [ ] **Branch protection** on `main` — require PR reviews before merge
- [ ] **Staging environment** — deploy to a staging VPS first, then production
- [ ] **Database backups** — `pg_dump` before each deploy, keep last 7 days
- [ ] **Slack/Telegram notifications** — add a webhook step after health check
- [ ] **.env secrets** — never commit to repo; use GitHub Secrets + scp
- [ ] **Lock Docker tags** — use `n8nio/n8n:1.70.0` not `:latest`
- [ ] **Failed deploy detection** — add a cron on VPS that reverts if health check fails

## Why This Beats K8s on 2C4G

Kubernetes on a 2C4G VPS consumes ~1 GB just for the control plane. The GitHub Actions approach uses zero persistent resources. You get:

- **Same GitOps workflow** as K8s
- **Same zero-downtime deploy** pattern
- **Better rollback** (git revert + push)
- **Zero cluster management overhead**
- **Real-time logs** from `docker compose logs -f`

## Integration with Existing Auto-AI-Cluster

This pipeline integrates with everything built in earlier blogs:

| Blog | Integration |
|:-----|:-----------|
| #10 (No K8s) | This is the deployment strategy for that architecture |
| #6 (Healthchecks) | The `healthcheck` in docker-compose powers the CI/CD health check |
| #12 (Telegram Bot) | Add notification hook: deploy success/failure → Telegram |
| #11 (AI Gateway) | Deploy new gateway configs with the pipeline |

## Next Steps

1. Add **automated DB migrations** — backup, migrate, verify, revert on failure
2. Add **canary deployments** — route 10% traffic to a new version first
3. Add **auto-scaling** — trigger GitHub Actions via webhook from a load monitor
4. Set up **scheduled deploys** — weekly `cron` in GitHub Actions to pull latest images

---

*Part of the Auto-AI-Cluster series. Published 2026-07-19. [Source on GitHub.](https://github.com/lu7897859-tech/auto-ai-cluster)*
