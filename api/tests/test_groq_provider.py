"""LLM_PROVIDER=groq is a preset over the OpenAI-compatible hosted provider."""

from __future__ import annotations

import pytest

from app.config import GROQ_BASE_URL, GROQ_DEFAULT_MODEL, get_settings
from app.providers.llm import get_provider
from app.providers.llm.hosted import HostedProvider


def test_groq_preset_fills_base_url_and_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.delenv("HOSTED_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    settings = get_settings()
    assert settings.hosted_base_url == GROQ_BASE_URL
    assert settings.llm_model == GROQ_DEFAULT_MODEL


def test_groq_preset_respects_explicit_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.setenv("HOSTED_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("LLM_MODEL", "llama-3.3-70b-versatile")
    settings = get_settings()
    assert settings.hosted_base_url == "https://example.test/v1"
    assert settings.llm_model == "llama-3.3-70b-versatile"


def test_groq_selects_hosted_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    provider = get_provider(get_settings())
    assert isinstance(provider, HostedProvider)
    assert provider.name == "groq"


def test_groq_without_key_fails_loudly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    provider = get_provider(get_settings())
    with pytest.raises(RuntimeError, match="LLM_API_KEY"):
        provider.generate("What CGPA triggers academic warning?", [])



def test_groq_default_model_is_universal():
    from app.config import GROQ_DEFAULT_MODEL
    assert GROQ_DEFAULT_MODEL == "openai/gpt-oss-20b"
