"""One-click desktop launcher for Financial Intelligence Platform V7.

Frozen with PyInstaller into FinancialIntelligenceV7.exe. It:

1. Re-uses an already running instance (single-instance lock + health check) instead
   of starting a duplicate server.
2. Picks a free localhost port (8501–8599) and binds to 127.0.0.1 only.
3. Starts Streamlit in-process and opens the default browser once the server is healthy.
4. Loads optional user configuration (GEMINI_API_KEY, SEC_CONTACT_EMAIL, …) from
   %LOCALAPPDATA%\\FinancialIntelligenceV7\\config.toml into the process environment.
   Nothing secret is embedded in the executable.
5. Shuts down when the console window is closed or Ctrl+C is pressed, removing the lock.
6. On failure prints troubleshooting steps and writes launcher.log.

Developer usage:  python desktop/launcher.py [--port 8517] [--no-browser]
"""
from __future__ import annotations

import argparse
import atexit
import json
import logging
import os
import socket
import sys
import threading
import time
import traceback
import urllib.request
import webbrowser
from pathlib import Path

APP_TITLE = "Financial Intelligence Platform V7"
SETTINGS_KEYS = ("GEMINI_API_KEY", "GEMINI_MODELS", "SEC_CONTACT_EMAIL", "AI_ACCESS_CODE", "AI_ENABLED",
                 "AI_CLIENT_DAILY_LIMIT", "AI_GLOBAL_DAILY_LIMIT", "AI_GLOBAL_PER_MINUTE", "AI_COOLDOWN_SECONDS")


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS"))
    return Path(__file__).resolve().parent.parent


def user_dir() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / ".local" / "share") / "FinancialIntelligenceV7"
    base.mkdir(parents=True, exist_ok=True)
    return base


LOCK_FILE = user_dir() / "server.json"
LOG_FILE = user_dir() / "launcher.log"
CONFIG_FILE = user_dir() / "config.toml"


def log(message: str) -> None:
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')}  {message}"
    print(message, flush=True)
    try:
        with LOG_FILE.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass


def healthy(port: int, timeout: float = 1.5) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/_stcore/health", timeout=timeout) as resp:
            return resp.status == 200
    except OSError:
        return False


def pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes
        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        code = ctypes.c_ulong()
        ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
        ctypes.windll.kernel32.CloseHandle(handle)
        return code.value == 259  # STILL_ACTIVE
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def existing_instance() -> int | None:
    try:
        info = json.loads(LOCK_FILE.read_text(encoding="utf-8"))
        port, pid = int(info["port"]), int(info["pid"])
    except (OSError, ValueError, KeyError):
        return None
    if pid_alive(pid) and healthy(port):
        return port
    LOCK_FILE.unlink(missing_ok=True)
    return None


def free_port(preferred: int | None = None) -> int:
    candidates = ([preferred] if preferred else []) + list(range(8501, 8600))
    for port in candidates:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError("No free local port between 8501 and 8599.")


def load_user_config() -> list[str]:
    """Copy whitelisted settings from config.toml into the environment (server-side only)."""
    if not CONFIG_FILE.exists():
        CONFIG_FILE.write_text(
            "# Financial Intelligence Platform V7 — local settings (this file stays on your PC).\n"
            "# Uncomment and fill in. Never share this file.\n"
            '# SEC_CONTACT_EMAIL = "you@example.com"\n'
            '# GEMINI_API_KEY = "your-free-tier-key-from-aistudio.google.com"\n',
            encoding="utf-8",
        )
        return []
    try:
        import toml
        data = toml.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except Exception as exc:  # a malformed file must not stop the app
        log(f"Ignoring {CONFIG_FILE}: could not parse ({type(exc).__name__}).")
        return []
    loaded = []
    for key in SETTINGS_KEYS:
        if key in data and str(data[key]).strip() and not os.environ.get(key):
            os.environ[key] = str(data[key]).strip()
            loaded.append(key)
    return loaded


