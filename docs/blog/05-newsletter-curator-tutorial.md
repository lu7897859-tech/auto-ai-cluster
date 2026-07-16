# 05 — Zero-to-Hero: Building an AI Newsletter Curator on a $5 VPS

**2026-07-16**

This is a complete tutorial showing how to build an AI-powered newsletter curator using n8n + DeepSeek API on a 2C4G VPS.

## The Workflow
```
Input           → RSS feeds (5 sources)
Processing      → DeepSeek API summarizes each article
Filtering       → Relevance scoring (custom logic)
Formatting      → HTML email template
Delivery        → SMTP to subscribers
Scheduling      → Every morning at 6:00 AM
```

## n8n Workflow Design
```
1. RSS Feed Read → one trigger node
2. Loop Over Items → splitInBatches
3. HTTP Request (DeepSeek API) → summarize in 3 sentences
4. Code Node → relevance scoring
5. IF Node → filter out score < 3
6. HTML Template → format for email
7. Email (SMTP) → send to list
```

## Resource Impact
| Metric | Value |
|--------|-------|
| CPU per run | ~8 seconds |
| Memory per run | ~120MB |
| Time per run | ~45 seconds |
| Cost per run | $0.0003 (DeepSeek API) |
| Frequency | Daily |
| **Monthly cost** | **<$0.01** |

## Why This Matters
This entire system — AI summarization, curation, scheduling, email delivery — runs on infrastructure that costs less than a cup of coffee per month. And it runs **autonomously forever**.

→ [Full source code + docker-compose](https://github.com/lu7897859-tech/auto-ai-cluster)
→ [Read the architecture paper](/auto-ai-cluster/white-paper.html)
