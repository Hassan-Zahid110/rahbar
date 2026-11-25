"""Part A (RAGOps 4.2.1 - 4.2.4): Data Verification Stage & Data Lake Incremental State.

Runs after extraction and before chunking. Evaluates four mandatory checks per document:
  1. quality      (empty, garbled, or failed extraction)
  2. completeness (required metadata: source, title, date/version, page_count; text not truncated)
  3. recency      (detects newer or stale version of the same policy document)
  4. uniqueness   (exact duplicate by SHA-256 hash, near-duplicate by embedding cosine similarity)

Failed documents are moved/copied to the quarantine folder and excluded from indexing.
Produces a structured verification report per run (JSON + formatted terminal table).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import time
from typing import Any

from .embed import hash_embed
from .models import Document

TRUNCATION_MARKERS = ("[TRUNCATED", "[EOF_ERROR", "...[CUT]")
TERMINAL_PUNCT = (".", "!", "?", ":", "|", "\"", "'", ")", "]")


def cosine_sim(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def normalize_body(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def body_sha256(text: str) -> str:
    return hashlib.sha256(normalize_body(text).encode("utf-8")).hexdigest()


def canonical_policy_id(doc: Document) -> str:
    if doc.policy_id:
        return doc.policy_id.strip().lower()
    stem = Path(doc.source).stem.lower()
    # Strip trailing 4-digit year or version tag
    stem = re.sub(r"-(?:19|20)\d{2}(?:-[a-z0-9]+)?$", "", stem)
    return stem


@dataclass
class CheckOutcome:
    status: str  # "pass" or "fail"
    reason: str


@dataclass
class DocumentVerificationResult:
    source: str
    policy_id: str
    doc_version: str
    overall: str  # "pass" or "fail"
    action: str   # "index_new", "index_update", "skip_unchanged", "supersede_and_index", "quarantine"
    sha256: str
    checks: dict[str, CheckOutcome]
    supersedes_source: str | None = None
    quarantine_path: str | None = None


@dataclass
class DataLakeEntry:
    source: str
    policy_id: str
    title: str
    doc_version: str
    date: str
    page_count: int
    sha256: str
    embedding: list[float]
    superseded: bool = False
    archived_path: str | None = None
    updated_at: str = ""


class DataLakeManager:
    """Manages persistent data lake state, quarantine folder, and archived versions on PVC."""

    def __init__(self, data_dir: str) -> None:
        self.root = Path(data_dir)
        self.lake_dir = self.root / "data_lake"
        self.quarantine_dir = self.root / "quarantine"
        self.archive_dir = self.root / "archive"
        self.reports_dir = self.root / "reports"
        for d in (self.lake_dir, self.quarantine_dir, self.archive_dir, self.reports_dir):
            d.mkdir(parents=True, exist_ok=True)
        self.state_file = self.lake_dir / "manifest_state.json"
        self.entries: dict[str, DataLakeEntry] = self._load_state()

    def _load_state(self) -> dict[str, DataLakeEntry]:
        if not self.state_file.exists():
            return {}
        try:
            raw = json.loads(self.state_file.read_text(encoding="utf-8"))
            out: dict[str, DataLakeEntry] = {}
            for src, item in raw.get("documents", {}).items():
                out[src] = DataLakeEntry(**item)
            return out
        except Exception:
            return {}

    def save_state(self) -> None:
        payload = {
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "documents": {src: asdict(entry) for src, entry in self.entries.items()},
        }
        self.state_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def quarantine_file(self, src_path: Path) -> Path:
        dest = self.quarantine_dir / src_path.name
        if src_path.exists():
            shutil.copy2(src_path, dest)
        return dest

    def archive_superseded(self, old_source: str) -> Path | None:
        lake_file = self.lake_dir / old_source
        dest = self.archive_dir / old_source
        if lake_file.exists():
            shutil.copy2(lake_file, dest)
        if old_source in self.entries:
            self.entries[old_source].superseded = True
            self.entries[old_source].archived_path = str(dest)
        return dest if dest.exists() else None

    def commit_verified_document(self, src_path: Path, doc: Document, sha: str, vec: list[float]) -> None:
        dest = self.lake_dir / src_path.name
        if src_path.exists():
            shutil.copy2(src_path, dest)
        self.entries[doc.source] = DataLakeEntry(
            source=doc.source,
            policy_id=canonical_policy_id(doc),
            title=doc.title or doc.source,
            doc_version=doc.doc_version,
            date=doc.date or doc.doc_version,
            page_count=doc.page_count or len(doc.pages),
            sha256=sha,
            embedding=vec,
            superseded=doc.superseded,
            updated_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        )


def check_quality(doc: Document) -> CheckOutcome:
    text = doc.full_text
    if not text or not text.strip():
        return CheckOutcome("fail", "empty_extraction: 0 characters extracted")
    if "\ufffd" in text or "\x00" in text:
        printable = sum(1 for c in text if c.isprintable() or c in "\n\r\t")
        ratio = printable / max(1, len(text))
        return CheckOutcome(
            "fail",
            f"garbled_or_corrupt_extraction: contains replacement/null bytes (printable_ratio={ratio:.2f})",
        )
    alnum = sum(1 for c in text if c.isalnum())
    if alnum < 40:
        return CheckOutcome("fail", f"insufficient_content: only {alnum} alphanumeric chars (< 40)")
    return CheckOutcome("pass", f"clean_extraction: {alnum} alphanumeric chars across {len(doc.pages)} page(s)")


def check_completeness(doc: Document) -> CheckOutcome:
    # Required metadata: source, title, date or version, page count
    missing: list[str] = []
    if not doc.source:
        missing.append("source")
    if not doc.title:
        missing.append("title")
    if (not doc.doc_version or doc.doc_version == "unknown") and not doc.date:
        missing.append("doc_version/date")
    if doc.page_count <= 0:
        missing.append("page_count")
    if missing:
        return CheckOutcome("fail", f"missing_required_metadata: missing {missing}")

    text = doc.full_text.strip()
    for marker in TRUNCATION_MARKERS:
        if marker in text:
            return CheckOutcome("fail", f"text_truncated: detected truncation marker {marker!r}")
    if text and not text.endswith(TERMINAL_PUNCT):
        last_line = text.splitlines()[-1].strip()
        if not last_line.startswith("#") and not last_line.endswith(TERMINAL_PUNCT):
            return CheckOutcome("fail", f"text_truncated: trailing line lacks terminal punctuation ({last_line[-24:]!r})")
    return CheckOutcome(
        "pass",
        f"metadata_complete: title={doc.title!r}, version={doc.doc_version}, pages={doc.page_count}",
    )


def check_recency(
    doc: Document,
    active_by_policy: dict[str, DataLakeEntry],
) -> tuple[CheckOutcome, str | None]:
    pol_id = canonical_policy_id(doc)
    incoming_ver = str(doc.doc_version or doc.date or "0").strip()
    existing = active_by_policy.get(pol_id)
    if existing is None:
        return CheckOutcome("pass", f"current_version: new policy family {pol_id!r} (v{incoming_ver})"), None

    existing_ver = str(existing.doc_version or existing.date or "0").strip()
    if incoming_ver < existing_ver:
        return (
            CheckOutcome(
                "fail",
                f"stale_version: incoming v{incoming_ver} < active v{existing_ver} ({existing.source})",
            ),
            None,
        )
    if incoming_ver > existing_ver and existing.source != doc.source:
        return (
            CheckOutcome(
                "pass",
                f"newer_version_detected: v{incoming_ver} supersedes {existing.source} (v{existing_ver})",
            ),
            existing.source,
        )
    return CheckOutcome("pass", f"current_version: v{incoming_ver} matches active policy {pol_id!r}"), None


def check_uniqueness(
    doc: Document,
    sha: str,
    vec: list[float],
    datalake: DataLakeManager,
    batch_seen_hashes: dict[str, str],
    batch_seen_vecs: dict[str, tuple[str, list[float]]],
    near_dup_threshold: float = 0.90,
) -> tuple[CheckOutcome, str]:
    pol_id = canonical_policy_id(doc)

    # Case 1: Re-running on exact same filename already in data lake
    if doc.source in datalake.entries and not datalake.entries[doc.source].superseded:
        existing_entry = datalake.entries[doc.source]
        if existing_entry.sha256 == sha:
            return (
                CheckOutcome("pass", "unchanged_existing_document: sha256 matches active data lake entry"),
                "skip_unchanged",
            )
        return (
            CheckOutcome("pass", "modified_existing_document: content updated for existing source"),
            "index_update",
        )

    # Case 2: Exact duplicate hash check against active data lake or earlier in current batch
    for active_src, entry in datalake.entries.items():
        if entry.superseded:
            continue
        if active_src != doc.source and entry.sha256 == sha:
            return (
                CheckOutcome("fail", f"exact_duplicate_hash: sha256 matches active document {active_src}"),
                "quarantine",
            )
    for seen_src, seen_sha in batch_seen_hashes.items():
        if seen_src != doc.source and seen_sha == sha:
            return (
                CheckOutcome("fail", f"exact_duplicate_hash: sha256 matches batch document {seen_src}"),
                "quarantine",
            )

    # Case 3: Near-duplicate embedding similarity check against active docs of different policy_id
    max_sim = 0.0
    max_src = ""
    for active_src, entry in datalake.entries.items():
        if entry.superseded or active_src == doc.source:
            continue
        # Intentional newer version of the same policy_id is handled by recency/superseding, not duplicate failure
        if entry.policy_id == pol_id and str(doc.doc_version) > str(entry.doc_version):
            continue
        sim = cosine_sim(vec, entry.embedding)
        if sim > max_sim:
            max_sim = sim
            max_src = active_src

    for seen_src, (seen_pol, seen_vec) in batch_seen_vecs.items():
        if seen_src == doc.source:
            continue
        if seen_pol == pol_id:
            continue
        sim = cosine_sim(vec, seen_vec)
        if sim > max_sim:
            max_sim = sim
            max_src = seen_src

    if max_sim >= near_dup_threshold:
        return (
            CheckOutcome(
                "fail",
                f"near_duplicate_embedding: cosine_sim={max_sim:.4f} >= {near_dup_threshold:.2f} with {max_src}",
            ),
            "quarantine",
        )

    return (
        CheckOutcome(
            "pass",
            f"unique_content: max_cosine_sim={max_sim:.4f} < {near_dup_threshold:.2f}",
        ),
        "index_new",
    )


def verify_batch(
    extracted_docs: list[tuple[Path, Document]],
    datalake: DataLakeManager,
    near_dup_threshold: float = 0.90,
) -> tuple[list[DocumentVerificationResult], dict[str, Any]]:
    """Run A1 verification checks on all extracted documents in a batch."""
    results: list[DocumentVerificationResult] = []
    active_by_policy: dict[str, DataLakeEntry] = {
        e.policy_id: e for e in datalake.entries.values() if not e.superseded
    }
    batch_seen_hashes: dict[str, str] = {}
    batch_seen_vecs: dict[str, tuple[str, list[float]]] = {}

    for path, doc in extracted_docs:
        sha = body_sha256(doc.full_text)
        vec = hash_embed(doc.full_text, dim=384)
        pol_id = canonical_policy_id(doc)

        q_out = check_quality(doc)
        c_out = check_completeness(doc)
        r_out, supersedes_src = check_recency(doc, active_by_policy)
        u_out, u_action = check_uniqueness(
            doc,
            sha,
            vec,
            datalake,
            batch_seen_hashes,
            batch_seen_vecs,
            near_dup_threshold=near_dup_threshold,
        )

        checks = {
            "quality": q_out,
            "completeness": c_out,
            "recency": r_out,
            "uniqueness": u_out,
        }
        passed = all(chk.status == "pass" for chk in checks.values())

        quarantine_path: str | None = None
        if not passed:
            action = "quarantine"
            q_dest = datalake.quarantine_file(path)
            quarantine_path = str(q_dest)
        else:
            if supersedes_src:
                action = "supersede_and_index"
            else:
                action = u_action
            batch_seen_hashes[doc.source] = sha
            batch_seen_vecs[doc.source] = (pol_id, vec)
            # Update active_by_policy in-memory so later docs in the same batch see the newest version
            active_by_policy[pol_id] = DataLakeEntry(
                source=doc.source,
                policy_id=pol_id,
                title=doc.title or doc.source,
                doc_version=doc.doc_version,
                date=doc.date or doc.doc_version,
                page_count=doc.page_count or len(doc.pages),
                sha256=sha,
                embedding=vec,
                superseded=False,
            )

        results.append(
            DocumentVerificationResult(
                source=doc.source,
                policy_id=pol_id,
                doc_version=doc.doc_version,
                overall="pass" if passed else "fail",
                action=action,
                sha256=sha[:16],
                checks=checks,
                supersedes_source=supersedes_src,
                quarantine_path=quarantine_path,
            )
        )

    summary = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total_documents": len(results),
        "passed": sum(1 for r in results if r.overall == "pass"),
        "failed_quarantined": sum(1 for r in results if r.overall == "fail"),
        "failures_by_check": {
            chk_name: sum(1 for r in results if r.checks[chk_name].status == "fail")
            for chk_name in ("quality", "completeness", "recency", "uniqueness")
        },
        "actions": {
            act: sum(1 for r in results if r.action == act)
            for act in ("index_new", "index_update", "skip_unchanged", "supersede_and_index", "quarantine")
        },
        "results": [
            {
                "source": r.source,
                "policy_id": r.policy_id,
                "doc_version": r.doc_version,
                "overall": r.overall,
                "action": r.action,
                "sha256": r.sha256,
                "supersedes_source": r.supersedes_source,
                "quarantine_path": r.quarantine_path,
                "checks": {k: asdict(v) for k, v in r.checks.items()},
            }
            for r in results
        ],
    }
    return results, summary


def format_verification_table(summary: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("=" * 118)
    lines.append(
        f"RAGOPS PART A1 VERIFICATION REPORT | Total: {summary['total_documents']} | "
        f"Passed: {summary['passed']} | Quarantined: {summary['failed_quarantined']}"
    )
    lines.append("-" * 118)
    header = f"{'Document':<34} | {'Qual':<4} | {'Comp':<4} | {'Recn':<4} | {'Uniq':<4} | {'Overall':<7} | {'Action / Reason'}"
    lines.append(header)
    lines.append("-" * 118)
    for item in summary["results"]:
        chks = item["checks"]
        q_s = chks["quality"]["status"].upper()
        c_s = chks["completeness"]["status"].upper()
        r_s = chks["recency"]["status"].upper()
        u_s = chks["uniqueness"]["status"].upper()
        ov = item["overall"].upper()
        # Pick primary reason (first failing check reason, or key pass note)
        failed_reasons = [
            f"{k}: {v['reason']}"
            for k, v in chks.items()
            if v["status"] == "fail"
        ]
        if failed_reasons:
            reason_str = f"[{item['action']}] " + "; ".join(failed_reasons)
        elif item["action"] == "supersede_and_index":
            reason_str = f"[supersede] {chks['recency']['reason']}"
        elif item["action"] == "skip_unchanged":
            reason_str = f"[unchanged] {chks['uniqueness']['reason']}"
        else:
            reason_str = f"[{item['action']}] all 4 checks passed"
        lines.append(
            f"{item['source']:<34} | {q_s:<4} | {c_s:<4} | {r_s:<4} | {u_s:<4} | {ov:<7} | {reason_str}"
        )
    lines.append("=" * 118)
    return "\n".join(lines)
