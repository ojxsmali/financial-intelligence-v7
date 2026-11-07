"""Secret-leakage and configuration hardening checks."""
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCAN_EXCLUDE = {".venv", ".cache", "__pycache__", ".pytest_cache", "build", "dist", "release", ".git"}
GOOGLE_KEY = re.compile(r"AIza[0-9A-Za-z_\-]{35}")
GENERIC_SECRET = re.compile(r"(?i)(api[_-]?key|secret|token)\s*=\s*['\"][A-Za-z0-9_\-]{24,}['\"]")


def project_files():
    for path in ROOT.rglob("*"):
        if path.is_file() and not (set(path.relative_to(ROOT).parts) & SCAN_EXCLUDE):
            if path.name == "secrets.toml":          # local, gitignored, never packaged (checked below)
                continue
            if path.suffix in {".py", ".toml", ".md", ".txt", ".json", ".yml", ".yaml", ".csv", ".example", ".ps1",
                               ".spec", ".cfg", ".ini", ".html", ".bat"}:
                yield path


def test_no_hardcoded_api_keys_in_repository():
    offenders = []
    for path in project_files():
        text = path.read_text(encoding="utf-8", errors="ignore")
        if GOOGLE_KEY.search(text) or GENERIC_SECRET.search(text):
            offenders.append(str(path.relative_to(ROOT)))
    assert not offenders, f"possible secrets in: {offenders}"


def test_secrets_file_is_gitignored_and_example_is_placeholder():
    ignore = (ROOT / ".gitignore").read_text()
    assert ".streamlit/secrets.toml" in ignore and ".env" in ignore
    example = (ROOT / ".streamlit" / "secrets.toml.example").read_text()
    assert "GEMINI_API_KEY" in example and not GOOGLE_KEY.search(example)


def test_no_api_key_input_anywhere_in_ui():
    for path in list((ROOT / "views").glob("*.py")) + list((ROOT / "fip" / "ui").glob("*.py")) + [ROOT / "app.py"]:
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"text_input\([^)]*(api|gemini)[^)]*key", text, re.IGNORECASE | re.DOTALL), path
        assert "gemini_api_key()" not in text or path.name == "assistant.py", path


def test_key_only_passed_to_generate_in_assistant():
    text = (ROOT / "views" / "assistant.py").read_text(encoding="utf-8")
    uses = [line.strip() for line in text.splitlines() if "gemini_api_key()" in line]
    assert len(uses) == 1 and "generate(" in uses[0]


def test_streamlit_hides_error_details_from_visitors():
    config = (ROOT / ".streamlit" / "config.toml").read_text()
    assert 'showErrorDetails = "none"' in config
    assert "enableXsrfProtection = true" in config


def test_gemini_key_sent_in_header_not_url():
    text = (ROOT / "fip" / "gemini.py").read_text(encoding="utf-8")
    assert "x-goog-api-key" in text and "?key=" not in text


def test_secrets_toml_excluded_from_release_build():
    script = (ROOT / "scripts" / "package_release.py").read_text(encoding="utf-8")
    assert "secrets.toml" in script


@pytest.mark.skipif(not (ROOT / ".git").exists(), reason="not a git checkout")
def test_secrets_not_tracked_by_git():
    tracked = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True).stdout
    assert ".streamlit/secrets.toml" not in tracked.splitlines()
