# SPEC-004: AI API Gateway Protocol

**Status:** PROPOSED STANDARD | **Series:** Auto-AI-Cluster | **Date:** 2026-07-19

## Request
POST /v1/chat { messages, preferences: { max_cost, preferred_provider, fallback_ok } }

## Response
{ provider, content, cost, latency_ms, model }

## Circuit Breaker
CLOSED -> (3 failures/30s) -> OPEN -> (30s) -> HALF_OPEN -> (1 success) -> CLOSED

## Cost Matrix
Chat: DeepSeek($0.14/M) -> OLLAMA(free)
Code: OpenAI($1.50/M) -> DeepSeek($0.14/M)
Batch: OLLAMA(free) -> DeepSeek

## References
- SPEC-001, SPEC-002, SPEC-003
- https://lu7897859-tech.github.io/auto-ai-cluster/
