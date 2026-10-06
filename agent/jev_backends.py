"""One place that turns a ``--jev-backend`` name into a backend and describes it.

The evaluation runner and the GEPA optimizer both select a Jev backend from
the CLI; keeping the mapping here means a new backend lands in both with one
edit and that run metadata records the same provenance fields everywhere.
"""

from typing import Any, Dict, Optional, Tuple

from agent.jev_backend_gemini import GeminiSystem1Backend
from agent.jev_backend_gliner import GlinerDecideBackend
from agent.jev_backend_typesafe import TypeSafeJevBackend
from agent.jev_judge import BaseJevBackend, MockJevBackend

JEV_BACKEND_CHOICES: Tuple[str, ...] = ("gemini_system1", "typesafe", "mock", "gliner_decide")
DEFAULT_JEV_BACKEND = "gemini_system1"


def build_jev_backend(
    name: str,
    project_id: Optional[str] = None,
    location: str = "us-central1",
    client: Optional[Any] = None,
) -> BaseJevBackend:
    """Builds the backend for ``name``; ``project_id``/``location``/``client`` only matter for Gemini."""
    if name == "mock":
        return MockJevBackend()
    if name == "typesafe":
        return TypeSafeJevBackend()
    if name == "gliner_decide":
        return GlinerDecideBackend()
    if name == "gemini_system1":
        return GeminiSystem1Backend(project_id=project_id, location=location, client=client)
    raise ValueError(f"Unknown Jev backend {name!r}; choose one of {', '.join(JEV_BACKEND_CHOICES)}")


def describe_jev_backend(backend: BaseJevBackend) -> Dict[str, Any]:
    """Provenance for run metadata: what the judge is pinned to."""
    if isinstance(backend, GlinerDecideBackend):
        return backend.describe()
    if isinstance(backend, GeminiSystem1Backend):
        return {"backend": "gemini_system1", "model": backend.model, "location": backend.location}
    if isinstance(backend, TypeSafeJevBackend):
        return {"backend": "typesafe", "endpoint_url": backend.endpoint_url}
    if isinstance(backend, MockJevBackend):
        return {"backend": "mock"}
    return {"backend": type(backend).__name__}
