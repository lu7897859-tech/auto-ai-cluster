# 15 — Rate Limiting & API Security for Your 2C4G AI Cluster

**2026-07-21** | 2C4G AI Cluster Series

When you expose any service to the internet on a $5 VPS, you will get hammered. Automated bots, credential stuffing, and runaway loops from misconfigured agents — all will find your endpoint within hours of going live.

This post covers three layers of defense you can implement on a 2C4G VPS without spending extra money or adding meaningful latency.

---

## 1. Nginx Rate Limiting

The simplest first line of defense lives in your reverse proxy. Nginx's `limit_req_zone` creates a shared memory zone to track request rates per key (IP, API key, etc.).

```nginx
# /etc/nginx/conf.d/ratelimit.conf

# Define a zone: 10MB shared memory, 1 request per second burst to 5
limit_req_zone $binary_remote_addr zone=ip_limit:10m rate=1r/s;

# More generous for authenticated API calls
limit_req_zone $http_x_api_key zone=api_limit:10m rate=10r/s;

server {
    # Apply to unauthenticated endpoints
    location /n8n/ {
        limit_req zone=ip_limit burst=5 nodelay;
        proxy_pass http://127.0.0.1:5678;
    }

    # Apply to AI gateway
    location /api/ {
        limit_req zone=api_limit burst=20 nodelay;
        proxy_pass http://127.0.0.1:3000;
    }
}
```

Key parameters:
- `rate=1r/s` = 1 request per second per IP
- `burst=5` = allow 5 queued requests if burst exceeded
- `nodelay` = don't slow down, just reject excess immediately

Test it:

```bash
# 10 rapid requests — most should get 503
for i in {1..10}; do curl -s -o /dev/null -w "%{http_code}\n" http://your-vps/n8n/; done
```

---

## 2. Fail2Ban: Automated IP Banning

Fail2Ban watches your Nginx logs and bans IPs that repeatedly trigger 429/503 errors or search for exploit patterns.

```bash
# Install
apt install fail2ban -y
```

Create `/etc/fail2ban/jail.local`:

```ini
[nginx-429]
enabled  = true
port     = http,https
filter   = nginx-429
logpath  = /var/log/nginx/access.log
maxretry = 20
findtime = 60
bantime  = 3600

[nginx-noscript]
enabled  = true
port     = http,https
filter   = nginx-noscript
logpath  = /var/log/nginx/access.log
maxretry = 3
findtime = 600
bantime  = 86400
```

```bash
systemctl enable fail2ban
systemctl start fail2ban
fail2ban-client status
```

Check who got banned:

```bash
fail2ban-client status nginx-429
```

On a fresh VPS exposed to the internet, you will be surprised how fast the bans accumulate.

---

## 3. API Key Authentication Layer

For your AI gateway or n8n webhook, add a simple API key check at the Nginx level before requests ever reach your application:

```nginx
location /api/v1/ {
    # Reject requests without the X-API-Key header
    if ($http_x_api_key = "") {
        return 401;
    }

    # Reject requests with wrong key
    if ($http_x_api_key != "your-secret-key-here") {
        return 403;
    }

    limit_req zone=api_limit burst=20 nodelay;
    proxy_pass http://127.0.0.1:3000;
}
```

For multiple tenants, use a map:

```nginx
map $http_x_api_key $allowed_ips {
    default                      "";
    "tenant-a-key"              "10.0.0.0/8,172.16.0.0/12";
    "tenant-b-key"              "192.168.0.0/16";
}
```

---

## 4. Docker-Level Resource Guardrails

Even if an attacker gets through your network layer, container memory limits prevent one container from consuming your entire 4 GB RAM:

```yaml
# docker-compose.yml — always set these
services:
  n8n:
    deploy:
      resources:
        limits:
          memory: 512M
        reservations:
          memory: 256M

  ai-gateway:
    deploy:
      resources:
        limits:
          memory: 1024M

  postgres:
    deploy:
      resources:
        limits:
          memory: 512M
```

With 512 MB for Postgres, 512 MB for n8n, and 1024 MB for your AI gateway, you have 2 GB headroom for the OS, Nginx, and应急.

---

## 5. Monitoring Your Attack Surface

Add this to your Prometheus scrape config to alert when ban counts spike (attack underway):

```yaml
scrape_configs:
  - job_name: 'fail2ban'
    static_configs:
      - targets: ['localhost:9101']
```

A spike in `fail2ban_banned_total` is often your earliest signal that an automated attack is in progress.

---

## Putting It Together

```
Internet → Nginx (rate limit) → Fail2Ban (ban after abuse)
                                      ↓
                            Docker (memory limits)
                                      ↓
                            Your App (API key auth)
```

On a 2C4G VPS this whole stack uses under 50 MB RAM. The defense-in-depth approach means no single layer is relied upon to stop everything.

Configure rate limits generously enough that real users and legitimate automated agents don't hit them, but tightly enough that credential stuffing and enumeration attacks die fast.

---

*Part of the [Auto-AI-Cluster](https://github.com/lu7897859-tech/auto-ai-cluster) series. Deploy resilient, affordable AI infrastructure — one post at a time.*
