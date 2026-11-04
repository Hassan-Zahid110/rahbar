# ADR 0004: Pluggable LLM Provider Interface, Local Ollama Default, and Data Governance

## Status
Accepted · 2026-11-04

## Context
RAHBAR must support pluggable generation backends selected solely via `LLM_PROVIDER` in `ConfigMap/rahbar-config` (`stub`, `ollama-host`, `ollama-incluster`, or `hosted`) without rebuilding container images, while enforcing structured `Answer` outputs, defending against prompt injection, keeping secrets out of Git, and respecting data governance over university documents and student queries.

## Decision
1. **Single-protocol provider abstraction (`api/app/providers/llm/`)**:
   - `LLMProvider` (`base.py`) exposes one synchronous contract: `generate(question: str, passages: list[Passage]) -> Answer`.
   - `get_provider(settings)` dispatches on `LLM_PROVIDER` to `StubProvider` (deterministic offline CI/unit tests), `OllamaProvider` (`POST {OLLAMA_URL}/api/chat` with `format=Answer.model_json_schema()`), or `HostedProvider` (`POST {HOSTED_BASE_URL}/chat/completions` with `response_format={"type": "json_object"}` and bearer auth from `Secret/rahbar-secret`).
2. **Default runtime mode: `ollama-host` (`llama3.2:3b` + `nomic-embed-text`)**:
   - Runs natively on Apple Silicon Metal acceleration on the host (`OLLAMA_HOST=0.0.0.0 ollama serve`), reached from Minikube via `http://host.minikube.internal:11434` through an explicit port-`11434` egress rule in `allow-api` and `allow-indexer`.
   - **Data governance & PII**: Student questions (which frequently contain roll numbers, CGPA details, or disciplinary appeals) and internal university policy texts never leave the local machine—eliminating third-party retention, external API rate limits (`429`), and credential rotation risk during live grading.
3. **Defense-in-depth around untrusted inputs & outputs**:
   - Retrieved chunks and user questions are wrapped in `<retrieved_evidence>` and `<user_question>` XML delimiters with explicit system rules treating their contents as untrusted data.
   - Provider calls enforce explicit `httpx.Timeout` bounds (`90s`), low temperature (`0.1`), constrained JSON schema decoding, `Answer.model_validate_json` verification, retrieved-passage citation cross-checking, one automatic retry on failure, and a non-500 safe fallback.
   - Hosted credentials (`LLM_API_KEY`) are `repr=False` in `Settings`, gitignored (`*secret*.yaml`), and injected exclusively via `kubectl create secret generic rahbar-secret`.

## Options Considered
1. **`ollama-incluster` as default** — Supported by the same `OllamaProvider` code (changing only `OLLAMA_URL`), but running both `llama3.2:3b` and `nomic-embed-text` inside Docker Desktop's Linux VM lacks macOS Metal GPU acceleration (5–10x slower generation) and requires an 8+ GB Minikube VM footprint.
2. **Cloud-only `hosted` provider (Groq / Gemini / OpenRouter) as sole implementation** — Implemented and supported via `HostedProvider`, but relying exclusively on a third-party free tier introduces external network failure modes, rate limits during 18-question eval runs, and sends student queries off-premises.

## Consequences
- **Easier**: Swapping between local GPU-accelerated `ollama-host`, in-cluster Ollama, cloud `hosted` APIs, and offline `stub` CI takes a single ConfigMap key edit; zero API keys exist in Git history.
- **Harder / Watch-fors**: `ollama-host` requires `OLLAMA_HOST=0.0.0.0` on the host laptop and an explicit TCP `11434` egress rule in `NetworkPolicy`; embedding model parity between indexer and API is guarded in code by `/readyz` (`section 4.4`) rather than human memory.

