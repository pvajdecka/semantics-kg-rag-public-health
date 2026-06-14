#!/usr/bin/env python3
"""Reusable OpenAI embedding helper for the SEMANTiCS data artifacts.

The repository keeps this helper under ``openai/test_embedding_small.py``
because the backend work is expected to use OpenAI's small embedding model.
It is intentionally a thin wrapper around the official SDK so the vector
builders can import one stable function.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Iterable, Sequence


DEFAULT_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
DEFAULT_BATCH_SIZE = int(os.getenv("OPENAI_EMBEDDING_BATCH_SIZE", "128"))
ROOT = Path(__file__).resolve().parents[1]
PROJECT_PACKAGES = ROOT / ".python_packages"
if PROJECT_PACKAGES.exists():
    sys.path.insert(0, str(PROJECT_PACKAGES))


def load_env_file(path: Path) -> None:
    """Load simple KEY=VALUE entries from a .env file without overwriting env."""

    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


load_env_file(ROOT / ".env")


def require_openai_sdk() -> Any:
    """Import the OpenAI SDK lazily and provide a useful setup error."""

    try:
        from openai import OpenAI  # type: ignore
    except ImportError as exc:  # pragma: no cover - depends on local env.
        raise RuntimeError(
            "The OpenAI Python SDK is not installed. Install it with "
            "`python3 -m pip install openai` before building vectors."
        ) from exc
    return OpenAI


def make_client(api_key: str | None = None) -> Any:
    """Create an OpenAI client after validating credentials are available."""

    key = api_key or os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY is not set; cannot request OpenAI embeddings.")
    openai_client = require_openai_sdk()
    return openai_client(api_key=key)


def embed_batch_with_retries(
    client: Any,
    texts: Sequence[str],
    *,
    model: str = DEFAULT_MODEL,
    dimensions: int | None = None,
    max_retries: int = 5,
    retry_base_seconds: float = 2.0,
) -> list[list[float]]:
    """Embed one batch of texts with exponential-backoff retries."""

    if not texts:
        return []
    request: dict[str, Any] = {"model": model, "input": list(texts)}
    if dimensions is not None:
        request["dimensions"] = dimensions

    last_error: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            response = client.embeddings.create(**request)
            ordered = sorted(response.data, key=lambda item: item.index)
            return [list(item.embedding) for item in ordered]
        except Exception as exc:  # pragma: no cover - API failure path.
            last_error = exc
            if attempt >= max_retries:
                break
            time.sleep(min(60.0, retry_base_seconds * (2**attempt)))
    raise RuntimeError(f"OpenAI embedding request failed after retries: {last_error}") from last_error


def embed_texts(
    texts: Sequence[str],
    *,
    model: str = DEFAULT_MODEL,
    batch_size: int = DEFAULT_BATCH_SIZE,
    dimensions: int | None = None,
    api_key: str | None = None,
    max_retries: int = 5,
) -> list[list[float]]:
    """Embed all texts and return vectors in input order."""

    client = make_client(api_key=api_key)
    vectors: list[list[float]] = []
    for start in range(0, len(texts), batch_size):
        batch = texts[start : start + batch_size]
        vectors.extend(
            embed_batch_with_retries(
                client,
                batch,
                model=model,
                dimensions=dimensions,
                max_retries=max_retries,
            )
        )
    return vectors


def read_jsonl_texts(path: Path, text_field: str) -> Iterable[tuple[dict[str, Any], str]]:
    """Yield JSONL records and the selected text field."""

    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            record = json.loads(line)
            text = str(record.get(text_field, "")).strip()
            if not text:
                raise ValueError(f"{path}:{line_number} has an empty `{text_field}` field")
            yield record, text


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-test or run OpenAI small embeddings.")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--dimensions", type=int, default=None)
    parser.add_argument("--text", default="SEMANTiCS retrieval embedding smoke test.")
    parser.add_argument("--input-jsonl", type=Path, default=None)
    parser.add_argument("--text-field", default="text")
    parser.add_argument("--output-jsonl", type=Path, default=None)
    args = parser.parse_args()

    if args.input_jsonl:
        if args.output_jsonl is None:
            parser.error("--output-jsonl is required with --input-jsonl")
        records = list(read_jsonl_texts(args.input_jsonl, args.text_field))
        texts = [text for _, text in records]
        vectors = embed_texts(
            texts,
            model=args.model,
            batch_size=args.batch_size,
            dimensions=args.dimensions,
        )
        args.output_jsonl.parent.mkdir(parents=True, exist_ok=True)
        with args.output_jsonl.open("w", encoding="utf-8") as handle:
            for (record, _), vector in zip(records, vectors, strict=True):
                out = dict(record)
                out["embedding"] = vector
                handle.write(json.dumps(out, ensure_ascii=False) + "\n")
        print(f"Wrote {len(vectors)} embeddings to {args.output_jsonl}")
        return 0

    vectors = embed_texts([args.text], model=args.model, batch_size=args.batch_size, dimensions=args.dimensions)
    print(
        json.dumps(
            {
                "model": args.model,
                "dimensions": len(vectors[0]),
                "text": args.text,
                "first_8_values": vectors[0][:8],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
