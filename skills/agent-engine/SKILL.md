---
name: agent-engine
description: Dynamic model endpoint discovery, vLLM /v1/models resolution, and retry backoff for ADK agents on Vertex AI Agent Engine.
---

# Vertex AI Agent Engine & ADK Model Resolution

## Core Operational Rules
1. **Dynamic Model ID Resolution:**
   - Do not hardcode internal model identifier assumptions that may fail against vLLM internal naming.
   - Query `/v1/models` on the serving host dynamically to resolve the exact served model identifier (e.g. `google/gemma-3-4b-it`).
2. **Dynamic Endpoint Discovery:**
   - Query Vertex AI API (`gcloud ai endpoints list`) or Cloud Run API (`gcloud run services list`) to resolve active serving URLs.
3. **Resilience & Backoff:**
   - Wrap inference requests with exponential retry backoff for cold starts and status codes 503/429.
