"""Curated circuit blocks: each does what it says, merges cleanly, and is insertable over MCP."""

import pytest
from pydantic import ValidationError

from backend import parts_cli
from backend.block_library import BLOCKS, BLOCKS_INDEX_PATH, check_expectation, merge_block
from backend.block_models import CircuitBlock
from backend.project_models import DocumentContents, InsertBlock, ProjectFailure, apply_edits
from backend.schematic_engine import simulate_schematic
from backend.schematic_models import SchematicRequest


@pytest.mark.parametrize("block_id", sorted(BLOCKS))
def test_block_meets_its_expectations_and_every_rating(block_id: str) -> None:
    block = BLOCKS[block_id]
    report = simulate_schematic(block.circuit, block_id)
    assert report.ratings and all(check.passed for check in report.ratings)
    for expectation in block.expectations:
        measured, met = check_expectation(expectation, report)
        assert met, f"{expectation.meaning}: measured {measured:.4g}, expected {expectation.value}"


def existing_circuit() -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """A small circuit whose ids clash with most blocks (R1, D1, G1, P1)."""
    circuit = BLOCKS["pi_gpio_led"].circuit.model_dump()
    return circuit["parts"], circuit["wires"]


def test_merge_renames_clashing_ids_offsets_parts_and_keeps_wiring() -> None:
    parts, wires = existing_circuit()
    merged_parts, merged_wires = merge_block(parts, wires, BLOCKS["pi_gpio_led"], column=20, row=12)
    ids = [part["id"] for part in merged_parts]
    assert len(ids) == len(set(ids)) == 8
    assert ids[4:] == ["P2", "R2", "D2", "G2"]
    new_led = next(part for part in merged_parts if part["id"] == "D2")
    assert (new_led["x"], new_led["y"]) == (20 + 16 - 4, 12 + 9 - 6)
    assert {"a": {"part": "P2", "terminal": 0}, "b": {"part": "R2", "terminal": 0}} in merged_wires
    merged = SchematicRequest.model_validate({"parts": merged_parts, "wires": merged_wires,
                                             "timing": {"stop": 0.001, "step": 1e-5}})
    ratings = simulate_schematic(merged, "merged").ratings
    resistors = [part["id"] for part in merged_parts if part["kind"] == "R"]
    assert len([check for check in ratings if check.part not in resistors]) == 10
    assert sorted((check.part, check.rating) for check in ratings if check.part in resistors) == sorted(
        (resistor, rating) for resistor in resistors for rating in ("power_max", "voltage_max"))


def test_merge_refuses_blocks_that_do_not_fit() -> None:
    parts, wires = existing_circuit()
    with pytest.raises(ValueError, match="doesn't fit"):
        merge_block(parts, wires, BLOCKS["pi_relay_driver"], column=30, row=10)
    crowded = [{**parts[0], "id": f"R{index}", "kind": "R", "value": 100, "board_pin": None}
               for index in range(18)]
    with pytest.raises(ValueError, match="would exceed 20 parts"):
        merge_block(crowded, [], BLOCKS["pi_gpio_led"], column=4, row=4)


def test_insert_block_is_one_atomic_edit() -> None:
    contents = DocumentContents.model_validate({"circuit": BLOCKS["lm1117_3v3_supply"].circuit.model_dump()})
    edited = apply_edits(contents, [InsertBlock(operation="insert_block", block="pi_gpio_led", x=26, y=4)])
    assert len(edited.circuit.parts) == len(contents.circuit.parts) + 4
    with pytest.raises(ProjectFailure, match="Unknown circuit block"):
        apply_edits(contents, [InsertBlock(operation="insert_block", block="no_such_block", x=4, y=4)])
    with pytest.raises(ProjectFailure, match="doesn't fit"):
        apply_edits(contents, [InsertBlock(operation="insert_block", block="pi_relay_driver", x=30, y=10)])


def test_block_expectations_must_name_real_terminals() -> None:
    definition = BLOCKS["pi_gpio_led"].model_dump(mode="json")
    definition["expectations"] = [{**definition["expectations"][0], "signal": "V:D9:0"}]
    with pytest.raises(ValidationError, match="missing terminal"):
        CircuitBlock.model_validate(definition)


def test_browser_blocks_index_matches_the_block_files() -> None:
    assert BLOCKS_INDEX_PATH.read_text() == parts_cli.blocks_index_text(), \
        "run: python -m backend.parts_cli index"
