"""Build release/FinancialIntelligencePlatform_V7_source.zip.

Excludes local secrets (.streamlit/secrets.toml, .env), virtual environments, caches
and build outputs, then re-scans the archive for anything that looks like a key.
"""
from __future__ import annotations

import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "release"
EXCLUDED_DIRS = {".venv", "venv", ".cache", "__pycache__", ".pytest_cache", "build", "dist", "release", ".git",
                 ".idea", ".vscode"}
EXCLUDED_FILES = {"secrets.toml", ".env"}
EXCLUDED_SUFFIXES = {".pyc", ".sqlite3", ".salt", ".tmp"}
KEY_PATTERN = re.compile(rb"AIza[0-9A-Za-z_\-]{35}")


def included(path: Path) -> bool:
    rel = path.relative_to(ROOT)
    if set(rel.parts) & EXCLUDED_DIRS:
        return False
    return path.name not in EXCLUDED_FILES and path.suffix not in EXCLUDED_SUFFIXES


def main() -> int:
    OUT_DIR.mkdir(exist_ok=True)
    target = OUT_DIR / "FinancialIntelligencePlatform_V7_source.zip"
    files = sorted(p for p in ROOT.rglob("*") if p.is_file() and included(p))
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in files:
            zf.write(path, Path("FinancialIntelligencePlatform_V7") / path.relative_to(ROOT))
    with zipfile.ZipFile(target) as zf:
        names = zf.namelist()
        leaks = [n for n in names if n.endswith(("secrets.toml", ".env"))]
        leaks += [n for n in names if KEY_PATTERN.search(zf.read(n))]
    if leaks:
        target.unlink()
        print("ABORTED — secret-like content found in:", leaks, file=sys.stderr)
        return 1
    print(f"Wrote {target} ({target.stat().st_size / 1e6:.1f} MB, {len(names)} files, secret scan clean)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
