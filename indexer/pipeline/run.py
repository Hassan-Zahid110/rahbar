"""The indexer Job's entry point (Assignment 02 + Assignment 03 RAGOps Part A1 & A2).

    python -m pipeline.run --dummy
    python -m pipeline.run                                      # legacy or RAGOps pipeline
    python -m pipeline.run --verify --batch-dir corpus/batch_a  # Part A1 + A2 verification & incremental update
    python -m pipeline.run --delete-doc fees-2026.md            # Part A2 delete document (0 orphans proof)
    python -m pipeline.run --restore-version academic-rules 2026 # Part A2 restore superseded version
"""

from __future__ import annotations

import argparse
from dataclasses import replace
import json
import os
from pathlib import Path
import sys
import time
from typing import Any

from .config import IndexerSettings, get_settings
from .models import Chunk, Document


def log(msg: str, **fields: object) -> None:
    print(
        json.dumps(
            {
                "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "logger": "rahbar.indexer",
                "msg": msg,
                **fields,
            }
        ),
        flush=True,
    )


def _front_matter(path: Path) -> dict[str, str]:
    """Read `key: value` lines between leading '---' markers."""
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    meta: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        key, _, value = line.partition(":")
        meta[key.strip()] = value.strip().strip('"').strip("'")
    return meta


def discover(corpus_dir: str) -> list[tuple[Path, str, bool]]:
    """List (path, doc_version, superseded) for every document to index."""
    root_dir = Path(corpus_dir)
    index = root_dir / "_index.json"
    if index.exists():
        entries = json.loads(index.read_text(encoding="utf-8"))
        return [
            (
                root_dir / e["file"],
                str(e.get("doc_version", "unknown")),
                bool(e.get("superseded", False)),
            )
            for e in entries
        ]
    found = []
    for path in sorted(root_dir.glob("*")):
        if path.suffix.lower() not in {".pdf", ".md", ".html", ".txt"}:
            continue
        if path.name.lower().startswith("readme"):
            continue
        meta = _front_matter(path) if path.suffix.lower() == ".md" else {}
        found.append(
            (
                path,
                meta.get("doc_version", "unknown"),
                meta.get("superseded", "false").lower() == "true",
            )
        )
    return found


def run_pipeline(settings: IndexerSettings) -> int:
    """Standard 5-stage pipeline (used by baseline and unit tests)."""
    from .chunk import chunk
    from .clean import clean
    from .embed import embed
    from .extract import extract
    from .store import store

    documents = discover(settings.corpus_dir)
    if not documents:
        raise SystemExit(f"no documents found in {settings.corpus_dir}")
    all_chunks: list[Chunk] = []
    for path, doc_version, superseded in documents:
        doc = clean(extract(str(path), doc_version, superseded))
        pieces = chunk(doc, settings.chunk_size, settings.chunk_overlap)
        log("chunked", source=path.name, chunks=len(pieces))
        all_chunks.extend(pieces)
    vectors = embed([c.text for c in all_chunks], settings)
    return store(all_chunks, vectors, settings)


