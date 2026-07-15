# Auto-AI-Cluster · Western Marketing Kit

> Zero-cost distribution to US/EU engineering audience — push to Reddit, HN, Twitter/X, Product Hunt, Lobsters, Dev.to

---

## 📍 One Link to Rule Them All

**Main link (put this everywhere):**
→ https://github.com/lu7897859-tech/auto-ai-cluster

**Direct white paper download:**
→ https://github.com/lu7897859-tech/auto-ai-cluster/releases/download/v1.0.0/Form-B-Architecture-Paper.pdf

**Project page:**
→ https://lu7897859-tech.github.io/auto-ai-cluster/

---

## 🎯 Positioning

**Nail the elevator pitch. Everything you write should hit 2-3 of these:**

- ✅ 2C4G constraint → extreme engineering discipline
- ✅ n8n as the core → lightweight, Python-powered workflow engine
- ✅ From zero to production → white paper + deployable code
- ✅ "Survival-first" architecture → anti-fragile design
- ✅ **Free white paper** ($399 value, free download)
- ✅ AGPLv3 → no source-code-level copyleft trap for business users

---

## 💬 Platform Posts (Copy-Paste Ready)

### Hacker News

**Title:** I built an autonomous AI cluster that runs on 2 vCPUs and 4GB RAM

**Body:**
After hitting the wall with bloated AI infrastructure (Kubernetes clusters costing thousands just to run n8n + a couple of models), I decided to ask: what's the minimum viable AI cluster?

Turns out, with the right engineering choices, you can run a full production-grade autonomous AI cluster on 2 vCPUs and 4GB RAM.

What's inside:
- n8n (workflow engine) — chosen over Airflow, Prefect, and Temporal after systematic comparison
- PostgreSQL + Redis
- AI-API gateway with 3-layer audit
- RSA-2048 authorization server with machine fingerprint binding (998 LOC, all 6 endpoints tested)
- Nginx reverse proxy + pgAdmin

The full white paper (11 chapters) walks through every decision: why n8n won, how to allocate resources under 2C4G, the survival-first circuit breaker pattern, and a complete reimplementation roadmap if you want to rebuild from scratch.

Everything is open source (AGPLv3). White paper is free.

GitHub: https://github.com/lu7897859-tech/auto-ai-cluster
PDF: https://github.com/lu7897859-tech/auto-ai-cluster/releases/download/v1.0.0/Form-B-Architecture-Paper.pdf

TL;DR — engineering constraints produce better designs. 2C4G forced me to make every service do exactly one thing. No bloat allowed.

---

### Reddit r/selfhosted

**Title:** Auto-AI-Cluster: self-hosted n8n + PostgreSQL + AI gateway running on a 2C4G VPS

**Body:**
I built a complete autonomous AI cluster that self-hosts on a $5/mo VPS. 7 Docker services: n8n, PostgreSQL, Redis, Nginx, AI-API gateway, authorization server, and pgAdmin. One `bash deploy.sh` to start.

Key decisions documented in the white paper:
- Why n8n over Airflow/Prefect/Temporal
- 2C4G resource budgeting (with actual numbers)
- Circuit breaker pattern for resource contention
- From docker-compose to K8s migration path

Everything is AGPLv3, white paper is free.

https://github.com/lu7897859-tech/auto-ai-cluster

---

### Reddit r/devops

**Title:** We need to talk about the elephant in the room: AI infrastructure bloat

**Body:**
I see teams spinning up 8C32G Kubernetes clusters just to run a few n8n workflows and some LLM API calls. The cloud bill is $500+/mo before anyone even has a user.

I went the other direction. Built the same thing on 2C4G.

The engineering discipline this forces is actually valuable:
1. Each service has a hard resource limit — no "let's just add another microservice"
2. Circuit breaker releases non-critical services first (n8n and PG *never* go down)
3. Every architecture decision is documented against a $5/mo VPS constraint

White paper covers the full architecture, engine selection, security audit layers, and the "minimal logic principle" — if it doesn't fit on one A4 page, it's too complex.

Free download: https://github.com/lu7897859-tech/auto-ai-cluster/releases/download/v1.0.0/Form-B-Architecture-Paper.pdf
Source code: https://github.com/lu7897859-tech/auto-ai-cluster

---

### Reddit r/AI_Agents

**Title:** My "survival-first" architecture for running autonomous AI agents on a budget

**Body:**
I've been building an autonomous AI agent system and hit a fundamental question: how do you design for reliability when your entire infrastructure budget is a $5/mo VPS?

My solution has three layers:
1. **n8n** as the workflow engine — super lightweight, Python-native, trivial to containerize
2. **AI-API gateway** — 3-layer audit (inbound validation → content filter → rate limiter) so the LLM API calls don't bleed you dry
3. **Authorization server** — RSA-2048 + machine fingerprint binding, so you can distribute and track deployments

Everything is documented in the free white paper including 7 ready-to-use AI prompt templates.

https://github.com/lu7897859-tech/auto-ai-cluster

