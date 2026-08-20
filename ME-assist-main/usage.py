"""Token usage ledger, cost math, and free-tier quota tracking.

Everything is persisted to a local SQLite file so counts survive restarts and
stay correct when uvicorn runs with more than one worker.
"""

import contextlib
import functools
import os
import sqlite3
import sys
import tempfile
import threading
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import config

DB_PATH = Path(
    os.environ.get("ME_ASSIST_DB", Path(__file__).parent / "usage.db")
)

def _quota_tz():
    """Pacific time, where the providers' daily quotas roll over.

    Windows ships no system timezone database -- zoneinfo reads the OS copy,
    which only exists on macOS and Linux. The `tzdata` package supplies it and
    is installed on Windows, but if it is somehow missing the app must still
    start: fall back to a fixed -08:00.

    That fallback is correct outside US daylight saving and an hour off during
    it, which shifts the daily reset by an hour. Losing an hour of accuracy on
    a quota counter is vastly better than refusing to launch.
    """
    try:
        return ZoneInfo("America/Los_Angeles")
    except (ZoneInfoNotFoundError, KeyError):
        print(
            "  [no timezone database found; using a fixed -08:00 for quota "
            "resets. Install it with: pip install tzdata]",
            file=sys.stderr,
        )
        return timezone(timedelta(hours=-8), "PST")


# Gemini's free-tier request-per-day counter rolls over at midnight Pacific.
QUOTA_TZ = _quota_tz()

# USD per 1,000,000 tokens: (input, output). Verified August 2026.
PRICES: dict[str, tuple[float, float]] = {
    "gemini-2.5-flash": (0.30, 2.50),
    "gemini-2.5-flash-lite": (0.10, 0.40),
    "gemini-2.5-pro": (1.25, 10.00),
    "claude-sonnet-5": (2.00, 10.00),
    "claude-opus-5": (15.00, 75.00),
    "claude-haiku-4-5-20251001": (1.00, 5.00),
    "gpt-5": (1.25, 10.00),
    "gpt-5-mini": (0.25, 2.00),
    # Groq is free at the developer tier; these are its paid rates, used only
    # if the free allowance is exceeded on a billed account.
    "llama-3.3-70b-versatile": (0.59, 0.79),
    "llama-3.1-8b-instant": (0.05, 0.08),
    "openai/gpt-oss-120b": (0.15, 0.75),
    "qwen3-32b": (0.29, 0.59),
}

# Used when a model string is not in the table, so an unknown model never
# silently reports $0.00 and looks free.
FALLBACK_PRICE = (2.00, 10.00)

# Characters per token, used to size a turn before sending it.
#
# The usual rule of thumb is 4, which is right for prose but too optimistic for
# this prompt: the reference sheet is dense tables of numbers, units and
# punctuation, which tokenise far worse. Measured against real billing, a
# 35,480-character prompt cost ~10,700 tokens -- a ratio of 3.3, meaning the
# rule of thumb under-counts by about 17%.
#
# Erring low is the dangerous direction: it lets the daily budget overrun, lets
# an oversized prompt through the per-minute check, and under-states the cost
# shown on the approval card. So estimate slightly high on purpose.
CHARS_PER_TOKEN = 3.3

# Reentrant: a write already holding the lock can trigger lazy schema creation,
# which takes the lock again.
_write_lock = threading.RLock()
_initialised: set[str] = set()
_warned = False


