# ruff: noqa: E402
"""Part A Runner: Executes A1 Verification + A2 Incremental Update on Batch A and Batch B,
demonstrates 0-chunk re-run on unchanged corpus, single-doc update, deletion with 0 orphans,
and version archival + rollback. Writes reports to eval/results/.
"""

from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import shutil
import sys
from typing import Any

# Add indexer to path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "indexer"))

from pipeline.config import IndexerSettings, get_settings
from pipeline.run import (
    delete_document_from_pipeline,
    restore_archived_version,
    run_verified_incremental_pipeline,
)
from pipeline.store import get_document_chunk_counts


class InMemoryCollection:
    def __init__(self, name: str, metadata: dict[str, Any] | None = None) -> None:
        self.name = name
        self.metadata = metadata or {}
        self._rows: dict[str, dict[str, Any]] = {}

    def count(self) -> int:
        return len(self._rows)

    def get(self, include: list[str] | None = None) -> dict[str, Any]:
        ids = list(self._rows.keys())
        return {
            "ids": ids,
            "documents": [self._rows[i]["document"] for i in ids],
            "embeddings": [self._rows[i]["embedding"] for i in ids],
            "metadatas": [self._rows[i]["metadata"] for i in ids],
        }

    def upsert(
        self,
        ids: list[str],
        documents: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict[str, Any]],
    ) -> None:
        for cid, doc, emb, meta in zip(ids, documents, embeddings, metadatas):
            self._rows[cid] = {
                "document": doc,
                "embedding": list(emb),
                "metadata": dict(meta),
            }

    def add(
        self,
        ids: list[str],
        documents: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict[str, Any]],
    ) -> None:
        self.upsert(ids, documents, embeddings, metadatas)

    def delete(self, ids: list[str] | None = None) -> None:
        for cid in ids or []:
            self._rows.pop(cid, None)


class InMemoryChromaClient:
    def __init__(self) -> None:
        self.collections: dict[str, InMemoryCollection] = {}

    def get_collection(self, name: str) -> InMemoryCollection:
        if name not in self.collections:
            raise ValueError(f"Collection {name} does not exist")
        return self.collections[name]

    def create_collection(self, name: str, metadata: dict[str, Any] | None = None) -> InMemoryCollection:
        col = InMemoryCollection(name=name, metadata=metadata)
        self.collections[name] = col
        return col

    def delete_collection(self, name: str) -> None:
        self.collections.pop(name, None)


def get_chroma_or_memory(settings: IndexerSettings, use_live: bool = False) -> Any:
    if use_live:
        from pipeline.store import get_client
        return get_client(settings, attempts=3, delay_s=1.0)
    return InMemoryChromaClient()


