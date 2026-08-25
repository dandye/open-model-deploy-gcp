
# Managed vs Deployed

Google provides hosted, serverless access to Gemma models through both the **Gemini API (via Google AI Studio)** and **Gemini Enterprise Agent Platform (Model as a Service)**.

---

## Managed Access Options for Gemma Models

| Hosting Access Method | Key Features | Supported Models | Authentication & Interface | Sources |
|---|---|---|---|---|
| **Gemini API (Google AI Studio)** | Hosted serverless API for developers, rapid prototyping, and pay-per-token usage. | Gemma 4 31B IT (`gemma-4-31b-it`), Gemma 4 26B (`gemma-4-26b-a4b-it`) | API Key authentication via `google-genai` SDK or `generativelanguage.googleapis.com`. | |
| **Model as a Service (Gemini Enterprise Agent Platform)** | Serverless enterprise API with Google Cloud governance, global endpoints, and no infrastructure management. | Gemma 4 26B A4B IT (`gemma-4-26b-a4b-it-maas`) | Google Cloud IAM service account authentication via global REST or SDK endpoints. | |

---

## Code Example: Using Gemma via the Gemini API SDK

You can call supported Gemma models using the unified `google-genai` SDK in the same manner as Gemini models:

```python
from google import genai

client = genai.Client()

# Generate content directly using a hosted Gemma model
response = client.models.generate_content(
    model="gemma-4-26b-a4b-it",
    contents="Explain best practices for cloud security."
)

print(response.text)
```

---

## Comparison: Managed API vs. Self-Deployed Endpoints

| Capability / Feature | Hosted Managed API (No Deployment) | Self-Deployed Endpoint (GKE / Cloud Run / Model Garden) |
|---|---|---|
| **Infrastructure Management** | Fully managed by Google; zero server or GPU provisioning. | User-managed GPU or TPU infrastructure. |
| **Billing Model** | Pay-as-you-go per token. | Pay for reserved hourly accelerator uptime (GPUs/TPUs). |
| **Customization** | Standard base models with prompt engineering and thinking level controls. | Custom fine-tuned weights, LoRA adapters, and custom serving runtimes (vLLM, Ollama, MaxText). |
| **Deployment Time** | Instant access using an API key or IAM credentials. | Requires container creation, model weight downloading, and pod warming. |