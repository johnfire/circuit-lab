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
    check_ac(call, graph)
    try:
        call('/api/schematic/simulate', json.dumps({**graph, 'netlist': 'shell whoami'}).encode(), True)
    except urllib.error.HTTPError as error:
        assert error.code == 422
    else:
        raise AssertionError('Analog API accepted executable input')


def check_ac(call: Callable[[str, bytes | None, bool], object], graph: dict[str, object]) -> None:
    """Require finite real small-signal vectors across the network-disabled worker IPC."""
    request = {'circuit': graph, 'sweep': {'source': 'V1', 'amplitude': 2, 'phase': 30,
               'start': 1, 'stop': 1000, 'spacing': 'log', 'points': 20}}
    report = call('/api/schematic/ac', json.dumps(request).encode(), True)
    assert isinstance(report, dict) and report['analysis'] == 'ac'
    assert len(report['frequencies']) == 61
    node = report['pin_nodes']['R2:0']
    voltage = next(trace for trace in report['traces'] if trace['name'] == 'V:' + node)
    assert abs(voltage['real'][0] - .866025403784) < .00001
    assert abs(voltage['imaginary'][0] - .5) < .00001
    assert report['dc_biases'] == {'V1': 5}
    try:
        call('/api/schematic/ac', json.dumps({**request, 'netlist': 'shell whoami'}).encode(), True)
    except urllib.error.HTTPError as error:
        assert error.code == 422
    else:
        raise AssertionError('AC API accepted executable input')
