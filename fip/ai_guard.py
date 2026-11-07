"""Server-side protection for the shared Gemini free-tier quota.

Anonymous visitors of a public deployment share one server-side key, so limits
must be enforced on the server — browser/session counters are trivially reset.

* Global caps: requests per minute and per rolling 24 h (all visitors combined).
* Per-client caps: requests per rolling 24 h and a cooldown between requests.
  Clients are identified by a salted hash of their IP address (raw IPs are never
  stored) with the Streamlit session id as fallback.
* Optional access code (``AI_ACCESS_CODE``) with brute-force throttling.
* Response cache: identical question + identical fact pack is answered from the
  cache for 24 h without spending quota.
* Kill switch: ``AI_ENABLED=false`` disables the assistant entirely.

State lives in SQLite under the runtime cache directory, so it survives Streamlit
reruns and is shared by every session served by the process (and by multiple
processes on the same host).
"""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import sqlite3
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from fip.config import cache_dir, get_bool_setting, get_int_setting, get_setting

DAY = 24 * 3600
_LOCK = threading.Lock()


@dataclass(frozen=True)
class Limits:
    enabled: bool
    global_per_day: int
    global_per_minute: int
    client_per_day: int
    cooldown_seconds: int
    cache_ttl: int = DAY
    max_bad_codes_per_hour: int = 5

    @classmethod
    def from_settings(cls) -> "Limits":
        return cls(
            enabled=get_bool_setting("AI_ENABLED", True),
            global_per_day=get_int_setting("AI_GLOBAL_DAILY_LIMIT", 100, minimum=0, maximum=10_000),
            global_per_minute=get_int_setting("AI_GLOBAL_PER_MINUTE", 5, minimum=1, maximum=60),
            client_per_day=get_int_setting("AI_CLIENT_DAILY_LIMIT", 5, minimum=0, maximum=1_000),
            cooldown_seconds=get_int_setting("AI_COOLDOWN_SECONDS", 20, minimum=0, maximum=3_600),
        )


@dataclass
class Decision:
    allowed: bool
    reason: str = ""
    client_remaining: int = 0
    global_remaining: int = 0
    retry_after: int = 0


