"""Polite corpus downloader for Kubernetes Job initContainers (reads sources.yaml -> CORPUS_DIR).

When CORPUS_DIR already contains documents (e.g. CI fixture ConfigMap or a warm PVC),
this script exits immediately without touching the network.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, urlsplit

import httpx
import yaml  # type: ignore[import-untyped]

USER_AGENT = "RAHBAR-coursework-fetcher/1.0 (CS4032 student project; one request at a time)"
PAUSE_SECONDS = 2.0
DRIVE_VIEW = re.compile(r"https?://drive\.google\.com/file/d/([^/?#]+)")


def _normalise(url: str) -> str:
    match = DRIVE_VIEW.match(url)
    if match:
        return f"https://drive.google.com/uc?export=download&id={match.group(1)}"
    return quote(url, safe=":/?&=%#+,;@!$'()*~")


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:80] or "document"


def _guess_extension(url: str, content_type: str) -> str:
    ct = content_type.lower()
    if "pdf" in ct:
        return ".pdf"
    if "html" in ct:
        return ".html"
    suffix = Path(urlsplit(url).path).suffix.lower()
    return suffix if suffix in {".pdf", ".html", ".htm", ".docx", ".txt", ".md"} else ".bin"


def ensure_corpus(sources_path: Path, corpus_dir: Path) -> int:
    if os.environ.get("SKIP_FETCH", "").strip().lower() in {"1", "true", "yes"}:
        print("SKIP_FETCH set; using existing files in CORPUS_DIR.", flush=True)
        return 0

    corpus_dir.mkdir(parents=True, exist_ok=True)
    existing_docs = [
        p for p in corpus_dir.iterdir()
        if p.is_file() and p.suffix.lower() in {".pdf", ".md", ".html", ".txt"}
    ]
    index_path = corpus_dir / "_index.json"
    if existing_docs and (index_path.exists() or not sources_path.exists()):
        print(f"Found {len(existing_docs)} existing corpus files in {corpus_dir}; skipping fetch.", flush=True)
        return 0

    if not sources_path.exists():
        print(f"No sources file at {sources_path} and no existing docs in {corpus_dir}", file=sys.stderr)
        return 1

    data = yaml.safe_load(sources_path.read_text(encoding="utf-8")) or {}
    docs = data.get("documents") or []
    entries = []
    with httpx.Client(
        headers={"User-Agent": USER_AGENT},
        follow_redirects=True,
        timeout=httpx.Timeout(60.0, connect=15.0),
    ) as client:
        for doc in docs:
            name = doc["name"]
            url = _normalise(doc["url"])
            resp = client.get(url)
            resp.raise_for_status()
            ct = resp.headers.get("content-type", "")
            filename = _slug(name) + _guess_extension(url, ct)
            (corpus_dir / filename).write_bytes(resp.content)
            entries.append(
                {
                    "name": name,
                    "url": url,
                    "file": filename,
                    "bytes": len(resp.content),
                    "sha256": hashlib.sha256(resp.content).hexdigest(),
                    "content_type": ct.split(";")[0],
                    "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                    "doc_version": str(doc.get("doc_version", "unknown")),
                    "superseded": bool(doc.get("superseded", False)),
                }
            )
            print(f"Fetched {filename} ({len(resp.content):,} bytes)", flush=True)
            time.sleep(PAUSE_SECONDS)

    index_path.write_text(json.dumps(entries, indent=2), encoding="utf-8")
    return 0


def main() -> int:
    sources = Path(os.environ.get("SOURCES_YAML", "/etc/rahbar-corpus/sources.yaml"))
    corpus_dir = Path(os.environ.get("CORPUS_DIR", "/corpus"))
    return ensure_corpus(sources, corpus_dir)


if __name__ == "__main__":
    sys.exit(main())

