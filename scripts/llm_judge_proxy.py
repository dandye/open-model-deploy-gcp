#!/usr/bin/env python3
"""OpenAI-compatible LLM proxy for SkillEvaluator backed by Vertex AI Gemini."""

import os
import sys
import time
from typing import Any, Dict, List, Optional
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import litellm

# Configure Vertex AI
os.environ["VERTEXAI_PROJECT"] = os.environ.get("VERTEXAI_PROJECT", "secops-demo-env")
os.environ["VERTEXAI_LOCATION"] = os.environ.get("VERTEXAI_LOCATION", "us-central1")
if "GOOGLE_APPLICATION_CREDENTIALS" not in os.environ:
    sa_key = os.path.expanduser("~/.config/gcloud/secops-demo-env-sa-key.json")
    if os.path.exists(sa_key):
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = sa_key

app = FastAPI(title="SkillEvaluator Judge Proxy")

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/v1/models")
def list_models():
    return {
        "object": "list",
        "data": [
            {"id": "vertex_ai/gemini-2.5-flash", "object": "model"},
            {"id": "claude-3-5-sonnet-20241022", "object": "model"}
        ]
    }

@app.post("/v1/chat/completions")
@app.post("/chat/completions")
async def chat_completions(request: Request):
    payload = await request.json()
    model = payload.get("model", "vertex_ai/gemini-2.5-flash")
    if not model.startswith("vertex_ai/"):
        target_model = "vertex_ai/gemini-2.5-flash"
    else:
        target_model = model
    
    messages = payload.get("messages", [])
    temperature = payload.get("temperature", 0.0)
    max_tokens = payload.get("max_tokens")

    try:
        response = litellm.completion(
            model=target_model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.model_dump()
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
