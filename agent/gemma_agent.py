"""Gemma-Powered ADK Agent for Vertex AI Agent Engine.

This agent connects dynamically to self-deployed Gemma endpoints (Vertex AI Online
Prediction or Cloud Run with GPU) or hosted Gemini API / MaaS models. It supports
auto-discovering active endpoints to gracefully handle rapid deployment & teardown cycles.
"""

from typing import Any, Callable, Dict, List, Optional
import os
import sys
import json
import tempfile
import subprocess

os.environ.setdefault("GOOGLE_API_USE_CLIENT_CERTIFICATE", "false")



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

    def set_up(self) -> None:
        """Called automatically when initialized on Vertex AI Agent Engine."""
        pass

    def discover_active_vertex_endpoint(self) -> Optional[Dict[str, str]]:
        """Auto-discovers any currently active Gemma endpoint across standard regions."""
        regions_to_scan = [self.region, "us-central1", "us-east1", "us-west1", "us-east4"]
        seen_regions = set()

        for reg in regions_to_scan:
            if reg in seen_regions:
                continue
            seen_regions.add(reg)
            try:
                from google.cloud import aiplatform
                endpoints = aiplatform.Endpoint.list(
                    filter='display_name="gemma*"',
                    project=self.project_id,
                    location=reg,
                )
                for ep in endpoints:
                    if ep.gca_resource.deployed_models:
                        self.endpoint_id = ep.name
                        self.region = reg
                        return {
                            "endpoint_id": ep.name,
                            "region": reg,
                            "display_name": ep.display_name,
                        }
            except Exception:
                try:
                    cmd = [
                        "gcloud", "ai", "endpoints", "list",
                        f"--region={reg}",
                        f"--project={self.project_id}",
                        "--filter=displayName:gemma*",
                        "--sort-by=~createTime",
                        "--format=value(name.basename(),displayName)",
                    ]
                    res = subprocess.run(cmd, capture_output=True, text=True)
                    if res.returncode == 0 and res.stdout.strip():
                        valid_lines = [
                            l.strip().split(None, 1)
                            for l in res.stdout.splitlines()
                            if l.strip() and not l.strip().startswith("Using endpoint")
                        ]
                        for parts in valid_lines:
                            if not parts or not parts[0].isdigit():
                                continue
                            ep_id = parts[0]
                            display_name = parts[1] if len(parts) > 1 else ep_id
                            self.endpoint_id = ep_id
                            self.region = reg
                            return {
                                "endpoint_id": ep_id,
                                "region": reg,
                                "display_name": display_name,
                            }
                except Exception:
                    pass
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
        # Strategy 1: Cloud Run URL
        if self.cloudrun_url:
            import urllib.request
            token = ""
            try:
                import google.auth
                import google.auth.transport.requests
                credentials, _ = google.auth.default()
                if not credentials.valid:
                    auth_req = google.auth.transport.requests.Request()
                    credentials.refresh(auth_req)
                token = credentials.token or ""
            except Exception:
                try:
                    token_res = subprocess.run(["gcloud", "auth", "print-access-token"], capture_output=True, text=True)
                    token = token_res.stdout.strip()
                except Exception:
                    pass
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
            req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            reply = data["choices"][0]["message"]["content"]
            raw_usage = data.get("usage", {})
            usage = {
                "prompt_tokens": raw_usage.get("prompt_tokens", int(len(prompt.split()) * 1.3)),
                "completion_tokens": raw_usage.get("completion_tokens", int(len(reply.split()) * 1.3)),
                "total_tokens": raw_usage.get("total_tokens", int((len(prompt.split()) + len(reply.split())) * 1.3)),
            }
            return {
                "response": reply,
                "backend": "Cloud Run GPU",
                "url": self.cloudrun_url,
                "usage": usage,
            }

        # Strategy 2: Explicit or Auto-Discovered Vertex AI Endpoint
        active_endpoint = self.endpoint_id
        active_region = self.region

        if not active_endpoint:
            discovery = self.discover_active_vertex_endpoint()
            if discovery:
                active_endpoint = discovery["endpoint_id"]
                active_region = discovery["region"]

        if active_endpoint:
            instances = [
                {
                    "prompt": f"<start_of_turn>user\n{self.system_instruction}\n\n{prompt}<end_of_turn>\n<start_of_turn>model\n",
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                }
            ]
            try:
                from google.cloud import aiplatform
                endpoint = aiplatform.Endpoint(
                    endpoint_name=active_endpoint,
                    project=self.project_id,
                    location=active_region,
                )
                res = endpoint.predict(instances=instances)
                predictions = res.predictions
                reply = predictions[0] if predictions else "No prediction returned."
                if isinstance(reply, str) and "Output:\n" in reply:
                    reply = reply.split("Output:\n", 1)[1].strip()
                prompt_est = int(len(f"{self.system_instruction} {prompt}".split()) * 1.3)
                comp_est = int(len(str(reply).split()) * 1.3)
                return {
                    "response": str(reply),
                    "backend": "Vertex AI Online Prediction",
                    "endpoint_id": active_endpoint,
                    "region": active_region,
                    "usage": {
                        "prompt_tokens": prompt_est,
                        "completion_tokens": comp_est,
                        "total_tokens": prompt_est + comp_est,
                    },
                }
            except Exception:
                payload = {"instances": instances}
                with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
                    json.dump(payload, f)
                    tmp_path = f.name

                try:
                    cmd = [
                        "gcloud", "ai", "endpoints", "predict", active_endpoint,
                        f"--region={active_region}",
                        f"--project={self.project_id}",
                        f"--json-request={tmp_path}",
                        "--format=json",
                    ]
                    res = subprocess.run(cmd, capture_output=True, text=True)
                    if res.returncode == 0:
                        data = json.loads(res.stdout)
                        predictions = data.get("predictions", [])
                        reply = predictions[0] if predictions else "No prediction returned."
                        if isinstance(reply, str) and "Output:\n" in reply:
                            reply = reply.split("Output:\n", 1)[1].strip()
                        prompt_est = int(len(f"{self.system_instruction} {prompt}".split()) * 1.3)
                        comp_est = int(len(str(reply).split()) * 1.3)
                        return {
                            "response": reply,
                            "backend": "Vertex AI Online Prediction",
                            "endpoint_id": active_endpoint,
                            "region": active_region,
                            "usage": {
                                "prompt_tokens": prompt_est,
                                "completion_tokens": comp_est,
                                "total_tokens": prompt_est + comp_est,
                            },
                        }
                except Exception:
                    pass
                finally:
                    if os.path.exists(tmp_path):
                        os.remove(tmp_path)


        # Strategy 3: Fallback / Managed Model
        target_managed_model = self.managed_model or "gemini-2.5-flash"
        try:
            from google import genai
            from google.genai import types
            client = genai.Client(vertexai=True, project=self.project_id, location=self.region)
            config = types.GenerateContentConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
                system_instruction=self.system_instruction,
            )
            chat = client.chats.create(model=target_managed_model, config=config)
            res = chat.send_message(prompt)
            prompt_cnt = getattr(res.usage_metadata, "prompt_token_count", int(len(prompt.split()) * 1.3))
            comp_cnt = getattr(res.usage_metadata, "candidates_token_count", int(len((res.text or "").split()) * 1.3))
            total_cnt = getattr(res.usage_metadata, "total_token_count", prompt_cnt + comp_cnt)
            return {
                "response": res.text or "",
                "backend": f"Vertex AI Model Garden / MaaS ({target_managed_model})",
                "model": target_managed_model,
                "usage": {
                    "prompt_tokens": prompt_cnt,
                    "completion_tokens": comp_cnt,
                    "total_tokens": total_cnt,
                },
            }
        except Exception as e:
            return {
                "error": f"Managed model query failed: {e}",
                "backend": "Managed Model Error",
            }


