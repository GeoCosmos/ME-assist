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