def open_when_ready(port: int, open_browser: bool) -> None:
    deadline = time.time() + 120
    while time.time() < deadline:
        if healthy(port, timeout=1):
            url = f"http://localhost:{port}"
            log(f"Ready: {url}")
            if open_browser:
                webbrowser.open(url, new=2)
            return
        time.sleep(0.5)
    log("The server did not become ready within 120 s. See troubleshooting below.")


class _BenignResetFilter(logging.Filter):
    """Drop asyncio's 'connection lost' noise when a browser tab closes its websocket on Windows
    (CPython bpo-39010). Only ConnectionResetError raised in _call_connection_lost is filtered."""

    def filter(self, record: logging.LogRecord) -> bool:
        exc = record.exc_info[1] if record.exc_info else None
        return not (isinstance(exc, ConnectionResetError) and "_call_connection_lost" in record.getMessage())


def quiet_benign_windows_socket_resets() -> None:
    if os.name == "nt":
        logging.getLogger("asyncio").addFilter(_BenignResetFilter())


def troubleshooting(exc: BaseException | None = None) -> None:
    print("\n" + "=" * 70)
    print(f"{APP_TITLE} could not start.")
    if exc is not None:
        print(f"Reason: {type(exc).__name__}: {exc}")
    print(f"""
Troubleshooting
  1. Close other copies of the app and try again.
  2. Make sure ports 8501-8599 on this PC are not all in use.
  3. Antivirus tools sometimes block new executables on first run —
     allow FinancialIntelligenceV7.exe and retry.
  4. Details are logged in: {LOG_FILE}
""")
    print("=" * 70)


def main() -> int:
    parser = argparse.ArgumentParser(description=APP_TITLE)
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    if os.name == "nt":
        os.system(f"title {APP_TITLE}")
    print(f"{APP_TITLE}\n" + "-" * len(APP_TITLE))

    port = existing_instance()
    if port is not None:
        log(f"Already running on http://localhost:{port} — opening it instead of starting a second server.")
        if not args.no_browser:
            webbrowser.open(f"http://localhost:{port}", new=2)
        time.sleep(2)
        return 0

    base = app_dir()
    os.chdir(base)  # Streamlit reads .streamlit/config.toml from the working directory
    loaded = load_user_config()
    if loaded:
        log("Loaded settings from config.toml: " + ", ".join(loaded))  # names only, never values
    else:
        log(f"Optional settings file: {CONFIG_FILE}")
    os.environ.setdefault("FIP_CACHE_DIR", str(user_dir() / "cache"))

    port = free_port(args.port)
    LOCK_FILE.write_text(json.dumps({"pid": os.getpid(), "port": port, "started": time.time()}), encoding="utf-8")
    atexit.register(lambda: LOCK_FILE.unlink(missing_ok=True))
    log(f"Starting on http://localhost:{port} … (first launch can take 20–40 s while files unpack)")
    print("Keep this window open while you use the app. Close it (or press Ctrl+C) to stop the app.\n")

    threading.Thread(target=open_when_ready, args=(port, not args.no_browser), daemon=True).start()
    quiet_benign_windows_socket_resets()

    from streamlit.web import cli as stcli
    sys.argv = [
        "streamlit", "run", str(base / "app.py"),
        "--server.port", str(port),
        "--server.address", "127.0.0.1",
        "--server.headless", "true",
        "--global.developmentMode", "false",
        "--browser.gatherUsageStats", "false",
        "--server.fileWatcherType", "none",
    ]
    try:
        stcli.main()
    except SystemExit as exc:
        return int(exc.code or 0)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as error:  # show help instead of a vanishing window
        log("Fatal: " + "".join(traceback.format_exception_only(type(error), error)).strip())
        with LOG_FILE.open("a", encoding="utf-8") as fh:
            traceback.print_exc(file=fh)
        troubleshooting(error)
        if sys.stdin and sys.stdin.isatty():
            input("Press Enter to close…")
        sys.exit(1)