def run_verified_incremental_pipeline(
    settings: IndexerSettings,
    report_out: str | None = None,
    client: Any | None = None,
    print_table: bool = True,
) -> dict[str, Any]:
    """RAGOps Part A1 (Verification) + Part A2 (Incremental Update & Versioning)."""
    from .chunk import chunk
    from .clean import clean
    from .embed import embed, hash_embed
    from .extract import extract
    from .store import get_document_chunk_counts, store_incremental
    from .verify import (
        DataLakeManager,
        body_sha256,
        format_verification_table,
        verify_batch,
    )

    datalake = DataLakeManager(settings.data_dir)
    discovered = discover(settings.corpus_dir)
    if not discovered:
        raise SystemExit(f"no documents found in {settings.corpus_dir}")

    extracted_docs: list[tuple[Path, Document]] = []
    for path, doc_version, superseded in discovered:
        raw_doc = extract(str(path), doc_version, superseded)
        # Note: verify quality on raw extraction before clean strips control chars
        extracted_docs.append((path, raw_doc))

    ver_results, ver_summary = verify_batch(
        extracted_docs,
        datalake,
        near_dup_threshold=settings.near_dup_threshold,
    )

    if print_table:
        print(format_verification_table(ver_summary), flush=True)

    chunks_to_embed: list[Chunk] = []
    updated_sources: list[str] = []
    superseded_sources: list[str] = []
    unchanged_sources: list[str] = []
    new_sources: list[str] = []
    quarantined_sources: list[str] = []

    doc_map = {doc.source: (path, doc) for path, doc in extracted_docs}

    for res in ver_results:
        if res.overall == "fail" or res.action == "quarantine":
            quarantined_sources.append(res.source)
            log("document quarantined", source=res.source, action=res.action)
            continue

        path, raw_doc = doc_map[res.source]
        if res.action == "skip_unchanged":
            unchanged_sources.append(res.source)
            continue

        if res.action == "supersede_and_index" and res.supersedes_source:
            superseded_sources.append(res.supersedes_source)
            datalake.archive_superseded(res.supersedes_source)
            log(
                "archived superseded document",
                superseded_source=res.supersedes_source,
                new_source=res.source,
                new_version=res.doc_version,
            )

        if res.action == "index_update":
            updated_sources.append(res.source)
        else:
            new_sources.append(res.source)

        cleaned_doc = clean(raw_doc)
        pieces = chunk(cleaned_doc, settings.chunk_size, settings.chunk_overlap)
        log("chunked verified document", source=res.source, action=res.action, chunks=len(pieces))
        chunks_to_embed.extend(pieces)

        sha = body_sha256(raw_doc.full_text)
        vec = hash_embed(raw_doc.full_text, dim=384)
        datalake.commit_verified_document(path, raw_doc, sha, vec)

    datalake.save_state()

    vectors = embed([c.text for c in chunks_to_embed], settings) if chunks_to_embed else []
    store_stats = store_incremental(
        chunks_to_embed,
        vectors,
        settings,
        updated_sources=updated_sources,
        superseded_sources=superseded_sources,
        client=client,
    )
    doc_counts = get_document_chunk_counts(settings, client=client)

    ver_summary["incremental_update"] = {
        "new_documents_indexed": len(new_sources),
        "updated_documents_reindexed": len(updated_sources),
        "unchanged_documents_skipped": len(unchanged_sources),
        "superseded_documents_archived": len(superseded_sources),
        "quarantined_documents": len(quarantined_sources),
        "chunks_embedded_this_run": len(chunks_to_embed),
        **store_stats,
        "document_chunk_counts": doc_counts,
    }

    # Save report file per run
    batch_name = Path(settings.corpus_dir).name
    default_report_path = datalake.reports_dir / f"verification_report_{batch_name}.json"
    default_report_path.write_text(json.dumps(ver_summary, indent=2), encoding="utf-8")
    if report_out:
        out_p = Path(report_out)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(json.dumps(ver_summary, indent=2), encoding="utf-8")

    log(
        "incremental run summary",
        batch=batch_name,
        passed=ver_summary["passed"],
        quarantined=ver_summary["failed_quarantined"],
        unchanged_docs=len(unchanged_sources),
        chunks_embedded=len(chunks_to_embed),
        total_chunks_in_store=store_stats["total_chunks_in_store"],
    )
    return ver_summary


def delete_document_from_pipeline(
    source_name: str,
    settings: IndexerSettings,
    client: Any | None = None,
) -> dict[str, Any]:
    """Part A2: Delete a document from data lake and ChromaDB, proving 0 orphan chunks remain."""
    from .store import get_document_chunk_counts, store_incremental
    from .verify import DataLakeManager

    datalake = DataLakeManager(settings.data_dir)
    before_counts = get_document_chunk_counts(settings, client=client)
    store_stats = store_incremental(
        [],
        [],
        settings,
        deleted_sources=[source_name],
        client=client,
    )
    if source_name in datalake.entries:
        del datalake.entries[source_name]
        datalake.save_state()
    lake_file = datalake.lake_dir / source_name
    if lake_file.exists():
        lake_file.unlink()
    after_counts = get_document_chunk_counts(settings, client=client)
    orphan_count = after_counts.get(source_name, {}).get("chunk_count", 0)
    result = {
        "action": "delete_document",
        "deleted_source": source_name,
        "chunks_before": before_counts.get(source_name, {}).get("chunk_count", 0),
        "deleted_chunks": store_stats["deleted_chunks"],
        "orphan_chunks_remaining": orphan_count,
        "document_chunk_counts_after": after_counts,
    }
    log("deleted document", **result)
    return result


