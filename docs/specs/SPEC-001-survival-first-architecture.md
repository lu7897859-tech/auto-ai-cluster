# SPEC-001: Survival-First Architecture for Autonomous AI Clusters

**Status:** PROPOSED STANDARD
**Series:** Auto-AI-Cluster Specification
**Date:** 2026-07-19
**Source:** https://lu7897859-tech.github.io/auto-ai-cluster/

## Abstract

This specification defines a survival-first architecture pattern for deploying autonomous AI agent clusters on resource-constrained infrastructure (minimum 2 CPU cores, 4 GB RAM).

## 1. Design Constraints

| Resource | Budget | Allocation |
|----------|--------|------------|
| CPU | 2 cores | n8n(0.5) + PG(0.5) + auth(0.1) + AI gateway(0.1) + overhead(0.8) |
| RAM | 4 GB | n8n(512MB) + PG(1GB) + auth(128MB) + AI gateway(128MB) + OS(1.5GB) + buffer |
| Storage | 20 GB | OS(5GB) + Docker images(3GB) + PG data(2GB) + logs(1GB) + swap(4GB) |

## 2. Failure Model

n8n Crash: Stateless containers, Docker restart + healthcheck, RPO=0 RTO<30s
PG Failure: Patroni HA, auto-failover <15s, etcd split-brain prevention
Internet Outage: OLLAMA local fallback, auto-detected by AI gateway

## 3. Security Model
RSA-4096 challenge-response. Auth agent validates before premium workflows.

## 4. References
- SPEC-002: n8n Hardening
- SPEC-003: PG HA on 2C4G
- SPEC-004: AI Gateway Protocol
- Form-A: https://lu7897859-tech.github.io/auto-ai-cluster/
- Form-B: https://lu7897859-tech.github.io/auto-ai-cluster/product.html
