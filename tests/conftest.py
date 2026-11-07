import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "companyfacts"

# Tests never touch the network unless a transport is injected explicitly.
os.environ["FIP_OFFLINE"] = "1"


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("FIP_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("FIP_OFFLINE", "1")
    for key in ("GEMINI_API_KEY", "AI_ACCESS_CODE", "AI_ENABLED", "GEMINI_MODELS", "SEC_CONTACT_EMAIL"):
        monkeypatch.delenv(key, raising=False)
    # A developer's local .streamlit/secrets.toml must not influence tests.
    import fip.config
    monkeypatch.setattr(fip.config, "_streamlit_secret", lambda name: None)
    yield tmp_path


def load_fixture(symbol: str) -> dict:
    return json.loads((FIXTURES / f"{symbol}.json").read_text(encoding="utf-8"))


class FakeResponse:
    def __init__(self, status_code=200, body=None, content=b"", headers=None):
        self.status_code = status_code
        self._body = body
        self.content = content or (json.dumps(body).encode() if body is not None else b"")
        self.headers = headers or {}
        self.ok = 200 <= status_code < 300

    def json(self):
        if self._body is None:
            raise ValueError("no json")
        return self._body


class Recorder:
    """Callable transport that returns queued responses and records calls."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, url, **kwargs):
        self.calls.append({"url": url, **kwargs})
        item = self.responses.pop(0) if len(self.responses) > 1 else self.responses[0]
        if isinstance(item, Exception):
            raise item
        return item
