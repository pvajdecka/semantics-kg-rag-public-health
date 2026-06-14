#!/usr/bin/env python3
"""Create an Overleaf-ready zip from this LaTeX project."""

from __future__ import annotations

import argparse
import fnmatch
import os
from pathlib import Path
import sys
import zipfile


DEFAULT_OUTPUT = Path("dist") / "semantics-paper-overleaf.zip"

LATEXMKRC = """# Generated for Overleaf import by make_overleaf_zip.py.
@default_files = ('semantics-paper.tex');
$pdf_mode = 4;
$lualatex = 'lualatex -shell-escape %O %S';
$bibtex = 'bibtex %O %B';
"""

BUILD_FILE_PATTERNS = {
    "*.abs",
    "*.aux",
    "*.bbl",
    "*.bcf",
    "*.blg",
    "*.fdb_latexmk",
    "*.fls",
    "*.log",
    "*.nav",
    "*.out",
    "*.run.xml",
    "*.snm",
    "*.synctex.gz",
    "*.toc",
    "*.vrb",
    "*.xmpdata",
    "*-blx.bib",
    "*~",
}

ALWAYS_EXCLUDE_FILE_PATTERNS = {
    "*.zip",
    ".DS_Store",
    "CEUR_SEMANTICS_COMPLIANCE.md",
    "Thumbs.db",
    "build-all.log",
    "make_overleaf_zip.py",
    "sample-*",
    "sample-ceur.bib",
}

ALWAYS_EXCLUDE_DIRS = {
    ".agents",
    ".codex",
    ".git",
    ".pytest_cache",
    ".texmf-var",
    "__pycache__",
    "auto",
    "dist",
    "last year award papers",
    "out",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Package the current LaTeX folder as an Overleaf-ready zip."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent,
        help="project root to package; defaults to the script directory",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"zip path to write; defaults to {DEFAULT_OUTPUT}",
    )
    parser.add_argument(
        "--include-generated-pdfs",
        action="store_true",
        help="include PDFs whose basename matches a .tex file",
    )
    parser.add_argument(
        "--include-build-files",
        action="store_true",
        help="include LaTeX build outputs such as .aux, .log, .bbl, and .xmpdata",
    )
    parser.add_argument(
        "--include-minted-cache",
        action="store_true",
        help="include _minted* cache directories",
    )
    parser.add_argument(
        "--include-backups",
        action="store_true",
        help="include .misnamed-backup",
    )
    parser.add_argument(
        "--include-local-python",
        action="store_true",
        help="include .python-packages; normally not useful on Overleaf",
    )
    parser.add_argument(
        "--no-latexmkrc",
        action="store_true",
        help="do not add a generated latexmkrc file to the zip",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the files that would be included without writing a zip",
    )
    return parser.parse_args()


def matches_any(path: str, patterns: set[str]) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)


def should_skip_dir(relative: Path, args: argparse.Namespace) -> bool:
    parts = relative.parts
    if not parts:
        return False

    name = parts[-1]
    if name in ALWAYS_EXCLUDE_DIRS:
        return True
    if name == ".misnamed-backup" and not args.include_backups:
        return True
    if name == ".python-packages" and not args.include_local_python:
        return True
    if name.startswith("_minted") and not args.include_minted_cache:
        return True
    return False


def should_skip_file(
    relative: Path, output_path: Path, tex_stems: set[str], args: argparse.Namespace
) -> bool:
    rel_posix = relative.as_posix()
    name = relative.name

    if relative == output_path:
        return True
    if matches_any(name, ALWAYS_EXCLUDE_FILE_PATTERNS):
        return True
    if not args.include_build_files and matches_any(name, BUILD_FILE_PATTERNS):
        return True
    if (
        relative.suffix.lower() == ".pdf"
        and relative.stem in tex_stems
        and not args.include_generated_pdfs
    ):
        return True
    if rel_posix == "latexmkrc" or rel_posix == ".latexmkrc":
        return False
    return False


def collect_files(root: Path, output: Path, args: argparse.Namespace) -> list[Path]:
    tex_stems = {path.stem for path in root.glob("*.tex")}
    files: list[Path] = []

    for current, dirs, filenames in os.walk(root):
        current_path = Path(current)
        current_relative = current_path.relative_to(root)

        dirs[:] = [
            directory
            for directory in sorted(dirs)
            if not should_skip_dir(current_relative / directory, args)
        ]

        for filename in sorted(filenames):
            path = current_path / filename
            relative = path.relative_to(root)
            if should_skip_file(relative, output, tex_stems, args):
                continue
            files.append(relative)

    return files


def write_zip(
    root: Path, output: Path, files: list[Path], add_generated_latexmkrc: bool
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for relative in files:
            archive.write(root / relative, relative.as_posix())
        if add_generated_latexmkrc:
            archive.writestr("latexmkrc", LATEXMKRC)


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    if not root.is_dir():
        print(f"error: root is not a directory: {root}", file=sys.stderr)
        return 2

    output = args.output
    if not output.is_absolute():
        output = root / output
    output = output.resolve()

    try:
        output_relative = output.relative_to(root)
    except ValueError:
        output_relative = Path("__outside_project__")

    files = collect_files(root, output_relative, args)
    has_latexmkrc = any(path.as_posix() in {"latexmkrc", ".latexmkrc"} for path in files)
    add_generated_latexmkrc = not args.no_latexmkrc and not has_latexmkrc

    if args.dry_run:
        for path in files:
            print(path.as_posix())
        if add_generated_latexmkrc:
            print("latexmkrc")
        return 0

    write_zip(root, output, files, add_generated_latexmkrc)
    total = len(files) + int(add_generated_latexmkrc)
    print(f"Wrote {output}")
    print(f"Included {total} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
