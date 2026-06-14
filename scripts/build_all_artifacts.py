#!/usr/bin/env python3
"""Build KG, retrieval corpora, and optional OpenAI vector artifacts."""

from __future__ import annotations

import argparse
from pathlib import Path

from build_kg import ARTIFACT_DIR as KG_DIR
from build_kg import build_graph
from build_openai_embeddings import VECTOR_DIR, build_embeddings_for_approach, default_input_for_approach, load_embedding_helper
from build_retrieval_corpus import RETRIEVAL_DIR, build_corpora


def main() -> int:
    helper = load_embedding_helper()
    parser = argparse.ArgumentParser(description="Build all pre-backend SEMANTiCS RAG/KG-RAG artifacts.")
    parser.add_argument("--kg-dir", type=Path, default=KG_DIR)
    parser.add_argument("--retrieval-dir", type=Path, default=RETRIEVAL_DIR)
    parser.add_argument("--vector-dir", type=Path, default=VECTOR_DIR)
    parser.add_argument("--include-hospitalization-slices", action="store_true")
    parser.add_argument("--include-deep-infectious-slices", action="store_true")
    parser.add_argument("--skip-embeddings", action="store_true")
    parser.add_argument("--dry-run-embeddings", action="store_true")
    parser.add_argument("--model", default=helper.DEFAULT_MODEL)
    parser.add_argument("--batch-size", type=int, default=helper.DEFAULT_BATCH_SIZE)
    parser.add_argument("--dimensions", type=int, default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--overwrite-vectors", action="store_true")
    args = parser.parse_args()

    kg_manifest = build_graph(args.kg_dir)
    print(f"KG built: {kg_manifest['node_count']} nodes, {kg_manifest['edge_count']} edges")

    corpus_manifest = build_corpora(
        output_dir=args.retrieval_dir,
        kg_dir=args.kg_dir,
        include_hospitalization_slices=args.include_hospitalization_slices,
        include_deep_infectious_slices=args.include_deep_infectious_slices,
    )
    print(
        "Retrieval corpora built: "
        f"standard_rag={corpus_manifest['document_counts']['standard_rag']} docs, "
        f"kg_rag={corpus_manifest['document_counts']['kg_rag']} docs"
    )

    if args.skip_embeddings:
        print("Skipped OpenAI embeddings.")
        return 0

    for approach in ["standard_rag", "kg_rag"]:
        manifest = build_embeddings_for_approach(
            approach=approach,
            input_path=default_input_for_approach(approach),
            output_dir=args.vector_dir,
            model=args.model,
            batch_size=args.batch_size,
            dimensions=args.dimensions,
            limit=args.limit,
            overwrite=args.overwrite_vectors,
            dry_run=args.dry_run_embeddings,
        )
        if args.dry_run_embeddings:
            print(f"Embedding dry run for {approach}: {manifest['document_count']} docs")
        else:
            print(
                f"Embeddings built for {approach}: "
                f"{manifest['document_count']} docs, {manifest['embedding_dimensions']} dims"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