def restore_archived_version(
    policy_id: str,
    target_version: str,
    settings: IndexerSettings,
    client: Any | None = None,
) -> dict[str, Any]:
    """Part A2 Rollback Demo: Restore an archived superseded version and supersede the newer version."""
    from .store import get_client, get_document_chunk_counts, invalidate_semantic_cache
    from .verify import DataLakeManager

    datalake = DataLakeManager(settings.data_dir)
    chroma = client if client is not None else get_client(settings)
    collection = chroma.get_collection(name=settings.collection)
    got = collection.get(include=["metadatas", "documents", "embeddings"])
    all_ids: list[str] = list(got.get("ids") or [])
    all_metas: list[dict[str, Any]] = list(got.get("metadatas") or [])
    all_docs: list[str] = list(got.get("documents") or [])
    raw_embs = got.get("embeddings")
    all_embs: list[Any] = list(raw_embs) if raw_embs is not None else []

    restored_sources: set[str] = set()
    demoted_sources: set[str] = set()
    upd_ids: list[str] = []
    upd_docs: list[str] = []
    upd_embs: list[list[float]] = []
    upd_metas: list[dict[str, Any]] = []

    for idx, (cid, meta) in enumerate(zip(all_ids, all_metas)):
        m = dict(meta or {})
        doc_id = str(m.get("doc_id", ""))
        src = str(m.get("source", ""))
        ver = str(m.get("doc_version", ""))
        if doc_id == policy_id or src.startswith(policy_id):
            if ver == target_version:
                m["superseded"] = False
                restored_sources.add(src)
            else:
                m["superseded"] = True
                demoted_sources.add(src)
            upd_ids.append(cid)
            if idx < len(all_docs):
                upd_docs.append(all_docs[idx])
            if idx < len(all_embs):
                upd_embs.append([float(x) for x in all_embs[idx]])
            upd_metas.append(m)

    if upd_ids:
        write_fn = getattr(collection, "upsert", None) or collection.add
        write_fn(ids=upd_ids, documents=upd_docs, embeddings=upd_embs, metadatas=upd_metas)

    for src, entry in datalake.entries.items():
        if entry.policy_id == policy_id:
            entry.superseded = (entry.doc_version != target_version)
    datalake.save_state()
    invalidate_semantic_cache(settings)

    after_counts = get_document_chunk_counts(settings, client=client)
    res = {
        "action": "restore_version",
        "policy_id": policy_id,
        "restored_version": target_version,
        "restored_sources": sorted(restored_sources),
        "superseded_sources": sorted(demoted_sources),
        "chunks_updated": len(upd_ids),
        "document_chunk_counts": after_counts,
    }
    log("restored archived version", **res)
    return res


def main() -> int:
    parser = argparse.ArgumentParser(description="Build & verify the RAHBAR RAGOps index.")
    parser.add_argument("--dummy", action="store_true", help="write three fake chunks")
    parser.add_argument("--verify", action="store_true", help="run RAGOps Part A1+A2 verification and incremental update")
    parser.add_argument("--batch-dir", type=str, default="", help="override CORPUS_DIR for batch ingestion")
    parser.add_argument("--data-dir", type=str, default="", help="override DATA_DIR for data lake, quarantine, archive")
    parser.add_argument("--report-out", type=str, default="", help="path to write verification JSON report")
    parser.add_argument("--delete-doc", type=str, default="", help="delete a document by source name and prove 0 orphans")
    parser.add_argument("--restore-version", nargs=2, metavar=("POLICY_ID", "VERSION"), help="restore an archived version")
    parser.add_argument("--show-counts", action="store_true", help="print chunk counts by document id")
    args = parser.parse_args()

    settings = get_settings()
    if args.batch_dir:
        settings = replace(settings, corpus_dir=args.batch_dir)
    if args.data_dir:
        settings = replace(settings, data_dir=args.data_dir)

    use_verify = args.verify or os.environ.get("RAGOPS_VERIFY", "").lower() in {"1", "true", "yes"}

    log(
        "indexer starting",
        dummy=args.dummy,
        verify=use_verify,
        embed_model=settings.embed_model,
        collection=settings.collection,
        corpus_dir=settings.corpus_dir,
        data_dir=settings.data_dir,
        chroma=f"{settings.chroma_host}:{settings.chroma_port}",
        pod=os.environ.get("HOSTNAME", "-"),
    )
    started = time.perf_counter()
    try:
        if args.dummy:
            from .dummy import write_dummy_index
            from .store import get_client

            count = write_dummy_index(settings, get_client(settings))
        elif args.delete_doc:
            res = delete_document_from_pipeline(args.delete_doc, settings)
            print(json.dumps(res, indent=2), flush=True)
            count = sum(v["chunk_count"] for v in res["document_chunk_counts_after"].values())
        elif args.restore_version:
            pol_id, ver = args.restore_version
            res = restore_archived_version(pol_id, ver, settings)
            print(json.dumps(res, indent=2), flush=True)
            count = sum(v["chunk_count"] for v in res["document_chunk_counts"].values())
        elif args.show_counts:
            from .store import get_document_chunk_counts

            counts = get_document_chunk_counts(settings)
            print(json.dumps(counts, indent=2), flush=True)
            count = sum(v["chunk_count"] for v in counts.values())
        elif use_verify:
            summary = run_verified_incremental_pipeline(settings, report_out=args.report_out or None)
            count = summary["incremental_update"]["total_chunks_in_store"]
        else:
            count = run_pipeline(settings)
    except NotImplementedError as exc:
        log("indexer stage not implemented yet", error=str(exc))
        return 2
    log("indexer finished", chunks=count, seconds=round(time.perf_counter() - started, 2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