def run_all_part_a(use_live_chroma: bool = False, data_dir_override: str = "") -> dict[str, Any]:
    results_dir = REPO_ROOT / "eval" / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    data_dir = Path(data_dir_override) if data_dir_override else (REPO_ROOT / "data_store")
    if data_dir.exists():
        shutil.rmtree(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)

    base_settings = replace(
        get_settings(),
        embed_model="hash-384",
        chunk_size=300,
        chunk_overlap=50,
        data_dir=str(data_dir),
        near_dup_threshold=0.90,
    )
    client = get_chroma_or_memory(base_settings, use_live=use_live_chroma)

    print("\n>>> [STEP A1.1] Ingesting Batch A (Clean Baseline Corpus: 6 Documents)...")
    s_batch_a = replace(base_settings, corpus_dir=str(REPO_ROOT / "corpus" / "batch_a"))
    rep_a1 = run_verified_incremental_pipeline(
        s_batch_a,
        report_out=str(results_dir / "part_a_batch_a_report.json"),
        client=client,
    )

    print("\n>>> [STEP A2.1] Re-running Ingestion on Unchanged Batch A (Must Embed 0 Chunks)...")
    rep_a2_unchanged = run_verified_incremental_pipeline(
        s_batch_a,
        report_out=str(results_dir / "part_a_unchanged_rerun_report.json"),
        client=client,
    )
    inc_u = rep_a2_unchanged["incremental_update"]
    print(
        f"UNCHANGED RERUN PROOF -> unchanged_documents_skipped: {inc_u['unchanged_documents_skipped']}, "
        f"chunks_embedded_this_run: {inc_u['chunks_embedded_this_run']}, "
        f"total_chunks_in_store: {inc_u['total_chunks_in_store']}"
    )

    print("\n>>> [STEP A1.2 & A2.2] Ingesting Batch B (11 Documents with 7 Planted Failing Docs, 1 Newer Version, 1 Injected, 2 New)...")
    s_batch_b = replace(base_settings, corpus_dir=str(REPO_ROOT / "corpus" / "batch_b"))
    rep_b = run_verified_incremental_pipeline(
        s_batch_b,
        report_out=str(results_dir / "part_a_batch_b_report.json"),
        client=client,
    )

    print("\n>>> [STEP A2.3] Demonstrating Single Changed Document Update (Replaces Only Its Own Chunks)...")
    tmp_mod_dir = data_dir / "tmp_modified_batch"
    tmp_mod_dir.mkdir(parents=True, exist_ok=True)
    mod_doc = REPO_ROOT / "corpus" / "batch_a" / "library-and-lab-rules-2026.md"
    mod_text = mod_doc.read_text(encoding="utf-8") + "\n\n3.2 Extended exam-week lab hours run until 23:00.\n"
    (tmp_mod_dir / "library-and-lab-rules-2026.md").write_text(mod_text, encoding="utf-8")
    s_mod = replace(base_settings, corpus_dir=str(tmp_mod_dir))
    rep_mod = run_verified_incremental_pipeline(s_mod, client=client, print_table=False)
    print(
        f"CHANGED DOC PROOF -> updated_documents_reindexed: {rep_mod['incremental_update']['updated_documents_reindexed']}, "
        f"chunks_embedded_this_run: {rep_mod['incremental_update']['chunks_embedded_this_run']}, "
        f"deleted_old_chunks: {rep_mod['incremental_update']['deleted_chunks']}"
    )

    print("\n>>> [STEP A2.4] Demonstrating Document Deletion (Zero Orphan Chunks Proof)...")
    del_res = delete_document_from_pipeline("course-registration-add-drop-2026.md", base_settings, client=client)
    print(
        f"DELETE DOC PROOF -> deleted_source: {del_res['deleted_source']}, "
        f"chunks_before: {del_res['chunks_before']}, "
        f"deleted_chunks: {del_res['deleted_chunks']}, "
        f"orphan_chunks_remaining: {del_res['orphan_chunks_remaining']}"
    )
    # Re-add course-registration-add-drop-2026.md so full corpus remains intact for downstream tests
    tmp_readd = data_dir / "tmp_readd_batch"
    tmp_readd.mkdir(parents=True, exist_ok=True)
    shutil.copy2(REPO_ROOT / "corpus" / "batch_b" / "course-registration-add-drop-2026.md", tmp_readd / "course-registration-add-drop-2026.md")
    run_verified_incremental_pipeline(replace(base_settings, corpus_dir=str(tmp_readd)), client=client, print_table=False)

    print("\n>>> [STEP A2.5] Demonstrating Superseded Version Archival & Rollback Restore (2027 -> 2026 -> 2027)...")
    rollback_to_2026 = restore_archived_version("academic-rules", "2026", base_settings, client=client)
    print(
        f"ROLLBACK TO 2026 PROOF -> restored_sources: {rollback_to_2026['restored_sources']}, "
        f"superseded_sources: {rollback_to_2026['superseded_sources']}, "
        f"academic-rules-2026 superseded={rollback_to_2026['document_chunk_counts']['academic-rules-2026.md']['superseded']}"
    )
    restore_to_2027 = restore_archived_version("academic-rules", "2027", base_settings, client=client)
    print(
        f"FORWARD RESTORE TO 2027 -> restored_sources: {restore_to_2027['restored_sources']}, "
        f"academic-rules-2027 superseded={restore_to_2027['document_chunk_counts']['academic-rules-2027.md']['superseded']}"
    )

    final_counts = get_document_chunk_counts(base_settings, client=client)
    print("\n>>> [FINAL CHUNK COUNTS BY DOCUMENT ID]:")
    for src, info in final_counts.items():
        print(f"  - {src:<36} | doc_id={info['doc_id']:<22} | v={info['doc_version']:<4} | superseded={str(info['superseded']):<5} | chunks={info['chunk_count']}")

    quarantined_files = sorted(p.name for p in (data_dir / "quarantine").glob("*"))
    archived_files = sorted(p.name for p in (data_dir / "archive").glob("*"))
    print(f"\nQuarantined files ({len(quarantined_files)}): {quarantined_files}")
    print(f"Archived files    ({len(archived_files)}): {archived_files}")

    full_part_a_summary = {
        "batch_a_initial": rep_a1,
        "batch_a_unchanged_rerun": rep_a2_unchanged,
        "batch_b_ingestion": rep_b,
        "single_doc_update": rep_mod["incremental_update"],
        "delete_doc_zero_orphans": del_res,
        "rollback_demo_2026": rollback_to_2026,
        "restore_2027": restore_to_2027,
        "quarantined_files": quarantined_files,
        "archived_files": archived_files,
        "final_document_chunk_counts": final_counts,
    }
    out_file = results_dir / "part_a_complete_summary.json"
    out_file.write_text(json.dumps(full_part_a_summary, indent=2), encoding="utf-8")
    return full_part_a_summary


if __name__ == "__main__":
    use_live = "--live" in sys.argv
    run_all_part_a(use_live_chroma=use_live)
