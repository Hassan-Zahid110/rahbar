"""Ollama provider: ollama-host or ollama-incluster (sections 3.4 and 3.5)."""

from __future__ import annotations

import httpx

from ...config import Settings
from ...routes import metrics
from ...schemas import Answer, Passage
from ...services.prompting import build_augmented_messages, estimate_tokens


class OllamaProvider:
    name = "ollama"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def generate(self, question: str, passages: list[Passage]) -> Answer:
        """Build the augmented prompt, enforce JSON output via Ollama's `format=` schema,
        and validate the response with Pydantic."""
        messages = build_augmented_messages(
            question=question,
            passages=passages,
            strict_grounding=self.settings.strict_grounding_prompt,
        )
        payload = {
            "model": self.settings.llm_model,
            "messages": messages,
            "stream": False,
            "format": Answer.model_json_schema(),
            "options": {
                "temperature": self.settings.temperature,
            },
        }
        url = f"{self.settings.ollama_url.rstrip('/')}/api/chat"
        timeout = httpx.Timeout(self.settings.llm_timeout_seconds, connect=10.0)
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(url, json=payload)
            resp.raise_for_status()
            body = resp.json()

        prompt_toks = int(body.get("prompt_eval_count") or 0) or sum(
            estimate_tokens(m["content"]) for m in messages
        )
        completion_content = str((body.get("message") or {}).get("content") or "")
        out_toks = int(body.get("eval_count") or 0) or estimate_tokens(completion_content)
        metrics.TOKENS_IN.inc(prompt_toks)
        metrics.TOKENS_OUT.inc(out_toks)

        return Answer.model_validate_json(completion_content)
