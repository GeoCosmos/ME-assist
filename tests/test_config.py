import importlib


def test_default_model_when_env_not_set(monkeypatch):
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    import config
    importlib.reload(config)
    assert config.GEMINI_MODEL == "gemini-2.5-flash"


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


def test_default_provider_when_env_not_set(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    import config
    importlib.reload(config)
    assert config.LLM_PROVIDER == "gemini"


def test_provider_reads_from_env(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    import config
    importlib.reload(config)
    assert config.LLM_PROVIDER == "anthropic"


def test_default_anthropic_model_when_env_not_set(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)
    import config
    importlib.reload(config)
    assert config.ANTHROPIC_MODEL == "claude-sonnet-5"


def test_anthropic_model_reads_from_env(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-custom")
    import config
    importlib.reload(config)
    assert config.ANTHROPIC_MODEL == "claude-custom"


def test_anthropic_api_key_reads_from_env(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-456")
    import config
    importlib.reload(config)
    assert config.ANTHROPIC_API_KEY == "test-key-456"


def test_default_openai_model_when_env_not_set(monkeypatch):
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    import config
    importlib.reload(config)
    assert config.OPENAI_MODEL == "gpt-5"


def test_openai_model_reads_from_env(monkeypatch):
    monkeypatch.setenv("OPENAI_MODEL", "gpt-custom")
    import config
    importlib.reload(config)
    assert config.OPENAI_MODEL == "gpt-custom"


def test_openai_api_key_reads_from_env(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-789")
    import config
    importlib.reload(config)
    assert config.OPENAI_API_KEY == "test-key-789"