class AiGuard:
    def __init__(self, db_path: Path | None = None, limits: Limits | None = None, clock=time.time):
        self.db_path = Path(db_path or (cache_dir() / "ai_guard.sqlite3"))
        self.limits = limits or Limits.from_settings()
        self.clock = clock
        self._salt = self._load_salt()
        with self._connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS usage (ts REAL NOT NULL, client TEXT NOT NULL, kind TEXT NOT NULL)")
            db.execute("CREATE INDEX IF NOT EXISTS usage_ts ON usage(ts)")
            db.execute("CREATE TABLE IF NOT EXISTS answers (key TEXT PRIMARY KEY, ts REAL NOT NULL, payload TEXT NOT NULL)")

    # ------------------------------------------------------------ plumbing
    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.db_path, timeout=10, isolation_level=None)
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            yield conn
        finally:
            conn.close()

    def _load_salt(self) -> bytes:
        path = self.db_path.with_suffix(".salt")
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_bytes(secrets.token_bytes(32))
        return path.read_bytes()

    def client_id(self, ip: str | None, session_id: str | None) -> str:
        basis = f"ip:{ip}" if ip else f"session:{session_id or 'anonymous'}"
        return hmac.new(self._salt, basis.encode(), hashlib.sha256).hexdigest()[:24]

    def _count(self, db, since: float, kind: str = "request", client: str | None = None) -> int:
        if client is None:
            row = db.execute("SELECT COUNT(*) FROM usage WHERE ts >= ? AND kind = ?", (since, kind)).fetchone()
        else:
            row = db.execute("SELECT COUNT(*) FROM usage WHERE ts >= ? AND kind = ? AND client = ?",
                             (since, kind, client)).fetchone()
        return int(row[0])

    # ------------------------------------------------------------ access code
    def access_code_required(self) -> bool:
        return bool(get_setting("AI_ACCESS_CODE"))

    def check_access_code(self, client: str, attempt: str) -> tuple[bool, str]:
        expected = get_setting("AI_ACCESS_CODE")
        if not expected:
            return True, ""
        now = self.clock()
        with _LOCK, self._connect() as db:
            if self._count(db, now - 3600, "bad_code", client) >= self.limits.max_bad_codes_per_hour:
                return False, "Too many incorrect access codes. Try again in an hour."
            if hmac.compare_digest(attempt.strip().encode(), expected.encode()):
                return True, ""
            db.execute("INSERT INTO usage VALUES (?, ?, 'bad_code')", (now, client))
        return False, "Incorrect access code."

    # ------------------------------------------------------------ quota
    def status(self, client: str) -> Decision:
        now = self.clock()
        lim = self.limits
        with self._connect() as db:
            global_day = self._count(db, now - DAY)
            client_day = self._count(db, now - DAY, client=client)
            last = db.execute("SELECT MAX(ts) FROM usage WHERE client = ? AND kind = 'request'", (client,)).fetchone()[0]
        return Decision(
            allowed=True,
            client_remaining=max(0, lim.client_per_day - client_day),
            global_remaining=max(0, lim.global_per_day - global_day),
            retry_after=max(0, int((last or 0) + lim.cooldown_seconds - now)) if last else 0,
        )

    def reserve(self, client: str) -> Decision:
        """Atomically check every limit and, if allowed, record one request."""
        lim = self.limits
        if not lim.enabled:
            return Decision(False, "The AI assistant is disabled by the site owner.")
        now = self.clock()
        with _LOCK, self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                db.execute("DELETE FROM usage WHERE ts < ?", (now - 2 * DAY,))
                global_day = self._count(db, now - DAY)
                global_minute = self._count(db, now - 60)
                client_day = self._count(db, now - DAY, client=client)
                last = db.execute("SELECT MAX(ts) FROM usage WHERE client = ? AND kind = 'request'",
                                  (client,)).fetchone()[0]
                decision = Decision(True, client_remaining=max(0, lim.client_per_day - client_day - 1),
                                    global_remaining=max(0, lim.global_per_day - global_day - 1))
                if global_day >= lim.global_per_day:
                    decision = Decision(False, "This site's daily AI budget is used up. It resets on a rolling 24-hour "
                                               "basis; all financial dashboards keep working.")
                elif client_day >= lim.client_per_day:
                    decision = Decision(False, f"You have used your {lim.client_per_day} AI questions for the last "
                                               "24 hours. Cached answers and all dashboards remain available.")
                elif last and now - last < lim.cooldown_seconds:
                    wait = int(lim.cooldown_seconds - (now - last)) + 1
                    decision = Decision(False, f"Please wait {wait} s between AI questions.", retry_after=wait)
                elif global_minute >= lim.global_per_minute:
                    decision = Decision(False, "The assistant is busy (per-minute limit). Try again in a minute.",
                                        retry_after=60)
                if decision.allowed:
                    db.execute("INSERT INTO usage VALUES (?, ?, 'request')", (now, client))
                db.execute("COMMIT")
            except Exception:
                db.execute("ROLLBACK")
                raise
        return decision

    # ------------------------------------------------------------ answer cache
    @staticmethod
    def cache_key(fact_pack: dict, question: str, models: list[str]) -> str:
        normalized = " ".join(question.lower().split())
        blob = json.dumps({"q": normalized, "m": models, "f": fact_pack}, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(blob.encode()).hexdigest()

    def cached_answer(self, key: str) -> dict | None:
        with self._connect() as db:
            row = db.execute("SELECT ts, payload FROM answers WHERE key = ?", (key,)).fetchone()
        if not row or self.clock() - row[0] > self.limits.cache_ttl:
            return None
        return json.loads(row[1])

    def store_answer(self, key: str, answer: dict) -> None:
        with self._connect() as db:
            db.execute("INSERT OR REPLACE INTO answers VALUES (?, ?, ?)", (key, self.clock(), json.dumps(answer)))
            db.execute("DELETE FROM answers WHERE ts < ?", (self.clock() - 7 * DAY,))
