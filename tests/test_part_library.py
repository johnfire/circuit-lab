"""Parts library: file validation, trust gating, model generation and the CLI."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend import parts_cli
from backend.part_library import INDEX_PATH, LIBRARY, library_summaries, load_library, model_card
from backend.part_library_models import LibraryPart

DATASHEET = "https://example.com/1n4148.pdf"


def part_file(**changes: object) -> dict[str, object]:
    """A complete, valid draft diode file to mutate in each test."""
    definition: dict[str, object] = {
        "id": "testdiode", "name": "TEST1", "kind": "D", "category": "diode",
        "description": "Test diode", "package": "DO-35",
        "datasheet": {"manufacturer": None, "url": None},
        "model": {"parameters": {"IS": 2.52e-9, "N": 1.752, "RS": 0.568}},
        "ratings": {"vr_max": {"value": 100, "unit": "V", "source": "unconfirmed"},
                    "if_max": {"value": 0.2, "unit": "A", "source": "unconfirmed"}},
        "characterization": [{"test": "diode_forward_voltage", "current": 0.01, "max": 1.0,
                              "source": "unconfirmed"}],
        "trust": {"level": "draft"},
    }
    return definition | changes


def verified_file(**trust: object) -> dict[str, object]:
    """A diode that cites datasheet pages everywhere, with the given trust record."""
    definition = part_file(datasheet={"manufacturer": "Test", "url": DATASHEET})
    for rating in definition["ratings"].values():
        rating["source"] = "datasheet p. 2"
    definition["characterization"][0]["source"] = "datasheet p.3"
    definition["trust"] = {"level": "verified"} | trust
    return definition


def test_shipped_library_loads_with_unique_ids_and_draft_or_verified_trust() -> None:
    assert len(LIBRARY) >= 20
    assert {part.trust.level for part in LIBRARY.values()} <= {"draft", "verified"}
    assert [summary["id"] for summary in library_summaries()].count("1n4148") == 1


def test_verified_requires_reviewer_date_datasheet_and_page_citations() -> None:
    with pytest.raises(ValidationError, match="who reviewed"):
        LibraryPart.model_validate(verified_file())
    reviewed = {"reviewed_by": "Chris", "reviewed_on": "2026-10-22"}
    assert LibraryPart.model_validate(verified_file(**reviewed)).trust.level == "verified"
    uncited = verified_file(**reviewed)
    uncited["characterization"][0]["source"] = "unconfirmed"
    with pytest.raises(ValidationError, match="cite a datasheet page"):
        LibraryPart.model_validate(uncited)
    no_link = verified_file(**reviewed) | {"datasheet": {"manufacturer": "Test", "url": None}}
    with pytest.raises(ValidationError, match="link its datasheet"):
        LibraryPart.model_validate(no_link)


@pytest.mark.parametrize("change, message", [
    ({"kind": "NPN"}, "cannot be kind"),
    ({"ratings": {"vr_max": {"value": 100, "unit": "V", "source": "x x"}}}, "Missing ratings"),
    ({"ratings": {"vr_max": {"value": 100, "unit": "A", "source": "x x"},
                  "if_max": {"value": 0.2, "unit": "A", "source": "x x"}}}, "must be in V"),
    ({"characterization": [{"test": "bjt_current_gain", "collector_voltage": 1,
                            "collector_current": 0.01, "min": 100, "source": "x x"}]},
     "does not apply"),
    ({"model": {"parameters": {"IS ; shell": 1.0}}}, "pattern"),
    ({"characterization": [{"test": "diode_forward_voltage", "current": 0.01, "min": 1,
                            "max": 0.5, "source": "x x"}]}, "below max"),
])
def test_inconsistent_part_files_are_rejected(change: dict[str, object], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        LibraryPart.model_validate(part_file(**change))


def test_model_card_is_generated_from_numbers_with_channel_flag() -> None:
    diode = LibraryPart.model_validate(part_file())
    assert model_card(diode) == ".model lib_testdiode D(IS=2.52e-09 N=1.752 RS=0.568)"
    assert model_card(LIBRARY["ao3401a"]).startswith(".model lib_ao3401a VDMOS(pchan ")
    assert "pchan" not in model_card(LIBRARY["irlz44n"])


def write_part(root: Path, folder: str, definition: dict[str, object]) -> None:
    """Place a part file under a temporary library root."""
    path = root / folder / "part.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(definition))


def test_loader_requires_matching_folder_and_unique_ids(tmp_path: Path) -> None:
    write_part(tmp_path, "diode/testdiode", part_file())
    assert set(load_library(tmp_path)) == {"testdiode"}
    write_part(tmp_path, "diode/elsewhere", part_file())
    with pytest.raises(ValueError, match="must live at"):
        load_library(tmp_path)


def test_cli_scaffold_is_a_draft_the_loader_ignores(tmp_path: Path,
                                                     monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(parts_cli, "PARTS_ROOT", tmp_path)
    assert parts_cli.main(["new", "mosfet/testfet", "--kind", "NMOS"]) == 0
    draft = json.loads((tmp_path / "mosfet/testfet/part.draft.json").read_text())
    assert draft["trust"]["level"] == "draft"
    assert set(draft["ratings"]) == {"vds_max", "vgs_max", "id_max", "pd_max"}
    assert load_library(tmp_path) == {}
    assert parts_cli.main(["new", "mosfet/testfet", "--kind", "NMOS"]) == 2
    assert parts_cli.main(["new", "mosfet/badkind", "--kind", "NPN"]) == 2


def test_cli_verify_rejects_unknown_part() -> None:
    assert parts_cli.main(["verify", "no_such_part"]) == 2


def test_browser_parts_index_matches_the_part_files() -> None:
    assert INDEX_PATH.read_text() == parts_cli.index_text(), \
        "run: python -m backend.parts_cli index"


def test_browser_boards_index_matches_the_board_files() -> None:
    from backend.board_library import BOARDS_INDEX_PATH

    assert BOARDS_INDEX_PATH.read_text() == parts_cli.boards_index_text(), \
        "run: python -m backend.parts_cli index"