---

### Twitter/X Thread

**Tweet 1:**
Most AI infrastructure is over-engineered garbage. You do NOT need an 8C32G K8s cluster to run n8n + PostgreSQL.

I built the same thing on 2C4G. Here's how. 🧵

**Tweet 2:**
The trick: engineering constraints. When you only have 2 vCPUs and 4GB RAM, every service MUST justify its existence. No "let's add it just in case."

Result: 7 services, each doing exactly one thing.

**Tweet 3:**
Engine selection is everything:
- n8n (not Airflow/Prefect/Temporal) — full comparison in the white paper
- PostgreSQL + Redis — boring tech that just works
- Nginx — you already know it

**Tweet 4:**
The "survival-first" circuit breaker:
- Priority 1: n8n + PostgreSQL — NEVER go down
- Priority 2: Redis cache — graceful degradation
- Priority 3: AI gateway — rate limit, then queue, then fail open
- Priority 4: Monitoring tools — nice to have

**Tweet 5:**
Also included: RSA-2048 authorization server (998 LOC, all endpoints tested), so you can distribute this as a product with license enforcement.

**Tweet 6:**
Full white paper (11 chapters) + open source code here:
https://github.com/lu7897859-tech/auto-ai-cluster

White paper PDF direct download:
https://github.com/lu7897859-tech/auto-ai-cluster/releases/download/v1.0.0/Form-B-Architecture-Paper.pdf

**Tweet 7:**
AGPLv3 licensed. Using the API without modifying the source code? No copyleft issues.

Built for engineers who think in constraints. Enjoy.

---

### Product Hunt

**Tagline:** Production-grade autonomous AI cluster that runs on a $5/mo VPS

**Description:**
Auto-AI-Cluster is a complete, production-ready autonomous AI cluster designed for extreme resource efficiency.

What you get:
• 7 Docker services (n8n, PostgreSQL, Redis, Nginx, AI-API gateway, authorization server, pgAdmin)
• One-command deploy: `bash deploy.sh`
• RSA-2048 authorization system for commercial distribution
• 11-chapter architecture white paper (free download)
• Complete K8s migration path for scaling up

Built on the "survival-first" principle — every component has a hard resource limit, and a circuit breaker ensures core services never collapse under load.

GitHub: https://github.com/lu7897859-tech/auto-ai-cluster

---

## 📊 Channel Strategy

| Channel | Post Type | Best Time (ET) | Expected Reach |
|---------|-----------|----------------|----------------|
| **Hacker News** | Story with technical depth | Mon-Thu 8-10am ET | 500-5k views if frontpage |
| **Reddit r/devops** | Discussion post | Tue-Thu 10am-2pm ET | 1k-10k views |
| **Reddit r/selfhosted** | Project showcase | Any day, 12-3pm ET | 2k-20k views |
| **Reddit r/AI_Agents** | Technical deep-dive | Mon-Wed 9am-12pm ET | 500-5k views |
| **Twitter/X** | Thread (7 tweets) | Tue-Thu 8-10am ET | Varies |
| **Product Hunt** | Launch | Mon-Fri 12:01am ET | 500-5k views |
| **Lobste.rs** | Link post | Mon-Fri 9am-12pm ET | 200-2k views |
| **Dev.to** | Full article | Tue-Thu 8-10am ET | 1k-5k views |

---

## 💰 Monetization Flow (Non-Chinese Market)

Unlike the Chinese market (WeChat transfer), Western users expect:

### For the White Paper ($0)
- It's free. No paywall. That's the funnel.
- The white paper is the **lead magnet**.

### For Community Edition ($0)
- AGPLv3, free, on GitHub.
- Users pull, deploy, use it.
- **When they need commercial support → that's the conversion.**

### For Enterprise Edition ($6,800)
- Kubernetes Helm Chart deployment
- Patroni HA PostgreSQL
- EFK logging stack
- Enterprise authorization integration
- SLAs, priority support

### For Distributor/Reseller (15-20% commission)
- White paper: $60/sale (if pricing at $399)
- Enterprise: $1,020-$1,360/sale
- Ideal partners: DevOps consultancies, cloud service providers, AI integration shops

### Payment Options
- **Buy Me a Coffee** / **Ko-fi** — zero setup, tips/donations
- **Gumroad** — sell the enterprise license PDF, handles payments
- **GitHub Sponsors** — recurring revenue
- **PayPal / Stripe** — direct invoices for enterprise

**Recommended immediate: set up a Ko-fi → put the link in the GitHub repo README**

---

## ⚡ What You Need to Do (from your end)

1. Post the HN/Reddit threads (I wrote them above, just copy-paste)
2. Create a Twitter account for this project → post the thread
3. Set up Ko-fi or Gumroad → add payment link to GitHub README
4. That's it. The rest is watching GitHub stars and waiting for inbound leads.

---

*The West respects engineering depth. Lead with technical decisions, not marketing fluff. This project was born from constraints — that's a story that resonates with real engineers.*
