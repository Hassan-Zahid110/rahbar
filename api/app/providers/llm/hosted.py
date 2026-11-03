"""Hosted free-tier OpenAI-compatible provider (Groq, Google AI Studio, OpenRouter).

The API key arrives via LLM_API_KEY from a Kubernetes Secret created on the CLI.
It is never committed to Git and never logged.
"""

from __future__ import annotations

import httpx

from ...config import Settings
from ...routes import metrics
from ...schemas import Answer, Passage
from ...services.prompting import build_augmented_messages, estimate_tokens


class HostedProvider:
    name = "hosted"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def generate(self, question: str, passages: list[Passage]) -> Answer:
        """Call an OpenAI-compatible `/chat/completions` endpoint in JSON mode and
        validate the structured output with `Answer.model_validate_json`."""
        if not self.settings.hosted_base_url:
            raise RuntimeError("HOSTED_BASE_URL is not configured for LLM_PROVIDER=hosted")
        if not self.settings.llm_api_key:
            raise RuntimeError("LLM_API_KEY is missing from Secret for LLM_PROVIDER=hosted")

        messages = build_augmented_messages(
            question=question,
            passages=passages,
            strict_grounding=self.settings.strict_grounding_prompt,
        )
        payload = {
            "model": self.settings.llm_model,
            "messages": messages,
            "temperature": self.settings.temperature,
            "response_format": {"type": "json_object"},
        }
        headers = {
            "Authorization": f"Bearer {self.settings.llm_api_key}",
            "Content-Type": "application/json",
        }
        url = f"{self.settings.hosted_base_url.rstrip('/')}/chat/completions"
        timeout = httpx.Timeout(self.settings.llm_timeout_seconds, connect=10.0)
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            body = resp.json()

        choices = body.get("choices") or []
        if not choices:
            raise RuntimeError("Hosted LLM returned no choices")
        content = str((choices[0].get("message") or {}).get("content") or "")

        usage = body.get("usage") or {}
        in_toks = int(usage.get("prompt_tokens") or 0) or sum(
            estimate_tokens(m["content"]) for m in messages
        )
        out_toks = int(usage.get("completion_tokens") or 0) or estimate_tokens(content)
        metrics.TOKENS_IN.inc(in_toks)
        metrics.TOKENS_OUT.inc(out_toks)

        return Answer.model_validate_json(content)
