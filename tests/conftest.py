"""Shared, genuine analog fixtures for solver and HTTP integration tests."""

import pytest

from backend.schematic_models import SchematicRequest


@pytest.fixture
def analog_request() -> SchematicRequest:
    """A 5 V pulse charging a 10 µF capacitor through 1 kΩ."""
    return SchematicRequest.model_validate({
        "parts": [
            {"id": "V1", "kind": "PULSE", "value": 5, "x": 6, "y": 8,
             "rotation": 90, "pulse": {"period": .1, "width": .05, "delay": .001}},
            {"id": "R1", "kind": "R", "value": 1000, "x": 16, "y": 6},
            {"id": "C1", "kind": "C", "value": 1e-5, "x": 26, "y": 8, "rotation": 90},
            {"id": "G1", "kind": "GND", "value": 0, "x": 16, "y": 16},
        ],
        "wires": [
            {"a": {"part": "V1", "terminal": 0}, "b": {"part": "R1", "terminal": 0}},
            {"a": {"part": "R1", "terminal": 1}, "b": {"part": "C1", "terminal": 0}},
            {"a": {"part": "C1", "terminal": 1}, "b": {"part": "G1", "terminal": 0}},
            {"a": {"part": "G1", "terminal": 0}, "b": {"part": "V1", "terminal": 1}},
        ], "timing": {"stop": .03, "step": .0001},
    })
