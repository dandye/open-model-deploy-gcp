"""Gemma-Powered ADK Agent for Vertex AI Agent Engine.

This agent connects dynamically to self-deployed Gemma endpoints (Vertex AI Online
Prediction or Cloud Run with GPU) or hosted Gemini API / MaaS models. It supports
auto-discovering active endpoints to gracefully handle rapid deployment & teardown cycles.
"""

from typing import Any, Callable, Dict, List, Optional
import os
import json
import requests
import google.auth
import google.auth.transport.requests
from google.cloud import aiplatform


def get_current_time() -> str:
    """Returns the current UTC date and time."""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def calculate(expression: str) -> str:
    """Safely evaluates basic mathematical expressions.
    
    Args:
        expression: Mathematical expression (e.g. '24 * 1024 / 4').
    """
    try:
        # Safe eval using restricted globals/locals
        allowed_chars = set("0123456789+-*/(). %")
        if not all(c in allowed_chars for c in expression):
            return "Error: Expression contains disallowed characters."
        result = eval(expression, {"__builtins__": None}, {})
        return str(result)
    except Exception as e:
        return f"Calculation error: {e}"


class GemmaAgent:
    """Agent Engine compatible Agent powered by configurable Gemma backends."""

    def __init__(
        self,
        project_id: Optional[str] = None,
        region: str = "us-central1",
        endpoint_id: Optional[str] = None,
        cloudrun_url: Optional[str] = None,
        managed_model: Optional[str] = None,
        system_instruction: Optional[str] = None,
        tools: Optional[List[Callable]] = None,
    ):
        """Initializes the GemmaAgent.

        Args:
            project_id: GCP project ID (defaults to ADC or environment).
            region: GCP region for Vertex AI endpoints.
            endpoint_id: Optional numeric Vertex AI Endpoint ID.
            cloudrun_url: Optional Cloud Run HTTPS service URL.
            managed_model: Optional hosted Gemma model name (e.g. 'gemma-4-26b-a4b-it').
            system_instruction: Custom system persona and instruction.
            tools: Optional list of Python callables for function calling.
        """
        self.project_id = project_id or os.environ.get("GCP_PROJECT_ID", "dandye-0324-chronicle")
        self.region = region
        self.endpoint_id = endpoint_id
        self.cloudrun_url = cloudrun_url
        self.managed_model = managed_model
        self.system_instruction = system_instruction or (
            "You are an AI assistant powered by Google Gemma models on Google Cloud Platform. "
            "Provide concise, factually grounded, and helpful answers."
        )
        self.tools = tools or [get_current_time, calculate]
        self._auth_credentials = None
        self._auth_request = None

    def set_up(self) -> None:
        """Called automatically when initialized on Vertex AI Agent Engine."""
        aiplatform.init(project=self.project_id, location=self.region)
        self._auth_credentials, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        self._auth_request = google.auth.transport.requests.Request()

    def _get_token(self) -> str:
        """Retrieves a fresh OAuth2 Bearer token."""
        if self._auth_credentials is None or self._auth_request is None:
            self.set_up()
        if not self._auth_credentials.valid:
            self._auth_credentials.refresh(self._auth_request)
        return self._auth_credentials.token

    def discover_active_vertex_endpoint(self) -> Optional[Dict[str, str]]:
        """Auto-discovers any currently active Gemma endpoint across standard regions."""
        regions_to_scan = [self.region, "us-central1", "us-east1", "us-west1"]
        seen_regions = set()

        for reg in regions_to_scan:
            if reg in seen_regions:
                continue
            seen_regions.add(reg)
            try:
                endpoints = aiplatform.Endpoint.list(
                    project=self.project_id,
                    location=reg,
                    order_by="create_time desc",
                )
                for ep in endpoints:
                    if ep.deployed_models:
                        return {
                            "endpoint_id": ep.name,
                            "region": reg,
                            "display_name": ep.display_name,
                        }
            except Exception:
                continue
        return None

    def query(self, prompt: str, max_tokens: int = 512, temperature: float = 0.7) -> Dict[str, Any]:
        """Queries the configured or auto-discovered Gemma model backend.

        Args:
            prompt: Input user prompt.
            max_tokens: Maximum generated tokens.
            temperature: Sampling temperature.

        Returns:
            Dictionary containing the generated response, metadata, and active backend.
        """
        token = self._get_token()

        # Strategy 1: Cloud Run URL
        if self.cloudrun_url:
            url = f"{self.cloudrun_url.rstrip('/')}/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": "gemma",
                "messages": [
                    {"role": "system", "content": self.system_instruction},
                    {"role": "user", "content": prompt},
                ],
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
            resp = requests.post(url, headers=headers, json=payload, timeout=120)
            resp.raise_for_status()
            data = resp.json()
            reply = data["choices"][0]["message"]["content"]
            return {"response": reply, "backend": "Cloud Run GPU", "url": self.cloudrun_url}

        # Strategy 2: Explicit or Auto-Discovered Vertex AI Endpoint
        active_endpoint = self.endpoint_id
        active_region = self.region

        if not active_endpoint:
            discovery = self.discover_active_vertex_endpoint()
            if discovery:
                active_endpoint = discovery["endpoint_id"]
                active_region = discovery["region"]

        if active_endpoint:
            url = (
                f"https://{active_region}-aiplatform.googleapis.com/v1/projects/"
                f"{self.project_id}/locations/{active_region}/endpoints/{active_endpoint}:predict"
            )
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }
            # Standard OpenAI/vLLM format supported by Model Garden containers
            payload = {
                "instances": [
                    {
                        "prompt": f"<start_of_turn>user\n{self.system_instruction}\n\n{prompt}<end_of_turn>\n<start_of_turn>model\n",
                        "max_tokens": max_tokens,
                        "temperature": temperature,
                    }
                ]
            }
            resp = requests.post(url, headers=headers, json=payload, timeout=120)
            resp.raise_for_status()
            data = resp.json()
            predictions = data.get("predictions", [])
            reply = predictions[0] if predictions else "No prediction returned."
            return {
                "response": reply,
                "backend": "Vertex AI Online Prediction",
                "endpoint_id": active_endpoint,
                "region": active_region,
            }

        # Strategy 3: Fallback / Managed Model
        if self.managed_model:
            from google import genai
            client = genai.Client()
            resp = client.models.generate_content(
                model=self.managed_model,
                contents=prompt,
            )
            return {"response": resp.text, "backend": "Managed MaaS / Gemini API", "model": self.managed_model}

        return {
            "error": "No active Gemma endpoint found and no managed model configured. Deploy a model with 'just vertex-deploy <flavor>' or specify an endpoint ID.",
            "backend": "None",
        }
