# SEMANTiCS Paper

This folder contains the CEUR/SEMANTiCS paper source for the KG-RAG public-health demo.

## Build

From this folder:

```bash
make semantics-paper.pdf
```

The build uses LuaLaTeX and BibTeX through the local `Makefile`.

## Overleaf Package

Create a zip suitable for Overleaf import:

```bash
python3 make_overleaf_zip.py
```

Generated build files, template samples, local Python packages, and distribution archives are ignored by Git.
