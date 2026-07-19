# Multi-Model AI Gateway: Route Between OpenAI, DeepSeek, and Local LLMs on a 2C4G VPS

**2026-07-17**

Running a single AI model provider is a single point of failure. This guide shows how to build a lightweight AI gateway that routes requests across OpenAI, DeepSeek, and local models based on cost, latency, and availability — all on a 2C4G VPS.

## Why You Need an AI Gateway

If your n8n workflows depend on a single AI provider, you are vulnerable to:

- **API outages**: Provider goes down → your agent stops working
- **Cost spikes**: No fallback to cheaper models when your primary API raises prices
- **Rate limits**: Hitting token caps on popular models mid-workflow
- **Lock-in**: Hard to migrate when a better/cheaper provider emerges

A gateway solves all four with minimal overhead.

## Architecture Overview

The gateway runs as a single Docker container (~25 MB RAM) and exposes a unified API endpoint:

```
Client (n8n) → Gateway (Node.js + express) → Provider 1 (DeepSeek, cheapest, tried first)
                                            → Provider 2 (OpenAI, fallback)
                                            → Provider 3 (Local OLLAMA, last resort)
```

## Implementation

### Docker Compose

```yaml
version: "3.8"
services:
  ai-gateway:
    image: node:20-alpine
    ports:
      - "3002:3002"
    volumes:
      - ./gateway:/app
    working_dir: /app
    command: node server.js
    restart: unless-stopped
    environment:
      - DEEPSEEK_API_KEY=${DEEPSEEK_API_KEY}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      # OLLAMA_HOST is optional — only if running local models
      - OLLAMA_HOST=http://host.docker.internal:11434
    deploy:
      resources:
        limits:
          memory: 128M
```

### Gateway Server (server.js)

```javascript
const express = require('express');
const app = express();
app.use(express.json());

const PROVIDERS = [
  {
    name: 'deepseek',
    priority: 1,
    url: 'https://api.deepseek.com/v1/chat/completions',
    key: process.env.DEEPSEEK_API_KEY,
    maxRetries: 2,
    costPer1kTokens: 0.00014
  },
  {
    name: 'openai',
    priority: 2,
    url: 'https://api.openai.com/v1/chat/completions',
    key: process.env.OPENAI_API_KEY,
    maxRetries: 2,
    costPer1kTokens: 0.0015
  }
];

// Circuit breaker state
const failures = {};
const FAILURE_THRESHOLD = 3;
const COOLDOWN_MS = 30000;

async function tryProvider(provider, messages) {
  const now = Date.now();
  if (failures[provider.name]?.count >= FAILURE_THRESHOLD &&
      now - failures[provider.name].lastFailure < COOLDOWN_MS) {
    console.log(`Circuit open for ${provider.name}, skipping`);
    return null;
  }
  try {
    const res = await fetch(provider.url, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${provider.key}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ model: 'deepseek-chat', messages })
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    failures[provider.name] = { count: 0 };
    return { provider: provider.name, cost: data.usage?.total_tokens * provider.costPer1kTokens, content: data.choices[0].message.content };
  } catch (e) {
    failures[provider.name] = { count: (failures[provider.name]?.count || 0) + 1, lastFailure: Date.now() };
    return null;
  }
}

app.post('/v1/chat', async (req, res) => {
  const sorted = [...PROVIDERS].sort((a, b) => a.priority - b.priority);
  for (const provider of sorted) {
    const result = await tryProvider(provider, req.body.messages);
    if (result) return res.json(result);
  }
  res.status(503).json({ error: 'All providers failed' });
});

app.get('/health', (req, res) => res.json({ status: 'ok', providers: PROVIDERS.length }));
app.listen(3002, () => console.log('AI Gateway on :3002'));
```

### n8n Integration

In your n8n workflow, replace individual AI nodes with an HTTP Request node pointing to your gateway:

- **URL**: `http://localhost:3002/v1/chat`
- **Method**: POST
- **Body**: `{"messages": [{"role":"user","content":"{{ $json.input }}"}] }`
- **Response**: Extract `content` field

## Production Hardening

### Health Check Integration

Add to your docker-compose monitoring stack:

```yaml
healthcheck:
  test: ["CMD", "wget", "-qO-", "http://localhost:3002/health"]
  interval: 30s
  timeout: 5s
  retries: 3
```

### Cost Tracking

The gateway returns `cost` in each response. Log these to a file or Postgres for monthly analysis:

```bash
docker logs ai-gateway 2>&1 | grep "cost:" | awk '{sum+=$NF} END {print "Total cost: $" sum}'
```

### Graceful Degradation

When all cloud providers are down, the gateway falls back to local models via OLLAMA:

```javascript
if (process.env.OLLAMA_HOST) {
  PROVIDERS.push({
    name: 'ollama',
    priority: 3,
    url: `${process.env.OLLAMA_HOST}/api/chat`,
    costPer1kTokens: 0  // Local = free
  });
}
```

## Resource Analysis

| Component | RAM | CPU | Notes |
|-----------|:---:|:---:|-------|
| Gateway container | ~25 MB | <0.1 core | Almost negligible |
| OLLAMA (if used) | ~500 MB | 1 core | Only for fallback |
| **Total overhead** | **25-525 MB** | **<1.1 core** | |

On a 2C4G VPS, the gateway adds 0.6-13% overhead. Enable OLLAMA only when you actually need local fallback.

## Summary

A $0/month self-built AI gateway gives you enterprise-grade provider failover, cost optimization, and freedom from vendor lock-in. The code is ~60 lines and runs on any 2C4G VPS alongside your existing n8n deployment.
