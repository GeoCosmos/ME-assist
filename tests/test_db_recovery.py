"""The ledger must never take the app down with it."""

import sqlite3
from pathlib import Path

import pytest

import usage


@pytest.fixture(autouse=True)
def reset_resolution():
    usage._active_path = None
    usage._configured_path = None
    usage._initialised.clear()
    yield
    usage._active_path = None
    usage._configured_path = None
    usage._initialised.clear()


def test_zero_byte_database_is_recovered(tmp_path, monkeypatch):
    """Exactly what a half-created usage.db looks like."""
    db = tmp_path / "usage.db"
    db.write_bytes(b"")
    monkeypatch.setattr(usage, "DB_PATH", db)

    usage.record("groq", "llama-3.3-70b-versatile", 100, 10, billable=False)
    assert usage.requests_today("groq") == 1


def test_corrupt_database_is_quarantined_not_fatal(tmp_path, monkeypatch):
    db = tmp_path / "usage.db"
    db.write_bytes(b"this is definitely not a sqlite file" * 50)
    monkeypatch.setattr(usage, "DB_PATH", db)

    usage.record("groq", "x", 100, 10, billable=False)

    assert usage.requests_today("groq") == 1
    assert (tmp_path / "usage.db.broken").exists()


def test_stale_journal_beside_the_database_is_cleared(tmp_path, monkeypatch):
    db = tmp_path / "usage.db"
    db.write_bytes(b"")
    (tmp_path / "usage.db-journal").write_bytes(b"stale")
    monkeypatch.setattr(usage, "DB_PATH", db)

    usage.record("groq", "x", 100, 10, billable=False)
    assert usage.requests_today("groq") == 1


def test_unwritable_folder_falls_back_elsewhere(tmp_path, monkeypatch):
    readonly = tmp_path / "readonly"
    readonly.mkdir()
    readonly.chmod(0o500)
    monkeypatch.setattr(usage, "DB_PATH", readonly / "usage.db")
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))

    try:
        usage.record("groq", "x", 100, 10, billable=False)
        assert usage.requests_today("groq") == 1
        assert usage.active_path() != readonly / "usage.db"
    finally:
        readonly.chmod(0o700)


def test_reads_do_not_raise_when_everything_is_broken(tmp_path, monkeypatch):
    """/usage returned a 500 before this; it must degrade instead."""
    db = tmp_path / "usage.db"
    db.write_bytes(b"")
    monkeypatch.setattr(usage, "DB_PATH", db)

    assert usage.spend_today() == 0
    assert usage.tokens_today("groq") == 0
    assert isinstance(usage.free_summary(), dict)


def test_recording_never_raises(monkeypatch):
    def boom(*args, **kwargs):
        raise sqlite3.OperationalError("unable to open database file")

    monkeypatch.setattr(usage, "_connect", boom)

    # Returns the cost it would have logged, and does not propagate.
    assert usage.record("openai", "gpt-5", 1_000_000, 0) > 0


# --- a broken ledger must never break answering --------------------------


def test_every_ledger_read_degrades_instead_of_raising(monkeypatch):
    """The user hit `unable to open database file` as a 500 and as a test
    failure. Bookkeeping must never be able to do that."""
    def boom(*args, **kwargs):
        raise sqlite3.OperationalError("unable to open database file")

    monkeypatch.setattr(usage, "_connect", boom)

    assert usage.requests_today("groq") == 0
    assert usage.tokens_today("groq") == 0
    assert usage.spend_today() == 0.0
    assert usage.spend_this_month() == 0.0
    assert usage.exhausted_state("groq") is None
    assert usage.conversation_totals("c1")["turns"] == 0
    assert usage.cache_stats("groq")["turns"] == 0
    assert isinstance(usage.free_summary(), dict)
    usage.mark_exhausted("groq", usage.now_pacific(), "x")   # must not raise
    usage.clear_exhausted("groq")                            # must not raise


def test_a_chat_turn_completes_with_a_dead_ledger(monkeypatch):
    """End to end: the answer still arrives when the ledger is unusable."""
    import llm
    from llm.base import TextDelta, Usage as UsageEvent

    def boom(*args, **kwargs):
        raise sqlite3.OperationalError("unable to open database file")

    monkeypatch.setattr(usage, "_connect", boom)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    class Fake:
        def get_response_stream(self, history, domain=None, sections=None):
            yield TextDelta("the answer")
            yield UsageEvent("gemini", "gemini-2.5-flash", 100, 50)

    monkeypatch.setitem(llm._PROVIDERS, "gemini", Fake)

    events = list(llm.stream_answer([{"role": "user", "content": "hi"}], "c1"))
    text = "".join(e.text for e in events if isinstance(e, TextDelta))

    assert text == "the answer"


def test_connections_do_not_leak_file_descriptors(tmp_path, monkeypatch):
    """`with sqlite3.connect(...)` commits but does NOT close.

    Leaked descriptors exhaust the process limit -- 256 by default on macOS --
    and SQLite then reports it as "unable to open database file", miles from
    the actual cause.
    """
    import os

    monkeypatch.setattr(usage, "DB_PATH", tmp_path / "usage.db")

    def open_fds():
        try:
            return len(os.listdir(f"/proc/{os.getpid()}/fd"))
        except OSError:
            import subprocess
            out = subprocess.run(["lsof", "-p", str(os.getpid())],
                                 capture_output=True, text=True).stdout
            return out.count("\n")

    usage.requests_today("groq")          # warm up: create the schema
    before = open_fds()

    for _ in range(100):
        usage.requests_today("groq")
        usage.tokens_today("groq")
        usage.record("groq", "m", 10, 5, billable=False)

    assert open_fds() - before <= 2, "ledger is leaking file descriptors"


def test_a_test_database_does_not_create_wal_files(tmp_path, monkeypatch):
    """WAL triples the files per database; under a per-test database that is
    thousands of files and the descriptor limit is reached."""
    db = tmp_path / "usage.db"
    monkeypatch.setattr(usage, "DB_PATH", db)

    usage.record("groq", "m", 10, 5, billable=False)

    assert db.exists()
    assert not (tmp_path / "usage.db-wal").exists()
    assert not (tmp_path / "usage.db-shm").exists()
