#!/usr/bin/env python3
"""Embed retrieval documents with ``openai/test_embedding_small.py``.

Outputs are backend-ready:

- ``artifacts/vectors/<approach>/embeddings.npy``: float32 matrix
- ``artifacts/vectors/<approach>/metadata.jsonl``: vector index to document metadata
- ``artifacts/vectors/<approach>/manifest.json``: model, dimensions, counts, hashes
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
HELPER_PATH = ROOT / "openai" / "test_embedding_small.py"
RETRIEVAL_DIR = ROOT / "artifacts" / "retrieval"
VECTOR_DIR = ROOT / "artifacts" / "vectors"


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def progress(label: str, current: int, total: int) -> None:
    if total <= 0:
        return
    width = 28
    filled = int(width * current / total)
    bar = "#" * filled + "-" * (width - filled)
    percent = 100 * current / total
    end = "\n" if current >= total else "\r"
    print(f"{label} [{bar}] {current}/{total} ({percent:5.1f}%)", end=end, file=sys.stderr, flush=True)


def file_sha256(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_embedding_helper() -> Any:
    if not HELPER_PATH.exists():
        raise FileNotFoundError(f"Embedding helper not found: {HELPER_PATH}")
    spec = importlib.util.spec_from_file_location("semantics_openai_embedding_helper", HELPER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load embedding helper from {HELPER_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def sanitize_model_name(model: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", model).strip("_")


def read_documents(path: Path, *, limit: int | None = None) -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            doc = json.loads(line)
            if not str(doc.get("text", "")).strip():
                raise ValueError(f"{path}:{line_number} has no non-empty text field")
            docs.append(doc)
            if limit is not None and len(docs) >= limit:
                break
    return docs


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


def build_embeddings_for_approach(
    *,
    approach: str,
    input_path: Path,
    output_dir: Path,
    model: str,
    batch_size: int,
    dimensions: int | None,
    limit: int | None,
    overwrite: bool,
    dry_run: bool,
) -> dict[str, Any]:
    docs = read_documents(input_path, limit=limit)
    if not docs:
        raise ValueError(f"No documents loaded from {input_path}")

    approach_dir = output_dir / approach
    embeddings_path = approach_dir / "embeddings.npy"
    metadata_path = approach_dir / "metadata.jsonl"
    manifest_path = approach_dir / "manifest.json"
    if not overwrite and any(path.exists() for path in [embeddings_path, metadata_path, manifest_path]):
        raise FileExistsError(f"{approach_dir} already has vector outputs; pass --overwrite to rebuild.")

    planned = {
        "approach": approach,
        "document_count": len(docs),
        "input_path": str(input_path.relative_to(ROOT)),
        "input_sha256": file_sha256(input_path),
        "model": model,
        "dimensions_requested": dimensions,
        "batch_size": batch_size,
        "outputs": {
            "embeddings": str(embeddings_path.relative_to(ROOT)),
            "metadata": str(metadata_path.relative_to(ROOT)),
            "manifest": str(manifest_path.relative_to(ROOT)),
        },
    }
    if dry_run:
        return planned | {"dry_run": True}

    helper = load_embedding_helper()
    client = helper.make_client()
    approach_dir.mkdir(parents=True, exist_ok=True)
    tmp_embeddings = approach_dir / "embeddings.npy.tmp"
    tmp_metadata = approach_dir / "metadata.jsonl.tmp"

    mmap: np.memmap | None = None
    vector_dim: int | None = None
    written = 0
    with tmp_metadata.open("w", encoding="utf-8") as metadata_handle:
        for start in range(0, len(docs), batch_size):
            batch_docs = docs[start : start + batch_size]
            texts = [str(doc["text"]) for doc in batch_docs]
            vectors = helper.embed_batch_with_retries(
                client,
                texts,
                model=model,
                dimensions=dimensions,
            )
            arr = np.asarray(vectors, dtype=np.float32)
            if arr.ndim != 2:
                raise RuntimeError(f"Embedding batch returned unexpected shape {arr.shape}")
            if mmap is None:
                vector_dim = int(arr.shape[1])
                mmap = np.lib.format.open_memmap(
                    tmp_embeddings,
                    mode="w+",
                    dtype=np.float32,
                    shape=(len(docs), vector_dim),
                )
            elif arr.shape[1] != vector_dim:
                raise RuntimeError(f"Embedding dimension changed from {vector_dim} to {arr.shape[1]}")

            mmap[start : start + len(batch_docs), :] = arr
            for offset, doc in enumerate(batch_docs):
                vector_index = start + offset
                metadata_record = {
                    "vector_index": vector_index,
                    "document_id": doc.get("id"),
                    "approach": doc.get("approach"),
                    "doc_type": doc.get("doc_type"),
                    "text": doc.get("text"),
                    "metadata": doc.get("metadata") or {},
                }
                metadata_handle.write(json.dumps(metadata_record, ensure_ascii=False, sort_keys=True) + "\n")
            written += len(batch_docs)
            progress(f"{approach} embeddings", written, len(docs))

    if mmap is not None:
        mmap.flush()
        del mmap
    tmp_embeddings.replace(embeddings_path)
    tmp_metadata.replace(metadata_path)

    manifest = planned | {
        "generated_at": now_iso(),
        "dry_run": False,
        "document_count": written,
        "embedding_dimensions": vector_dim,
        "dtype": "float32",
        "output_sha256": {
            "embeddings": file_sha256(embeddings_path),
            "metadata": file_sha256(metadata_path),
        },
    }
    write_json(manifest_path, manifest)
    return manifest


def default_input_for_approach(approach: str) -> Path:
    if approach == "standard_rag":
        return RETRIEVAL_DIR / "standard_rag_documents.jsonl"
    if approach == "kg_rag":
        return RETRIEVAL_DIR / "kg_rag_documents.jsonl"
    raise ValueError(f"Unknown approach: {approach}")


def main() -> int:
    helper = load_embedding_helper()
    parser = argparse.ArgumentParser(description="Build OpenAI embedding matrices for RAG corpora.")
    parser.add_argument("--approach", action="append", choices=["standard_rag", "kg_rag"], default=None)
    parser.add_argument("--standard-input", type=Path, default=default_input_for_approach("standard_rag"))
    parser.add_argument("--kg-input", type=Path, default=default_input_for_approach("kg_rag"))
    parser.add_argument("--output-dir", type=Path, default=VECTOR_DIR)
    parser.add_argument("--model", default=helper.DEFAULT_MODEL)
    parser.add_argument("--batch-size", type=int, default=helper.DEFAULT_BATCH_SIZE)
    parser.add_argument("--dimensions", type=int, default=None)
    parser.add_argument("--limit", type=int, default=None, help="Embed only the first N docs for smoke testing.")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    approaches = args.approach or ["standard_rag", "kg_rag"]
    manifests = []
    for approach in approaches:
        input_path = args.standard_input if approach == "standard_rag" else args.kg_input
        manifest = build_embeddings_for_approach(
            approach=approach,
            input_path=input_path,
            output_dir=args.output_dir,
            model=args.model,
            batch_size=args.batch_size,
            dimensions=args.dimensions,
            limit=args.limit,
            overwrite=args.overwrite,
            dry_run=args.dry_run,
        )
        manifests.append(manifest)
        if args.dry_run:
            print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))

    if not args.dry_run:
        print("Built embedding outputs:")
        for manifest in manifests:
            print(
                f"- {manifest['approach']}: {manifest['document_count']} docs, "
                f"{manifest['embedding_dimensions']} dims -> {manifest['outputs']['embeddings']}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
