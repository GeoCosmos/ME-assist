import config


def test_default_model_when_env_not_set(monkeypatch):
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    assert config.get_model("gemini") == "gemini-2.5-flash"


def test_model_reads_from_env(monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL", "gemini-custom")
    assert config.get_model("gemini") == "gemini-custom"


def test_api_key_reads_from_env(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-123")
    assert config.get_api_key("gemini") == "test-key-123"


def test_default_anthropic_and_openai_models(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    assert config.get_model("anthropic") == "claude-sonnet-5"
    assert config.get_model("openai") == "gpt-5"


def test_is_configured_tracks_key_presence(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert config.is_configured("openai") is False
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    assert config.is_configured("openai") is True


def test_chain_defaults_to_the_largest_free_tier_first(monkeypatch):
    """Gemini's ~20/day would be spent in two conversations, so Groq leads."""
    monkeypatch.delenv("LLM_CHAIN", raising=False)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    assert config.get_chain() == ["groq", "gemini", "openai", "anthropic"]
    assert config.free_tier_rpd("groq") > config.free_tier_rpd("gemini")


def test_free_limits_are_overridable(monkeypatch):
    """Published limits are unreliable, so the user must be able to fix them."""
    monkeypatch.setenv("GROQ_FREE_RPD", "1234")
    monkeypatch.setenv("GROQ_FREE_TPM", "9999")
    assert config.free_tier_rpd("groq") == 1234
    assert config.free_tier_tpm("groq") == 9999


def test_bad_limit_values_fall_back_to_defaults(monkeypatch):
    monkeypatch.setenv("GROQ_FREE_RPD", "not-a-number")
    assert config.free_tier_rpd("groq") == config.FREE_TIERS["groq"]["rpd"]


def test_chain_honours_legacy_llm_provider(monkeypatch):
    monkeypatch.delenv("LLM_CHAIN", raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    assert config.get_chain()[0] == "anthropic"


def test_chain_reads_explicit_order(monkeypatch):
    monkeypatch.setenv("LLM_CHAIN", "openai, gemini")
    assert config.get_chain() == ["openai", "gemini"]


def test_chain_drops_unknown_and_duplicate_providers(monkeypatch):
    monkeypatch.setenv("LLM_CHAIN", "gemini,gemini,nonsense,openai")
    assert config.get_chain() == ["gemini", "openai"]


def test_masked_key_never_exposes_the_middle(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-proj-abcdefghijklmnop")
    masked = config.masked_key("openai")
    assert masked.startswith("sk-pr")
    assert masked.endswith("mnop")
    assert "abcdefghij" not in masked


def test_write_env_upserts_and_preserves_comments(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("# a comment\nGEMINI_API_KEY=old\nOTHER=keep\n")
    monkeypatch.setattr(config, "ENV_PATH", env_file)

    config.write_env({"GEMINI_API_KEY": "new", "OPENAI_API_KEY": "added"})

    text = env_file.read_text()
    assert "# a comment" in text
    assert "OTHER=keep" in text
    assert "GEMINI_API_KEY=new" in text
    assert "OPENAI_API_KEY=added" in text
    assert "old" not in text
    assert config.get_api_key("gemini") == "new"


def test_billing_flag_disables_free_tier(monkeypatch):
    assert config.has_billing_enabled("gemini") is False
    monkeypatch.setenv("GEMINI_BILLING_ENABLED", "true")
    assert config.has_billing_enabled("gemini") is True
