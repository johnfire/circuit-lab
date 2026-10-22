"""Every shipped part meets its stated specs on real ngspice, and bad specs fail."""

import pytest

from backend.part_characterization import characterize
from backend.part_library import LIBRARY
from backend.part_library_models import LibraryPart


@pytest.mark.parametrize("part_id", sorted(LIBRARY))
def test_shipped_part_meets_its_characterization(part_id: str) -> None:
    results = characterize(LIBRARY[part_id])
    failures = [result for result in results if not result.passed]
    assert results and not failures, failures


def with_bounds(part: LibraryPart, **bounds: float | None) -> LibraryPart:
    """The same part with its first test's bounds replaced."""
    test = part.characterization[0].model_copy(update=bounds)
    return part.model_copy(update={"characterization": [test]})


@pytest.mark.parametrize("part_id, bounds", [
    ("1n4148", {"max": 0.5}),
    ("1n4733a", {"min": 5.5, "max": 6.0}),
    ("2n7000", {"min": 2.5, "max": 3.0}),
    ("2n3904", {"min": 400, "max": 500}),
])
def test_out_of_spec_model_fails_with_its_real_measurement(part_id: str,
                                                           bounds: dict[str, float]) -> None:
    [result] = characterize(with_bounds(LIBRARY[part_id], **bounds))
    assert not result.passed
    assert result.measured is not None
    assert result.detail == "outside stated bounds"


def test_measurements_match_device_physics() -> None:
    [forward] = characterize(with_bounds(LIBRARY["1n4148"], max=1.0))
    assert forward.measured == pytest.approx(0.69, abs=0.05)
    zener = characterize(LIBRARY["1n4742a"])[0]
    assert zener.measured == pytest.approx(12.0, abs=0.1)
    p_channel = characterize(LIBRARY["ao3401a"])
    assert all(result.measured and result.measured > 0 for result in p_channel)


def test_unsolvable_model_reports_failure_instead_of_a_number() -> None:
    part = LIBRARY["1n4148"]
    broken = part.model_copy(update={"model": part.model.model_copy(
        update={"parameters": {"NOTAPARAM": 1.0}})})
    [result] = characterize(broken)
    assert not result.passed and result.measured is None
    assert "ngspice" in result.detail
