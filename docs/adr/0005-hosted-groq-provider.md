# ADR 0005: Hosted LLM Provider Preset for Groq

## Status
Accepted

## Context
Running Ollama locally requires significant memory and CPU/GPU resources that may not be available on all development or CI machines. A cloud-hosted OpenAI-compatible inference provider is needed to enable real model responses with minimal local footprint.

## Decision
We implemented `LLM_PROVIDER=groq` as an OpenAI-compatible preset. It defaults to Groq endpoints with low-latency JSON response format and reads API keys strictly from Kubernetes Secrets (`rahbar-secret`), never logging or committing keys.

## Consequences
- Fast inference (~40ms token generation).
- Zero secrets committed to git.
- Full compliance with Grounded RAG Answer Pydantic validation schema.
