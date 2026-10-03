"""Real hosted analog jobs and injection rejection across the private IPC socket."""

import json
import urllib.error
from collections.abc import Callable


def check_analog(call: Callable[[str, bytes | None, bool], object]) -> None:
    """Require a real 2.5 V divider and reject submitted executable fields."""
    graph = {
        "parts": [{"id": "V1", "kind": "V", "value": 5, "x": 6, "y": 8},
                  {"id": "R1", "kind": "R", "value": 1000, "x": 16, "y": 6},
                  {"id": "R2", "kind": "R", "value": 1000, "x": 26, "y": 8},
                  {"id": "G1", "kind": "GND", "value": 0, "x": 16, "y": 16}],
        "wires": [{"a": {"part": a, "terminal": ta}, "b": {"part": b, "terminal": tb}}
                  for a, ta, b, tb in [("V1", 0, "R1", 0), ("R1", 1, "R2", 0),
                                       ("R2", 1, "G1", 0), ("G1", 0, "V1", 1)]],
        "timing": {"stop": .01, "step": .0001},
    }
    report = call('/api/schematic/simulate', json.dumps(graph).encode(), True)
    assert isinstance(report, dict) and report['status'] == 'completed'
    assert len(report['times']) == 101
    node = report['pin_nodes']['R2:0']
    voltage = next(trace for trace in report['traces'] if trace['name'] == 'V:' + node)
    assert abs(voltage['values'][-1] - 2.5) < .001
    try:
        call('/api/schematic/simulate', json.dumps({**graph, 'netlist': 'shell whoami'}).encode(), True)
    except urllib.error.HTTPError as error:
        assert error.code == 422
    else:
        raise AssertionError('Analog API accepted executable input')
