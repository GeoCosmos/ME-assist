import pytest

import config


def _all_tunable_env_vars() -> list[str]:
    """Every environment variable that can change provider behaviour.

    Derived from config rather than hand-listed, so adding a provider or a knob
    cannot silently leak real settings into the suite.
    """
    names = ["LLM_PROVIDER", "LLM_CHAIN", "MAX_FREE_WAIT_SECONDS", "ME_ASSIST_DB"]
    for provider in config.PROVIDERS:
        upper = provider.upper()
        names += [
            config.KEY_ENV_VARS[provider],
            config.MODEL_ENV_VARS[provider],
            f"{upper}_FREE_RPD",
            f"{upper}_FREE_RPM",
            f"{upper}_BILLING_ENABLED",
            f"{upper}_RPM",
        ]
    return names


@pytest.fixture(autouse=True)
def isolated_ledger(tmp_path, monkeypatch):
    """Point the usage ledger at a throwaway database for every test."""
    import usage

    monkeypatch.setattr(usage, "DB_PATH", tmp_path / "usage.db")
    yield


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """Start every test from a known, credential-free configuration.

    The app loads a real .env at import time. Without this, a developer's live
    API keys would make the suite hit the network and behave differently on
    every machine.
    """
    for name in _all_tunable_env_vars():
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    yield


@pytest.fixture(autouse=True)
def clean_pacer():
    """Per-minute pacing is process-global state; do not leak it between tests."""
    import ratelimit

    ratelimit.reset()
    yield
    ratelimit.reset()
