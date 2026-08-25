# Gemma ADK Agent (Vertex AI Agent Engine)

This directory provides an Agent Development Kit (ADK) compatible agent designed for deployment to **Vertex AI Agent Engine (Reasoning Engines)** that dynamically connects to Google Gemma model backends.

---

## 1. Key Features & Architecture

* **Dynamic Backend Resolution**:
  * **Auto-Discovery**: Automatically discovers live Gemma endpoints across GCP regions (`us-central1`, `us-east1`, `us-west1`), ensuring seamless connectivity even during frequent deployment and teardown cycles.
  * **Vertex AI Dedicated GPU Endpoints**: Connects to active Model Garden vLLM endpoints via standard prediction APIs.
  * **Cloud Run Serverless GPU**: Connects to Cloud Run scale-to-zero microservices via OpenAI-compatible chat endpoints.
  * **Hosted Model-as-a-Service**: Seamless fallback to Google AI Studio / Gemini API hosted Gemma models.
* **Agent Engine Ready**: Fully compatible with `vertexai.preview.reasoning_engines` serialization and execution protocols.
* **Function Calling & Tools**: Includes built-in utilities (calculation, time) and extensible custom tool interfaces.

---

## 2. Directory Layout

* [`agent/gemma_agent.py`](gemma_agent.py): Core ADK Agent implementation with discovery logic.
* [`agent/deploy.py`](deploy.py): Packaging and deployment automation for Vertex AI Agent Engine.
* [`agent/test_agent.py`](test_agent.py): Local and remote testing CLI runner.
* [`agent/requirements.txt`](requirements.txt): Runtime dependencies for Agent Engine cloud containers.

---

## 3. Usage & Commands

### Test Locally (Auto-Discovering Active Gemma Endpoints)
```bash
python3 agent/test_agent.py "What are the three laws of robotics?"
```

### Test with Specific Endpoint or Cloud Run URL
```bash
# Specific Vertex AI Endpoint
python3 agent/test_agent.py --endpoint="7432316523475107840" --region="us-central1" "Hello Gemma!"

# Specific Cloud Run URL
python3 agent/test_agent.py --cloudrun-url="https://gemma-2-9b-it-xxxxx-uc.a.run.app" "Hello Gemma!"
```

### Deploy to Vertex AI Agent Engine
```bash
just agent-deploy
# Or run directly:
python3 agent/deploy.py
```
