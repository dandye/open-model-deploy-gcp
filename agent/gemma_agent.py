"""Gemma-Powered ADK Agent for Vertex AI Agent Engine.

This agent connects dynamically to self-deployed Gemma endpoints (Vertex AI Online
Prediction or Cloud Run with GPU) or hosted Gemini API / MaaS models. It supports
auto-discovering active endpoints to gracefully handle rapid deployment & teardown cycles.
"""

from pathlib import Path
import re
from typing import Any, Callable, Dict, List, Optional, Tuple
import os
import sys
import json
import time
import tempfile
import subprocess
import urllib.request
import urllib.error

os.environ["GOOGLE_API_USE_CLIENT_CERTIFICATE"] = "false"
os.environ["GOOGLE_API_USE_MTLS_ENDPOINT"] = "never"
os.environ["CLOUDSDK_CONTEXT_AWARE_USE_CLIENT_CERTIFICATE"] = "false"

try:
    import google.auth.transport._mtls_helper as _mtls_helper
    _mtls_helper.has_client_certificate = lambda: False
    _mtls_helper.get_client_cert_and_key = lambda: (False, None, None)
    _mtls_helper.get_client_ssl_credentials = lambda *args, **kwargs: (False, None, None, None)
except Exception:
    pass



def _load_models_catalog() -> Dict[str, Any]:
    """Loads configs/models.json safely for MaaS model ID and region resolution."""
    catalog_path = Path(__file__).resolve().parent.parent / "configs" / "models.json"
    if not catalog_path.exists():
        return {}
    try:
        with open(catalog_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _is_open_maas_model(model_id: str) -> bool:
    """Returns True when model_id routes to Vertex OpenAPI /endpoints/openapi/chat/completions."""
    clean = (model_id or "").strip().lower()
    if not clean.endswith("-maas") or "/" not in clean:
        return False
    provider, model_slug = clean.split("/", 1)
    if not provider or not model_slug:
        return False
    if provider in ("meta", "google", "publishers"):
        return False
    return True


def _build_open_maas_url(project_id: str, region: str) -> str:
    """Builds the Vertex AI OpenAPI chat completions URL for global or regional MaaS."""
    loc = (region or "global").strip()
    if loc == "global":
        return (
            f"https://aiplatform.googleapis.com/v1/projects/{project_id}"
            "/locations/global/endpoints/openapi/chat/completions"
        )
    return (
        f"https://{loc}-aiplatform.googleapis.com/v1/projects/{project_id}"
        f"/locations/{loc}/endpoints/openapi/chat/completions"
    )


def _resolve_managed_model_and_region(
    managed_model: str,
    default_region: str = "us-central1",
    catalog: Optional[Dict[str, Any]] = None,
) -> Tuple[str, str]:
    """Resolves bare or prefixed managed model IDs and target Vertex region."""
    raw_model = (managed_model or "gemini-2.5-flash").strip()
    target_region = (default_region or "us-central1").strip()
    cat = _load_models_catalog() if catalog is None else catalog

    entry: Optional[Dict[str, Any]] = None
    if raw_model in cat and isinstance(cat[raw_model], dict):
        entry = cat[raw_model]
    else:
        for cand in cat.values():
            if not isinstance(cand, dict):
                continue
            if raw_model in (cand.get("maasModelId"), cand.get("modelId")):
                entry = cand
                break

    target_model = raw_model
    if entry is not None and (
        entry.get("type") == "maas"
        or entry.get("maasModelId")
        or "vertex_maas" in (entry.get("supportedTargets") or [])
    ):
        target_model = str(
            entry.get("maasModelId") or entry.get("modelId") or raw_model
        ).strip()

    if (
        "/" not in target_model
        and target_model.lower().startswith("deepseek-")
        and target_model.lower().endswith("-maas")
    ):
        target_model = f"deepseek-ai/{target_model}"

    if "llama" in target_model.lower():
        if not target_model.startswith("meta/") and not target_model.startswith("publishers/"):
            target_model = f"meta/{target_model}"
        if "llama-4" in target_model.lower():
            target_region = "us-east5"
        else:
            target_region = "us-central1"
        return target_model, target_region

    cat_region = str(entry.get("region") or "").strip() if entry is not None else ""
    if target_model.lower().startswith("deepseek-ai/") and target_model.lower().endswith("-maas"):
        if cat_region == "global" or target_region == "us-central1":
            target_region = "global"
        return target_model, target_region

    if _is_open_maas_model(target_model):
        if cat_region == "global":
            target_region = "global"
        elif cat_region and target_region == "us-central1":
            target_region = cat_region
        elif target_region == "us-central1":
            target_region = "global"
        return target_model, target_region

    if (
        "gemini-3.7" in target_model.lower()
        or "gemini-3.5" in target_model.lower()
        or "gemini-3.1" in target_model.lower()
        or "gemini-3-" in target_model.lower()
        or "gemma-4" in target_model.lower()
    ) and target_region == "us-central1":
        target_region = "global"

    return target_model, target_region


def _get_bearer_token() -> str:
    """Refreshes Google Cloud ADC bearer credentials with gcloud CLI fallback."""
    try:
        import google.auth
        import google.auth.transport.requests
        credentials, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        if not getattr(credentials, "valid", False) or not getattr(credentials, "token", None):
            auth_req = google.auth.transport.requests.Request()
            credentials.refresh(auth_req)
        if getattr(credentials, "token", None):
            return str(credentials.token).strip()
    except Exception:
        pass
    try:
        token_res = subprocess.run(
            ["gcloud", "auth", "print-access-token"],
            capture_output=True,
            text=True,
            check=False,
        )
        if token_res.returncode == 0 and token_res.stdout.strip():
            return token_res.stdout.strip()
    except Exception:
        pass
    return ""


def _extract_openai_chat_message(msg: Dict[str, Any]) -> Tuple[str, Optional[str]]:
    """Extracts response text and separated reasoning metadata from an OpenAI chat message.

    Serializes tool_calls into ReAct Action JSON lines before considering reasoning_content,
    strips <think>...</think> blocks when post-think text or tool_calls exist, and preserves
    reasoning_content out-of-band so chain-of-thought never pollutes response assertions.
    """
    if not isinstance(msg, dict):
        return "", None

    action_lines: List[str] = []
    raw_tool_calls = msg.get("tool_calls") or []
    if isinstance(raw_tool_calls, list):
        for tc in raw_tool_calls:
            if not isinstance(tc, dict):
                continue
            fn = tc.get("function") if isinstance(tc.get("function"), dict) else tc
            if not isinstance(fn, dict):
                continue
            name = fn.get("name")
            if not name or not isinstance(name, str) or not name.strip():
                continue
            raw_args = fn.get("arguments")
            if raw_args is None:
                args_val: Any = {}
            elif isinstance(raw_args, str):
                stripped_args = raw_args.strip()
                if not stripped_args:
                    args_val = {}
                else:
                    try:
                        args_val = json.loads(stripped_args)
                    except Exception:
                        args_val = raw_args
            else:
                args_val = raw_args
            action_lines.append(
                f'Action: {json.dumps({"name": name.strip(), "arguments": args_val})}'
            )

    if not action_lines and isinstance(msg.get("function_call"), dict):
        fc = msg["function_call"]
        fc_name = fc.get("name")
        if fc_name and isinstance(fc_name, str) and fc_name.strip():
            fc_raw_args = fc.get("arguments")
            if isinstance(fc_raw_args, str) and fc_raw_args.strip():
                try:
                    fc_args: Any = json.loads(fc_raw_args.strip())
                except Exception:
                    fc_args = fc_raw_args
            elif fc_raw_args is None or fc_raw_args == "":
                fc_args = {}
            else:
                fc_args = fc_raw_args
            action_lines.append(
                f'Action: {json.dumps({"name": fc_name.strip(), "arguments": fc_args})}'
            )

    content_field = msg.get("content")
    if isinstance(content_field, list):
        parts: List[str] = []
        for part in content_field:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict) and isinstance(part.get("text"), str):
                parts.append(part["text"])
        raw_content = "".join(parts)
    elif content_field is None:
        raw_content = ""
    else:
        raw_content = str(content_field)

    raw_reasoning = msg.get("reasoning_content")
    if raw_reasoning is None:
        raw_reasoning = msg.get("reasoning")
    reasoning_content: Optional[str] = (
        str(raw_reasoning) if raw_reasoning is not None and str(raw_reasoning) != "" else None
    )

    cleaned_content = raw_content.strip()
    lower_content = raw_content.lower()
    if "<think>" in lower_content and "</think>" in lower_content:
        think_chunks = re.findall(
            r"<think>(.*?)</think>", raw_content, flags=re.DOTALL | re.IGNORECASE
        )
        extracted_think = "\n\n".join(c.strip() for c in think_chunks if c.strip())
        if extracted_think and not reasoning_content:
            reasoning_content = extracted_think
        after_think = re.sub(
            r"<think>.*?</think>", "", raw_content, flags=re.DOTALL | re.IGNORECASE
        ).strip()
        cleaned_content = after_think if after_think else ""
    elif "</think>" in lower_content:
        before_think, after_think_raw = re.split(
            r"</think>", raw_content, maxsplit=1, flags=re.IGNORECASE
        )
        if before_think.strip() and not reasoning_content:
            reasoning_content = before_think.strip()
        after_think = after_think_raw.strip()
        cleaned_content = after_think if after_think else ""

    if cleaned_content and action_lines:
        final_text = f"{cleaned_content}\n" + "\n".join(action_lines)
    elif action_lines:
        final_text = "\n".join(action_lines)
    elif cleaned_content:
        final_text = cleaned_content
    elif reasoning_content:
        final_text = reasoning_content
    else:
        final_text = ""

    return final_text, reasoning_content


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
        resolved_project_id = (
            project_id
            or os.environ.get("PROJECT_ID")
            or os.environ.get("GCP_PROJECT_ID")
            or os.environ.get("GOOGLE_CLOUD_PROJECT")
        )
        if not resolved_project_id:
            try:
                import google.auth
                _, default_project = google.auth.default()
                resolved_project_id = default_project
            except Exception:
                pass
        self.project_id = resolved_project_id or ""
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

    def query(
        self,
        prompt: str,
        max_tokens: Optional[int] = None,
        temperature: float = 0.7,
        image_urls: Optional[List[str]] = None,
        tools_schema: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Queries the configured or auto-discovered Gemma or MaaS model backend.

        Args:
            prompt: Input user prompt.
            max_tokens: Maximum generated tokens. Defaults to None for unbounded/default headroom.
            temperature: Sampling temperature.
            image_urls: Optional list of image URLs or data:image/... base64 URIs for multimodal queries.
            tools_schema: Optional list of OpenAI-compatible tool schema dicts.

        Returns:
            Dictionary containing the generated response, metadata, and active backend.
        """
        user_content: Any = (
            [
                {"type": "text", "text": prompt},
                *[{"type": "image_url", "image_url": {"url": u}} for u in image_urls],
            ]
            if image_urls
            else prompt
        )

        # Strategy 1: Cloud Run URL
        if self.cloudrun_url:
            token = _get_bearer_token()
            url = f"{self.cloudrun_url.rstrip('/')}/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }
            # Dynamically resolve registered model ID from vLLM /v1/models endpoint
            model_name = self.managed_model
            if not model_name:
                try:
                    models_url = f"{self.cloudrun_url.rstrip('/')}/v1/models"
                    models_req = urllib.request.Request(models_url, headers=headers)
                    with urllib.request.urlopen(models_req, timeout=10) as m_resp:
                        m_data = json.loads(m_resp.read().decode("utf-8"))
                        if m_data.get("data") and len(m_data["data"]) > 0:
                            model_name = m_data["data"][0]["id"]
                except Exception:
                    pass
            if not model_name:
                model_name = "google/gemma-3-1b-it"

            cloudrun_max_tokens = 8192 if max_tokens is None else max_tokens
            payload: Dict[str, Any] = {
                "model": model_name,
                "messages": [
                    {"role": "system", "content": self.system_instruction},
                    {"role": "user", "content": user_content},
                ],
                "max_tokens": cloudrun_max_tokens,
                "temperature": temperature,
            }
            if tools_schema:
                payload["tools"] = tools_schema
            req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
            max_retries = 6
            data = None
            for attempt in range(max_retries):
                try:
                    with urllib.request.urlopen(req, timeout=600) as resp:
                        data = json.loads(resp.read().decode("utf-8"))
                    break
                except urllib.error.HTTPError as e:
                    if e.code in (429, 503, 504) and attempt < max_retries - 1:
                        sleep_s = (2 ** attempt) * 3
                        time.sleep(sleep_s)
                        continue
                    raise
            choices = data.get("choices") or [] if isinstance(data, dict) else []
            msg = choices[0].get("message", {}) if choices and isinstance(choices[0], dict) else {}
            reply, reasoning_content = _extract_openai_chat_message(msg)
            raw_usage = data.get("usage", {}) if isinstance(data, dict) else {}
            usage = {
                "prompt_tokens": raw_usage.get("prompt_tokens", int(len(prompt.split()) * 1.3)),
                "completion_tokens": raw_usage.get("completion_tokens", int(len(reply.split()) * 1.3)),
                "total_tokens": raw_usage.get("total_tokens", int((len(prompt.split()) + len(reply.split())) * 1.3)),
            }
            return {
                "response": reply,
                "reasoning_content": reasoning_content,
                "backend": "Cloud Run GPU",
                "url": self.cloudrun_url,
                "usage": usage,
            }

        # Strategy 2: Explicit or Auto-Discovered Vertex AI Endpoint
        active_endpoint = self.endpoint_id
        active_region = self.region

        if not active_endpoint and not self.managed_model:
            discovery = self.discover_active_vertex_endpoint()
            if discovery:
                active_endpoint = discovery["endpoint_id"]
                active_region = discovery["region"]

        if active_endpoint:
            vertex_max_tokens = 8192 if max_tokens is None else max_tokens
            use_chat_completions = os.environ.get("VERTEX_USE_CHAT_COMPLETIONS", "").lower() in ("1", "true", "yes")
            if use_chat_completions:
                chat_instance: Dict[str, Any] = {
                    "@requestFormat": "chatCompletions",
                    "messages": [
                        {"role": "system", "content": self.system_instruction},
                        {"role": "user", "content": user_content},
                    ],
                    "max_tokens": vertex_max_tokens,
                    "temperature": temperature,
                }
                if tools_schema:
                    chat_instance["tools"] = tools_schema
                instances = [chat_instance]
            else:
                instances = [
                    {
                        "prompt": f"<start_of_turn>user\n{self.system_instruction}\n\n{prompt}<end_of_turn>\n<start_of_turn>model\n",
                        "max_tokens": vertex_max_tokens,
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
                raw_usage: Dict[str, Any] = {}
                reasoning_content: Optional[str] = None
                if isinstance(predictions, dict) and "choices" in predictions:
                    choices = predictions.get("choices") or []
                    msg = choices[0].get("message", {}) if choices else {}
                    reply, reasoning_content = _extract_openai_chat_message(msg)
                    raw_usage = predictions.get("usage") or {}
                elif (
                    isinstance(predictions, list)
                    and predictions
                    and isinstance(predictions[0], dict)
                    and "choices" in predictions[0]
                ):
                    pred0 = predictions[0]
                    choices = pred0.get("choices") or []
                    msg = choices[0].get("message", {}) if choices else {}
                    reply, reasoning_content = _extract_openai_chat_message(msg)
                    raw_usage = pred0.get("usage") or {}
                else:
                    reply = predictions[0] if predictions else "No prediction returned."
                    if isinstance(reply, str) and "Output:\n" in reply:
                        reply = reply.split("Output:\n", 1)[1].strip()
                    if isinstance(reply, str) and "</think>" in reply:
                        after_think = reply.split("</think>", 1)[1].strip()
                        if after_think:
                            reply = after_think
                prompt_est = int(raw_usage.get("prompt_tokens") or int(len(f"{self.system_instruction} {prompt}".split()) * 1.3))
                comp_est = int(raw_usage.get("completion_tokens") or int(len(str(reply).split()) * 1.3))
                total_est = int(raw_usage.get("total_tokens") or (prompt_est + comp_est))
                return {
                    "response": str(reply),
                    "reasoning_content": reasoning_content,
                    "backend": "Vertex AI Online Prediction",
                    "endpoint_id": active_endpoint,
                    "region": active_region,
                    "usage": {
                        "prompt_tokens": prompt_est,
                        "completion_tokens": comp_est,
                        "total_tokens": total_est,
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

        # Strategy 3: Fallback / Managed Model (OpenMaaS OpenAPI or google.genai)
        target_managed_model, target_region = _resolve_managed_model_and_region(
            self.managed_model or "gemini-2.5-flash",
            default_region=self.region,
        )

        # Strategy 3a: Partner Vertex OpenMaaS (/endpoints/openapi/chat/completions)
        if _is_open_maas_model(target_managed_model):
            url = _build_open_maas_url(self.project_id, target_region)
            token = _get_bearer_token()
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }
            maas_payload: Dict[str, Any] = {
                "model": target_managed_model,
                "messages": [
                    {"role": "system", "content": self.system_instruction},
                    {"role": "user", "content": user_content},
                ],
                "temperature": temperature,
            }
            if max_tokens is not None:
                maas_payload["max_tokens"] = max_tokens
            if tools_schema:
                maas_payload["tools"] = tools_schema

            encoded_payload = json.dumps(maas_payload).encode("utf-8")
            max_retries = 5
            data = None
            for attempt in range(max_retries):
                req = urllib.request.Request(
                    url, data=encoded_payload, headers=headers, method="POST"
                )
                try:
                    with urllib.request.urlopen(req, timeout=300) as resp:
                        data = json.loads(resp.read().decode("utf-8"))
                    break
                except urllib.error.HTTPError as http_err:
                    status_code = int(getattr(http_err, "code", 0) or 0)
                    err_body = ""
                    try:
                        raw_err = http_err.read()
                        if isinstance(raw_err, bytes):
                            err_body = raw_err.decode("utf-8", errors="replace").strip()
                        elif raw_err:
                            err_body = str(raw_err).strip()
                    except Exception:
                        err_body = ""

                    if status_code in (401, 403, 404):
                        access_tag = (
                            "MAAS_ACCESS_GATED" if status_code in (403, 404) else "MAAS_AUTH_ERROR"
                        )
                        detail = err_body or str(http_err)
                        return {
                            "error": (
                                f"OpenMaaS HTTP {status_code} ({access_tag}) for "
                                f"{target_managed_model} in {target_region}: {detail}"
                            ),
                            "status_code": status_code,
                            "error_body": err_body,
                            "maas_status": access_tag,
                            "backend": "Managed Model Error",
                            "model": target_managed_model,
                            "region": target_region,
                        }

                    if status_code in (429, 503, 504) and attempt < max_retries - 1:
                        time.sleep((2 ** attempt) * 2)
                        continue

                    detail = err_body or str(http_err)
                    return {
                        "error": (
                            f"OpenMaaS HTTP {status_code} for {target_managed_model} "
                            f"in {target_region}: {detail}"
                        ),
                        "status_code": status_code,
                        "error_body": err_body,
                        "backend": "Managed Model Error",
                        "model": target_managed_model,
                        "region": target_region,
                    }
                except Exception as exc:
                    return {
                        "error": f"OpenMaaS query failed for {target_managed_model}: {exc}",
                        "backend": "Managed Model Error",
                        "model": target_managed_model,
                        "region": target_region,
                    }

            choices = data.get("choices") or [] if isinstance(data, dict) else []
            msg = choices[0].get("message", {}) if choices and isinstance(choices[0], dict) else {}
            reply, reasoning_content = _extract_openai_chat_message(msg)

            raw_usage = data.get("usage") if isinstance(data, dict) else None
            has_actual_usage = isinstance(raw_usage, dict) and (
                raw_usage.get("prompt_tokens") is not None
                or raw_usage.get("completion_tokens") is not None
                or raw_usage.get("total_tokens") is not None
            )
            if has_actual_usage:
                prompt_cnt = int(raw_usage.get("prompt_tokens") or 0)
                comp_cnt = int(raw_usage.get("completion_tokens") or 0)
                total_cnt = int(raw_usage.get("total_tokens") or (prompt_cnt + comp_cnt))
                token_count_source = "actual"
            else:
                prompt_cnt = int(len(prompt.split()) * 1.3)
                comp_cnt = int(len(reply.split()) * 1.3)
                total_cnt = prompt_cnt + comp_cnt
                token_count_source = "estimated"

            usage_dict: Dict[str, Any] = {
                "prompt_tokens": prompt_cnt,
                "completion_tokens": comp_cnt,
                "total_tokens": total_cnt,
                "token_count_source": token_count_source,
            }
            if isinstance(raw_usage, dict):
                details = raw_usage.get("completion_tokens_details")
                reasoning_toks = None
                if isinstance(details, dict) and details.get("reasoning_tokens") is not None:
                    reasoning_toks = int(details["reasoning_tokens"])
                elif raw_usage.get("reasoning_tokens") is not None:
                    reasoning_toks = int(raw_usage["reasoning_tokens"])
                if reasoning_toks is not None:
                    usage_dict["reasoning_tokens"] = reasoning_toks

            return {
                "response": reply,
                "reasoning_content": reasoning_content,
                "backend": f"Vertex AI OpenMaaS ({target_managed_model})",
                "model": target_managed_model,
                "region": target_region,
                "url": url,
                "token_count_source": token_count_source,
                "usage": usage_dict,
            }

        try:
            from google import genai
            from google.genai import types
            client = genai.Client(
                vertexai=True,
                project=self.project_id,
                location=target_region,
                http_options=types.HttpOptions(timeout=90000),
            )
            if max_tokens is not None:
                config = types.GenerateContentConfig(
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                    system_instruction=self.system_instruction,
                )
            else:
                config = types.GenerateContentConfig(
                    temperature=temperature,
                    system_instruction=self.system_instruction,
                )
            res = None
            last_err = None
            for attempt in range(5):
                try:
                    chat = client.chats.create(model=target_managed_model, config=config)
                    res = chat.send_message(prompt)
                    break
                except Exception as call_err:
                    last_err = call_err
                    err_str = str(call_err)
                    if ("429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "503" in err_str) and attempt < 4:
                        time.sleep((2 ** attempt) * 3)
                        continue
                    raise
            if res is None and last_err is not None:
                raise last_err
            text_out = res.text or ""
            try:
                for cand in getattr(res, "candidates", None) or []:
                    content = getattr(cand, "content", None)
                    for part in getattr(content, "parts", None) or []:
                        fc = getattr(part, "function_call", None)
                        if fc is not None and getattr(fc, "name", None):
                            fc_args = dict(getattr(fc, "args", None) or {})
                            action_line = f'Action: {json.dumps({"name": fc.name, "arguments": fc_args})}'
                            text_out = f"{text_out}\n{action_line}".strip() if text_out else action_line
            except Exception:
                pass
            prompt_cnt = int(
                getattr(res.usage_metadata, "prompt_token_count", None)
                or int(len(prompt.split()) * 1.3)
            )
            comp_cnt = int(
                getattr(res.usage_metadata, "candidates_token_count", None)
                or int(len(text_out.split()) * 1.3)
            )
            total_cnt = int(
                getattr(res.usage_metadata, "total_token_count", None)
                or (prompt_cnt + comp_cnt)
            )
            return {
                "response": text_out,
                "backend": f"Vertex AI Model Garden / MaaS ({target_managed_model})",
                "model": target_managed_model,
                "region": target_region,
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