def _never_fails(default):
    """Ledger access must never break answering a question.

    The ledger is bookkeeping. If the database is unreadable -- a bad file, a
    read-only folder, a locked index -- the honest failure mode is to lose the
    accounting, not to refuse the user an answer.

    Note the safe direction: a read that fails returns "nothing recorded", so a
    free tier looks fully available. That risks overrunning a daily budget, but
    the provider's own 429 is the real backstop, and the alternative is the app
    refusing to work at all.
    """
    def decorate(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            global _warned
            try:
                return fn(*args, **kwargs)
            except (sqlite3.Error, OSError) as exc:
                if not _warned:
                    _warned = True
                    print(
                        f"  [usage ledger unavailable: {exc}]\n"
                        f"  Cost tracking is disabled for this session; "
                        f"answers are unaffected.",
                        file=sys.stderr,
                    )
                return default() if callable(default) else default
        return wrapper
    return decorate

# The file actually in use, which may differ from DB_PATH if that one was
# unusable. _configured_path tracks what DB_PATH was when we resolved, so a
# test (or a settings change) pointing DB_PATH elsewhere is picked up.
_active_path: Path | None = None
_configured_path: Path | None = None


@dataclass(frozen=True)
class CostEstimate:
    input_tokens: int
    output_tokens: int
    cost_usd: float

    def as_dict(self) -> dict:
        return asdict(self)


def _fallback_path() -> Path:
    """Somewhere writable when the project folder is not.

    Usage tracking is bookkeeping. If it cannot be stored where we would like,
    the app must keep answering questions rather than returning 500s.
    """
    override = os.environ.get("XDG_STATE_HOME")
    if override:
        base = Path(override)
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path.home() / ".local" / "state"

    directory = base / "me-assist"
    try:
        directory.mkdir(parents=True, exist_ok=True)
        return directory / "usage.db"
    except OSError:
        return Path(tempfile.gettempdir()) / "me-assist-usage.db"


def _wants_wal(path: Path) -> bool:
    """WAL is for the real, long-lived database only.

    It costs two extra files (-wal, -shm) and two extra file descriptors per
    connection. Under a test run that creates a fresh database per test, that
    multiplies into thousands of files and can exhaust the process descriptor
    limit -- which macOS sets at 256 by default, and which SQLite then reports
    as the thoroughly misleading "unable to open database file".
    """
    text = str(path)
    return not (
        "pytest" in text
        or text.startswith(tempfile.gettempdir())
        or "/tmp/" in text
    )


def _open(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path, check_same_thread=False, timeout=10)
    conn.row_factory = sqlite3.Row
    if _wants_wal(path):
        try:
            # WAL lets concurrent uvicorn workers read while one writes, but it
            # is unsupported on some network/mounted filesystems -- fall back
            # quietly.
            conn.execute("PRAGMA journal_mode=WAL")
        except sqlite3.OperationalError:
            pass
    return conn


@contextlib.contextmanager
def _db():
    """Open the ledger, commit on success, and ALWAYS close.

    `with sqlite3.connect(...) as conn:` commits the transaction but does *not*
    close the connection -- a well-known trap. Relying on refcounting to clean
    up works until it doesn't, and the failure mode is descriptor exhaustion
    far away from the cause.
    """
    conn = _connect()
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def _quarantine(path: Path) -> None:
    """Move an unusable database aside so a fresh one can be created."""
    for suffix in ("", "-journal", "-wal", "-shm"):
        candidate = Path(str(path) + suffix)
        if not candidate.exists():
            continue
        try:
            candidate.rename(str(candidate) + ".broken")
        except OSError:
            try:
                candidate.unlink()
            except OSError:
                pass


def _usable(path: Path) -> bool:
    """Is this file actually a working database?

    Must read the schema, not just evaluate an expression: `SELECT 1` never
    touches the file header, so a corrupt or zero-length database sails through
    it and only explodes later on a real query.
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with contextlib.closing(_open(path)) as conn:
            conn.execute("SELECT count(*) FROM sqlite_master").fetchone()
        return True
    except (sqlite3.Error, OSError):
        return False


def _resolve_path() -> Path:
    """Pick a database file that actually works.

    A zero-length or half-written usage.db, or a stale -journal beside it, makes
    SQLite raise "unable to open database file". Rather than surfacing that as a
    500 on every request, quarantine it and, failing that, move somewhere
    writable.
    """
    global _active_path
    if _active_path is not None and Path(DB_PATH) == _configured_path:
        return _active_path

    path = Path(DB_PATH)
    if not _usable(path):
        _quarantine(path)
        if not _usable(path):
            path = _fallback_path()
            _usable(path)

    _set_active(path)
    return path


def _set_active(path: Path) -> None:
    global _active_path, _configured_path
    _active_path = path
    _configured_path = Path(DB_PATH)


def active_path() -> Path:
    return _resolve_path()


def _connect() -> sqlite3.Connection:
    """Open the ledger, creating the schema on first use.

    Initialisation is lazy rather than at import time so that importing the app
    never touches disk, and so tests can redirect DB_PATH before anything runs.
    """
    path = _resolve_path()
    if str(path) not in _initialised:
        init_db(path)
    return _open(path)


@_never_fails(None)
def init_db(path: Path | None = None) -> None:
    path = Path(path or DB_PATH)
    conn = _open(path)
    with _write_lock, contextlib.closing(conn), conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                quota_day TEXT NOT NULL,
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                conversation_id TEXT,
                input_tokens INTEGER NOT NULL DEFAULT 0,
                output_tokens INTEGER NOT NULL DEFAULT 0,
                cost_usd REAL NOT NULL DEFAULT 0,
                billable INTEGER NOT NULL DEFAULT 1,
                cached_tokens INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        # Existing databases predate the column; adding it is cheap and safe.
        try:
            conn.execute(
                "ALTER TABLE events ADD COLUMN cached_tokens INTEGER NOT NULL DEFAULT 0"
            )
        except sqlite3.OperationalError:
            pass  # already present
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_events_day ON events (quota_day, provider)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_events_convo ON events (conversation_id)"
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS quota_state (
                provider TEXT PRIMARY KEY,
                exhausted_until TEXT,
                reason TEXT
            )
            """
        )
    _initialised.add(str(path))


