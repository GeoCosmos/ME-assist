import importlib


def test_default_model_when_env_not_set(monkeypatch):
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    import config
    importlib.reload(config)
    assert config.GEMINI_MODEL == "gemini-2.5-pro"


def test_model_reads_from_env(monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL", "gemini-custom")
    import config
    importlib.reload(config)
    assert config.GEMINI_MODEL == "gemini-custom"


def test_api_key_reads_from_env(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-123")
    import config
    importlib.reload(config)
    assert config.GEMINI_API_KEY == "test-key-123"
