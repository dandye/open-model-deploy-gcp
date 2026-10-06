"""Unit tests for the shared Jev backend factory."""

from unittest.mock import MagicMock

import pytest

from agent.jev_backend_gemini import GeminiSystem1Backend
from agent.jev_backend_gliner import GlinerDecideBackend
from agent.jev_backend_typesafe import TypeSafeJevBackend
from agent.jev_backends import JEV_BACKEND_CHOICES, build_jev_backend, describe_jev_backend
from agent.jev_judge import MockJevBackend


def test_choices_list_every_backend_with_gemini_first():
    assert JEV_BACKEND_CHOICES == ("gemini_system1", "typesafe", "mock", "gliner_decide")


def test_mock_name_builds_the_mock_backend():
    assert isinstance(build_jev_backend("mock"), MockJevBackend)


def test_gemini_name_builds_the_system1_backend_with_the_injected_client():
    client = MagicMock()
    backend = build_jev_backend("gemini_system1", project_id="proj", location="us-central1", client=client)
    assert isinstance(backend, GeminiSystem1Backend)
    assert backend.client is client
    assert backend.project_id == "proj"
    assert backend.location == "us-central1"


def test_typesafe_name_builds_the_remote_backend(monkeypatch):
    monkeypatch.setenv("TYPE_SAFE_API_KEY", "k")
    assert isinstance(build_jev_backend("typesafe"), TypeSafeJevBackend)


def test_gliner_name_builds_the_backend_without_loading_the_model():
    backend = build_jev_backend("gliner_decide")
    assert isinstance(backend, GlinerDecideBackend)
    assert backend._engine is None
    assert backend.model_id == "fastino/GLiNER2.5-Decide"


def test_unknown_name_is_rejected_with_the_choices():
    with pytest.raises(ValueError, match="gliner_decide"):
        build_jev_backend("jev")


def test_describe_reports_what_each_backend_pins():
    assert describe_jev_backend(MockJevBackend()) == {"backend": "mock"}
    gemini = describe_jev_backend(GeminiSystem1Backend(project_id="p", client=MagicMock()))
    assert gemini == {"backend": "gemini_system1", "model": "gemini-2.5-flash", "location": "us-central1"}
    gliner = describe_jev_backend(GlinerDecideBackend())
    assert gliner["backend"] == "gliner_decide"
    assert gliner["model_id"] == "fastino/GLiNER2.5-Decide"
    assert gliner["revision"] == "7ee5da4c2415e32259bcdc0b1a7367c32ce8d6f6"
    assert describe_jev_backend(TypeSafeJevBackend(api_key="k"))["backend"] == "typesafe"
