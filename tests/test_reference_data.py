from reference_data import REFERENCE_DATA


def test_reference_data_includes_common_aerospace_metals():
    assert "6061-T6" in REFERENCE_DATA
    assert "Ti-6Al-4V" in REFERENCE_DATA


def test_reference_data_includes_composite_failure_theories():
    assert "Tsai-Hill" in REFERENCE_DATA
    assert "Tsai-Wu" in REFERENCE_DATA


def test_reference_data_includes_gdt_symbols():
    assert "flatness" in REFERENCE_DATA.lower()
    assert "perpendicularity" in REFERENCE_DATA.lower()


def test_reference_data_includes_verification_caveat():
    assert "verify" in REFERENCE_DATA.lower()
