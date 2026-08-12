import pytest

import domains
import reference_data
from llm.base import build_full_system_instruction


def test_every_domain_is_complete():
    for key in domains.DOMAIN_ORDER:
        entry = domains.DOMAINS[key]
        assert entry["label"]
        assert entry["blurb"]
        assert entry["prompt"].strip()
        assert len(entry["starters"]) >= 3


def test_domain_order_covers_every_domain():
    assert set(domains.DOMAIN_ORDER) == set(domains.DOMAINS)


def test_every_referenced_section_exists():
    for key, entry in domains.DOMAINS.items():
        for section in entry["sections"]:
            assert section in reference_data.SECTIONS, f"{key} -> {section}"


def test_section_order_covers_every_section():
    assert set(reference_data.SECTION_ORDER) == set(reference_data.SECTIONS)


def test_full_sheet_contains_all_sections():
    sheet = reference_data.build()
    assert "6061-T6" in sheet
    assert "Tsai-Wu" in sheet
    assert "Miles' equation" in sheet or "Miles" in sheet
    assert "ASTM E595" in sheet


def test_selected_domain_narrows_the_reference_sheet():
    full = reference_data.build()
    gdt = reference_data.build(domains.get_sections("gdt"))

    assert len(gdt) < len(full)
    assert "Datum precedence" in gdt
    # Vibration tables are irrelevant to a tolerancing question.
    assert "Miles" not in gdt


def test_core_is_always_present():
    for key in domains.DOMAIN_ORDER:
        sheet = reference_data.build(domains.get_sections(key))
        assert "Margin of safety" in sheet
        assert "Stefan-Boltzmann" in sheet


def test_system_instruction_adds_the_domain_brief():
    general = build_full_system_instruction()
    composites = build_full_system_instruction("composites")

    assert "DISCIPLINE FOCUS" not in general
    assert "DISCIPLINE FOCUS: COMPOSITE" in composites
    assert "mechanical engineering assistant" in composites.lower()


def test_no_mode_ever_ships_the_complete_sheet():
    """Sectioning exists so a single turn stays inside a small TPM budget."""
    complete = len(reference_data.build())
    assert len(build_full_system_instruction()) < complete
    for key in domains.DOMAIN_ORDER:
        assert len(build_full_system_instruction(key)) < complete


def test_every_mode_fits_a_small_per_minute_token_budget():
    """Groq's free tier allows 6,000 tokens per minute, including the answer.

    Must use the calibrated ratio, not the chars/4 rule of thumb: measured
    against real billing this prompt runs about 17% denser than that, and using
    the optimistic figure hid two disciplines that actually overran the budget.
    """
    import usage

    budget = 6000
    reserve_for_answer = 900

    modes = [None] + list(domains.DOMAIN_ORDER)
    for key in modes:
        tokens = int(len(build_full_system_instruction(key)) / usage.CHARS_PER_TOKEN)
        assert tokens + reserve_for_answer < budget, f"{key} = {tokens} tokens"


def test_unknown_domain_falls_back_to_everything():
    assert domains.get_prompt("nonsense") == ""
    assert domains.get_sections("nonsense") is None
    assert build_full_system_instruction("nonsense") == build_full_system_instruction()


def test_catalog_is_serialisable_for_the_ui():
    catalog = domains.catalog()
    assert [d["id"] for d in catalog] == list(domains.DOMAIN_ORDER)
    assert all({"id", "label", "blurb", "starters"} <= set(d) for d in catalog)
    # The prompt text stays server-side.
    assert all("prompt" not in d for d in catalog)


@pytest.mark.parametrize("domain", domains.DOMAIN_ORDER)
def test_reference_sections_are_not_empty(domain):
    sheet = reference_data.build(domains.get_sections(domain))
    assert len(sheet) > 2000


def test_probe_instruction_is_tiny():
    """A key check must not ship the whole reference sheet."""
    from llm.base import PROBE_DOMAIN

    probe = build_full_system_instruction(PROBE_DOMAIN)
    full = build_full_system_instruction()

    assert len(probe) < 100
    assert len(probe) < len(full) / 100
    assert "6061-T6" not in probe


# --- prompt caching depends on a byte-identical prefix -------------------


def test_prefix_is_stable_across_a_conversation():
    """Providers cache on an exact prefix match.

    If the system prompt changes as the conversation develops, the cache never
    hits -- and on a token-metered free tier a cache hit is worth more than a
    marginally better choice of reference tables.
    """
    from llm.base import build_full_system_instruction as build

    history = [{"role": "user", "content": "What torque for a 1/4-20 into 6061?"}]
    first = build(None, history)

    history += [
        {"role": "model", "content": "Use 65-75 in-lb."},
        {"role": "user", "content": "Now what about thermal cycling in orbit?"},
    ]
    second = build(None, history)

    assert first == second, "system prompt changed mid-conversation; cache would miss"


def test_sections_come_from_the_first_question_not_the_latest():
    from llm.base import anchor_question

    history = [
        {"role": "user", "content": "first question"},
        {"role": "model", "content": "answer"},
        {"role": "user", "content": "second question"},
    ]
    assert anchor_question(history) == "first question"


def test_a_domain_prompt_is_identical_every_turn():
    from llm.base import build_full_system_instruction as build

    a = build("fasteners", [{"role": "user", "content": "torque?"}])
    b = build("fasteners", [{"role": "user", "content": "something else entirely"}])
    assert a == b


def test_different_conversations_can_still_differ():
    """Stability is per conversation, not a single global prompt."""
    from llm.base import build_full_system_instruction as build

    bolts = build(None, [{"role": "user", "content": "bolt torque preload thread"}])
    thermal = build(None, [{"role": "user", "content": "radiator emissivity heat flux"}])
    assert bolts != thermal


def test_prefix_survives_history_trimming(monkeypatch):
    """Trimming must not change the cacheable prefix.

    Sections are anchored on the untrimmed history for exactly this reason: if
    the first question is dropped by the window, re-deriving sections from
    what's left would change the prompt and miss the cache from then on.
    """
    import llm
    from llm.base import TextDelta, Usage as UsageEvent

    monkeypatch.setenv("MAX_HISTORY_TURNS", "4")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    seen = []

    class Fake:
        def get_response_stream(self, history, domain=None, sections=None):
            seen.append(sections)
            yield TextDelta("ok")
            yield UsageEvent("gemini", "gemini-2.5-flash", 10, 5)

    monkeypatch.setitem(llm._PROVIDERS, "gemini", Fake)

    history = [{"role": "user", "content": "bolt torque preload thread question"}]
    list(llm.stream_answer(list(history), "c1"))

    for i in range(6):
        history.append({"role": "model", "content": f"a{i}"})
        history.append({"role": "user", "content": f"follow up {i} about nothing"})
    list(llm.stream_answer(list(history), "c1"))

    assert seen[0] is not None
    assert seen[0] == seen[1], "sections changed after trimming; cache would miss"
