# 22 — Self-Hosted Vector Database on 2C4G: Semantic Search Without Cloud Lock-in

**2026-08-03**

Vector databases are the backbone of AI applications—RAG, semantic search, recommendation systems. But Pinecone, Weaviate Cloud, and Zilliz all charge per-GB and lock you into their APIs. If you're running a 2C4G VPS, you don't need cloud-managed vectors. You need **Qdrant or Chroma in a container**.

## Why Self-Hosted Vector DB on 2C4G Works

**Memory is cheap.** A 4GB VPS can hold millions of vectors if you're smart about quantization.

**Latency matters more than RAM.** Local vector search is 10-50x faster than cloud APIs for batch queries.

**No API keys to rotate.** No rate limits. No egress fees.

**The trade-off**: You trade managed backups and infinite scaling for operational simplicity and cost predictability. On a 2C4G box, that's the right trade.

## The Candidates: Qdrant vs Chroma vs Milvus Lite

| Feature | Qdrant | Chroma | Milvus Lite |
|---------|--------|--------|-------------|
| Min RAM | 512MB | 256MB | 1GB |
| Docker image size | 150MB | 180MB | 400MB+ |
| Quantization | Scalar, Product | None | Scalar |
| API | REST + gRPC | REST | REST |
| License | Apache 2.0 | Apache 2.0 | Apache 2.0 |
| Best for | Production 2C4G | Dev/prototyping | Embedded ML |

**Winner for 2C4G**: Qdrant with scalar quantization. You get 4x compression with <5% recall loss, and the container idles at ~200MB RAM.

## Docker Compose Setup for Qdrant on 2C4G

```yaml
# docker-compose.vector.yml
version: "3.8"
services:
  qdrant:
    image: qdrant/qdrant:latest
    container_name: qdrant
    restart: unless-stopped
    ports:
      - "6333:6333"  # REST API
      - "6334:6334"  # gRPC API
    volumes:
      - qdrant_storage:/qdrant/storage
    environment:
      - QDRANT__STORAGE__SNAPSHOTS_PATH=/qdrant/snapshots
    deploy:
      resources:
        limits:
          memory: 768M  # Hard cap for 2C4G
        reservations:
          memory: 256M  # Minimum guaranteed
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:6333/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s

volumes:
  qdrant_storage:
```

Deploy with:
```bash
docker compose -f docker-compose.vector.yml up -d
```

**Memory budget**: 768MB limit leaves 3GB for n8n, Postgres, and your app stack. If you hit the limit, Qdrant will OOM—but with quantization, you won't.

## Enabling Scalar Quantization

Scalar quantization reduces vector size from 4 bytes (float32) to 1 byte (uint8) per dimension. For a 1536-dim OpenAI embedding, that's 6KB → 1.5KB per vector.

```bash
# Create a collection with quantization enabled
curl -X PUT "http://localhost:6333/collections/ai_docs" \
  -H "Content-Type: application/json" \
  -d '{
    "vectors": {
      "size": 1536,
      "distance": "Cosine",
      "quantization_config": {
        "scalar": {
          "type": "int8",
          "quantile": 0.99,
          "always_ram": true
        }
      }
    }
  }'
```

**Result**: 1M vectors (1536-dim) fits in ~1.5GB RAM instead of 6GB.

## Integrating with n8n Workflows

Your AI agent cluster can now query Qdrant directly via HTTP Request nodes.

### Example: Semantic Document Search Flow

1. **Trigger**: Telegram message with query text
2. **Embed**: Call OpenAI `/embeddings` API (or local embedding model)
3. **Search**: POST to `http://qdrant:6333/collections/ai_docs/points/search`
4. **Respond**: Format top-3 results, reply via Telegram

```json
{
  "vector": [0.012, -0.234, ...],  // 1536 floats from embedding API
  "limit": 3,
  "with_payload": true
}
```

**Latency**: 10-30ms for 100K vectors. Compare to Pinecone's 100-200ms + network overhead.

## Backup Strategy for 2C4G

Qdrant stores vectors in `/qdrant/storage`. Use Docker volume snapshots or the built-in snapshot API:

```bash
# Create snapshot
curl -X POST "http://localhost:6333/collections/ai_docs/snapshots"

# List snapshots
curl "http://localhost:6333/collections/ai_docs/snapshots"

# Download for offsite backup
curl "http://localhost:6333/collections/ai_docs/snapshots/{snapshot_name}" \
  -o snapshot.tar
```

**3-2-1 backup rule**:
- 3 copies: live data + local snapshot + offsite tar
- 2 media: Docker volume + tar file
- 1 offsite: rsync to backup server or S3-compatible bucket

## When to Upgrade from 2C4G

You'll hit the wall when:
- Collection size > 2M vectors (even with quantization)
- Query latency > 500ms (concurrent requests pile up)
- RAM usage > 90% sustained (OOM risk)

**Upgrade path**: Move to a 4C8G VPS ($20/mo) and increase Qdrant's memory limit to 2GB. Or shard collections across multiple 2C4G instances.

## Cost Comparison: Self-Hosted vs Cloud Vector DB

| Option | 1M vectors (1536-dim) | Latency | Features |
|--------|-----------------------|---------|----------|
| Pinecone Starter | $70/mo | 100-200ms | Managed, auto-scaling |
| Weaviate Cloud | $25/mo + usage | 80-150ms | GraphQL, modules |
| Qdrant Cloud | Free tier 1GB | 50-100ms | Same API as self-hosted |
| **Self-hosted Qdrant** | **$5.5/mo (VPS)** | **10-30ms** | Full control, no limits |

**Break-even**: At 500K vectors, self-hosted saves $150-600/year compared to managed services.

## Summary: The 2C4G Vector Stack

- **Engine**: Qdrant with scalar quantization
- **Memory**: 768MB container limit, ~256MB idle
- **Capacity**: 1-2M vectors (1536-dim) on 4GB RAM
- **Latency**: 10-30ms search, local-only
- **Cost**: Included in your $5.5/mo VPS

If you're building an AI agent cluster, semantic search isn't optional—it's infrastructure. And on a 2C4G VPS, Qdrant is the right tool for the job.

---

**Next step**: Add the `docker-compose.vector.yml` to your stack, restart with `docker compose up -d`, and point your n8n HTTP Request nodes at `http://qdrant:6333`. Your cluster now has memory—semantic memory.