def now_pacific() -> datetime:
    return datetime.now(QUOTA_TZ)


def quota_day(moment: datetime | None = None) -> str:
    return (moment or now_pacific()).astimezone(QUOTA_TZ).strftime("%Y-%m-%d")


def next_reset(moment: datetime | None = None) -> datetime:
    local = (moment or now_pacific()).astimezone(QUOTA_TZ)
    tomorrow = (local + timedelta(days=1)).date()
    return datetime(tomorrow.year, tomorrow.month, tomorrow.day, tzinfo=QUOTA_TZ)


def price_for(model: str) -> tuple[float, float]:
    if model in PRICES:
        return PRICES[model]
    for known, price in PRICES.items():
        if model.startswith(known):
            return price
    return FALLBACK_PRICE


def cost_of(model: str, input_tokens: int, output_tokens: int) -> float:
    price_in, price_out = price_for(model)
    return (input_tokens * price_in + output_tokens * price_out) / 1_000_000


def record(
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    conversation_id: str | None = None,
    billable: bool = True,
    cached_tokens: int = 0,
) -> float:
    """Append one turn to the ledger. Returns its cost in USD.

    Never raises: losing a bookkeeping row must not destroy an answer the user
    has already waited for and already paid for.
    """
    cost = cost_of(model, input_tokens, output_tokens) if billable else 0.0
    try:
        with _write_lock, _db() as conn:
            conn.execute(
                """
                INSERT INTO events
                    (ts, quota_day, provider, model, conversation_id,
                     input_tokens, output_tokens, cost_usd, billable,
                     cached_tokens)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    now_pacific().isoformat(),
                    quota_day(),
                    provider,
                    model,
                    conversation_id,
                    input_tokens,
                    output_tokens,
                    cost,
                    int(billable),
                    cached_tokens,
                ),
            )
    except sqlite3.Error:
        pass
    return cost


@_never_fails(0)
def requests_today(provider: str) -> int:
    with _db() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM events WHERE quota_day = ? AND provider = ?",
            (quota_day(), provider),
        ).fetchone()
    return row["n"] if row else 0


@_never_fails(0)
def tokens_today(provider: str) -> int:
    """Tokens spent today. On a token-metered free tier this is the real meter."""
    with _db() as conn:
        row = conn.execute(
            """
            SELECT COALESCE(SUM(input_tokens + output_tokens), 0) AS n
            FROM events WHERE quota_day = ? AND provider = ?
            """,
            (quota_day(), provider),
        ).fetchone()
    return row["n"] if row else 0


@_never_fails(lambda: {"input_tokens": 0, "cached_tokens": 0, "hit_rate": 0.0, "turns": 0})
def cache_stats(provider: str) -> dict:
    """How much of today's input was served from the provider's prompt cache.

    Reported rather than assumed: whether cached tokens are exempt from a free
    tier's daily allowance is a claim best checked against the provider's own
    dashboard, and this is the number to check it with.
    """
    with _db() as conn:
        row = conn.execute(
            """
            SELECT COALESCE(SUM(input_tokens), 0) AS tin,
                   COALESCE(SUM(cached_tokens), 0) AS cached,
                   COUNT(*) AS turns
            FROM events WHERE quota_day = ? AND provider = ?
            """,
            (quota_day(), provider),
        ).fetchone()
    total = row["tin"] or 0
    cached = row["cached"] or 0
    return {
        "input_tokens": total,
        "cached_tokens": cached,
        "hit_rate": round(cached / total, 3) if total else 0.0,
        "turns": row["turns"],
    }


def tokens_remaining(provider: str) -> int | None:
    """Free tokens left today, or None if this provider has no daily token cap."""
    if not config.has_free_tier(provider):
        return None
    limit = config.free_tier_tpd(provider)
    if limit <= 0:
        return None
    return max(0, limit - tokens_today(provider))


@_never_fails(lambda: {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0, "turns": 0})
def conversation_totals(conversation_id: str) -> dict:
    with _db() as conn:
        row = conn.execute(
            """
            SELECT COALESCE(SUM(input_tokens), 0) AS tin,
                   COALESCE(SUM(output_tokens), 0) AS tout,
                   COALESCE(SUM(cost_usd), 0) AS cost,
                   COUNT(*) AS turns
            FROM events WHERE conversation_id = ?
            """,
            (conversation_id,),
        ).fetchone()
    return {
        "input_tokens": row["tin"],
        "output_tokens": row["tout"],
        "cost_usd": round(row["cost"], 6),
        "turns": row["turns"],
    }


@_never_fails(0.0)
def spend_since(day: str) -> float:
    with _db() as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(cost_usd), 0) AS cost FROM events WHERE quota_day >= ?",
            (day,),
        ).fetchone()
    return round(row["cost"], 6)


def spend_today() -> float:
    return spend_since(quota_day())


def spend_this_month() -> float:
    return spend_since(now_pacific().strftime("%Y-%m-01"))


@_never_fails(None)
def mark_exhausted(provider: str, until: datetime, reason: str) -> None:
    with _write_lock, _db() as conn:
        conn.execute(
            """
            INSERT INTO quota_state (provider, exhausted_until, reason)
            VALUES (?, ?, ?)
            ON CONFLICT(provider) DO UPDATE SET
                exhausted_until = excluded.exhausted_until,
                reason = excluded.reason
            """,
            (provider, until.isoformat(), reason),
        )


@_never_fails(None)
def clear_exhausted(provider: str) -> None:
    with _write_lock, _db() as conn:
        conn.execute("DELETE FROM quota_state WHERE provider = ?", (provider,))


@_never_fails(None)
def exhausted_state(provider: str) -> dict | None:
    """Returns the live exhaustion record, or None if the provider is usable."""
    with _db() as conn:
        row = conn.execute(
            "SELECT * FROM quota_state WHERE provider = ?", (provider,)
        ).fetchone()
    if not row or not row["exhausted_until"]:
        return None

    until = datetime.fromisoformat(row["exhausted_until"])
    if until <= now_pacific():
        clear_exhausted(provider)
        return None
    return {"provider": provider, "until": until, "reason": row["reason"]}


def free_remaining(provider: str = config.FREE_TIER_PROVIDER) -> int | None:
    """Free requests left today, or None if this provider has no free tier."""
    if not config.has_free_tier(provider):
        return None
    return max(0, config.free_tier_rpd(provider) - requests_today(provider))


def free_tier_available(provider: str = config.FREE_TIER_PROVIDER) -> bool:
    if not config.has_free_tier(provider):
        return False
    if exhausted_state(provider):
        return False
    remaining = free_remaining(provider)
    if remaining is not None and remaining <= 0:
        return False
    tokens = tokens_remaining(provider)
    return tokens is None or tokens > 0


def free_summary() -> dict[str, dict]:
    """Per-provider free-tier position, for the status bar and settings page."""
    return {
        provider: {
            "remaining": free_remaining(provider),
            "limit": config.free_tier_rpd(provider),
            "used": requests_today(provider),
            "tokens_remaining": tokens_remaining(provider),
            "tokens_limit": config.free_tier_tpd(provider),
            "tokens_used": tokens_today(provider),
            "cache": cache_stats(provider),
            "configured": config.is_configured(provider),
        }
        for provider in config.FREE_TIERS
        if config.has_free_tier(provider)
    }


def estimate_next_turn(
    model: str, history: list[dict], domain: str | None = None
) -> CostEstimate:
    """Rough forward estimate for the *next* turn.

    Input is the whole conversation re-sent plus the system instruction; output
    is assumed to be a typical full-rigor answer. Deliberately conservative so
    the number shown at the approval prompt is not an undercount.
    """
    from llm.base import build_full_system_instruction

    system_chars = len(build_full_system_instruction(domain, history))
    history_chars = sum(len(turn.get("content", "")) for turn in history)
    input_tokens = int((system_chars + history_chars) / CHARS_PER_TOKEN)
    output_tokens = 800
    return CostEstimate(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=round(cost_of(model, input_tokens, output_tokens), 4),
    )
