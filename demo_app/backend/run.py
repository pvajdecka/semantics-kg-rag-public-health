#!/usr/bin/env python3
"""Run the SEMANTiCS demo FastAPI server."""

from __future__ import annotations

import sys
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROJECT_PACKAGES = ROOT / ".python_packages"
if PROJECT_PACKAGES.exists():
    sys.path.insert(0, str(PROJECT_PACKAGES))

import uvicorn  # type: ignore  # noqa: E402


if __name__ == "__main__":
    uvicorn.run(
        "demo_app.backend.server:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        reload=False,
        app_dir=str(ROOT),
    )
