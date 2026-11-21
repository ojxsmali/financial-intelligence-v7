"""Vercel Python function entry point: every /api/* request is rewritten here (see vercel.json)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fip.api import app  # noqa: E402,F401  (Vercel serves the ASGI ``app``)
