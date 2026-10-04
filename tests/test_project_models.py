"""Pure collaboration contracts must preserve complete graph snapshots."""

import pytest
from pydantic import ValidationError

from backend.project_models import (
    DocumentContents,
    EditDocument,
    EditorCircuit,
    NewGrant,
    Principal,
    ProjectFailure,
    apply_edits,
    contents_hash,
)
from backend.schematic_models import SchematicRequest


def test_incomplete_editor_graph_is_saveable(analog_request: SchematicRequest) -> None:
    graph = analog_request.model_dump()
    graph["wires"] = []
    assert EditorCircuit.model_validate(graph).wires == []
    graph["parts"] = []
    assert EditorCircuit.model_validate(graph).parts == []


@pytest.mark.parametrize("kind", ["dangling", "self", "duplicate", "ground_pin", "duplicate_id"])
def test_editor_graph_rejects_invalid_connections(analog_request: SchematicRequest, kind: str) -> None:
    graph = analog_request.model_dump()
    if kind == "dangling":
        graph["wires"][0]["a"]["part"] = "missing"
    elif kind == "self":
        graph["wires"][0]["b"] = graph["wires"][0]["a"]
    elif kind == "duplicate":
        graph["wires"].append(graph["wires"][0])
    elif kind == "ground_pin":
        graph["wires"][2]["b"]["terminal"] = 1
    else:
        graph["parts"].append(graph["parts"][0])
    with pytest.raises(ValidationError):
        EditorCircuit.model_validate(graph)


def test_edit_batch_removes_related_wires_without_mutating_input(analog_request: SchematicRequest) -> None:
    original = DocumentContents(circuit=EditorCircuit.model_validate(analog_request.model_dump()))
    command = EditDocument.model_validate({"expected_revision": "00000000-0000-0000-0000-000000000001",
        "idempotency_key": "00000000-0000-0000-0000-000000000002", "reason": "Remove capacitor",
        "edits": [{"operation": "remove_part", "part": "C1"}]})
    changed = apply_edits(original, command.edits)
    assert len(changed.circuit.parts) == 3
    assert len(changed.circuit.wires) == 2
    assert len(original.circuit.parts) == 4
    assert len(original.circuit.wires) == 4
    assert contents_hash(original) != contents_hash(changed)


def test_connection_grants_need_unique_read_permission() -> None:
    for scopes in (["edit"], ["read", "read"]):
        with pytest.raises(ValidationError):
            NewGrant.model_validate({"client": "my-ai", "scopes": scopes, "lifetime_minutes": 30})


def test_principal_requires_explicit_permissions() -> None:
    principal = Principal(owner="verified-owner", actor="ai-agent:verified-client", correlation_id="test")
    assert principal.scopes == frozenset()


def test_atomic_edit_batch_updates_parts_connections_timing_and_sweep(
    analog_request: SchematicRequest,
) -> None:
    original = DocumentContents(circuit=EditorCircuit.model_validate(analog_request.model_dump()))
    resistor = analog_request.parts[1].model_dump()
    resistor.update(value=2200, x=20, rotation=90)
    command = EditDocument.model_validate({
        "expected_revision": "00000000-0000-0000-0000-000000000001",
        "idempotency_key": "00000000-0000-0000-0000-000000000002", "reason": "Retune filter",
        "edits": [
            {"operation": "put_part", "part": resistor},
            {"operation": "disconnect", "a": {"part": "R1", "terminal": 0},
             "b": {"part": "V1", "terminal": 0}},
            {"operation": "connect", "a": {"part": "V1", "terminal": 0},
             "b": {"part": "R1", "terminal": 0}},
            {"operation": "set_timing", "timing": {"stop": .08, "step": .0001}},
            {"operation": "set_sweep", "sweep": {"source": "V1", "amplitude": 1,
             "phase": 0, "start": 1, "stop": 1000, "spacing": "log", "points": 20}},
        ]})
    changed = apply_edits(original, command.edits)
    selected = next(part for part in changed.circuit.parts if part.id == "R1")
    assert (selected.value, selected.x, selected.rotation) == (2200, 20, 90)
    assert len(changed.circuit.parts) == len(original.circuit.parts)
    assert len(changed.circuit.wires) == len(original.circuit.wires)
    assert changed.circuit.timing.stop == .08
    assert changed.sweep is not None and changed.sweep.source == "V1"
    assert original.circuit.parts[1].value == 1000
    assert original.sweep is None


def test_unknown_part_removal_leaves_original_unchanged(analog_request: SchematicRequest) -> None:
    original = DocumentContents(circuit=EditorCircuit.model_validate(analog_request.model_dump()))
    snapshot_hash = contents_hash(original)
    command = EditDocument.model_validate({
        "expected_revision": "00000000-0000-0000-0000-000000000001",
        "idempotency_key": "00000000-0000-0000-0000-000000000002", "reason": "Invalid removal",
        "edits": [{"operation": "remove_part", "part": "missing"}]})
    with pytest.raises(ProjectFailure, match="Unknown part"):
        apply_edits(original, command.edits)
    assert contents_hash(original) == snapshot_hash


def test_unknown_code_and_shell_operations_are_rejected() -> None:
    with pytest.raises(ValidationError):
        EditDocument.model_validate({"expected_revision": "00000000-0000-0000-0000-000000000001",
            "idempotency_key": "00000000-0000-0000-0000-000000000002", "reason": "bad",
            "edits": [{"operation": "shell", "command": "touch /tmp/forbidden"}]})
