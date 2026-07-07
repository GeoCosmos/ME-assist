from system_prompt import SYSTEM_PROMPT


def test_forbids_register_simplification():
    assert "simplif" in SYSTEM_PROMPT.lower()


def test_requires_shown_work():
    assert "show" in SYSTEM_PROMPT.lower()


def test_names_full_subject_breadth():
    lowered = SYSTEM_PROMPT.lower()
    for topic in [
        "statics", "dynamics", "mechanics of materials", "thermodynamics",
        "heat transfer", "composite", "vibrations", "materials science",
        "gd&t", "fasteners", "manufacturing",
    ]:
        assert topic in lowered, f"missing topic: {topic}"


def test_treats_masters_level_as_floor_not_ceiling():
    lowered = SYSTEM_PROMPT.lower()
    assert "floor" in lowered
    assert "master" in lowered


def test_is_satellite_aware_not_satellite_only():
    lowered = SYSTEM_PROMPT.lower()
    assert "satellite" in lowered or "spacecraft" in lowered
    assert "not every question" in lowered or "equally in scope" in lowered


def test_includes_verify_flag_convention_and_safety_guardrail():
    assert "VERIFY:" in SYSTEM_PROMPT
    assert "certified" in SYSTEM_PROMPT.lower()


def test_instructs_preferring_reference_data():
    assert "reference" in SYSTEM_PROMPT.lower()
