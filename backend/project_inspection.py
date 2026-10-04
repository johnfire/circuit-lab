"""Construction versus solver readiness and compact, trustworthy snapshot differences."""

from pydantic import ValidationError

from backend.project_models import DocumentContents
from backend.schematic_models import SchematicRequest
from backend.schematic_topology import assign_nodes


def inspect_contents(contents: DocumentContents) -> dict[str, object]:
    """Unfinished circuits remain editable but cannot be described as simulation-ready."""
    try:
        circuit = SchematicRequest.model_validate(contents.circuit.model_dump())
        nodes = assign_nodes(circuit)
        return {"construction_valid": True, "simulation_ready": True, "pin_nodes": nodes,
                "diagnostics": [], "current_reference": "terminal 0 -> 1", "voltage_reference": "V0 - V1"}
    except (ValidationError, ValueError) as failure:
        diagnostics = ([error["msg"] for error in failure.errors(include_input=False)]
                       if isinstance(failure, ValidationError) else [str(failure)])
        return {"construction_valid": True, "simulation_ready": False,
                "diagnostics": diagnostics[:5], "pin_nodes": {},
                "notice": "Construction validity is not proof of hardware safety"}


def compare_contents(before: DocumentContents, after: DocumentContents) -> dict[str, object]:
    """Report changed component IDs and separate electrical, timing and layout changes."""
    first_parts = {part.id: part.model_dump() for part in before.circuit.parts}
    second_parts = {part.id: part.model_dump() for part in after.circuit.parts}
    identifiers = first_parts.keys() | second_parts.keys()
    changed = [identifier for identifier in sorted(identifiers)
               if first_parts.get(identifier) != second_parts.get(identifier)]
    return {"changed_parts": changed, "wires_changed": before.circuit.wires != after.circuit.wires,
            "timing_changed": before.circuit.timing != after.circuit.timing,
            "sweep_changed": before.sweep != after.sweep,
            "before_parts": len(first_parts), "after_parts": len(second_parts)}
