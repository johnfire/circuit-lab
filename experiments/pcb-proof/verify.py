"""Verify real KiCad round-trip pad identities and unrouted DRC evidence."""
import json
from pathlib import Path

import pcbnew

folder = Path('/work')
expected = json.loads((folder / 'components.json').read_text())
board = pcbnew.LoadBoard(str(folder / 'generated.kicad_pcb'))
actual = {part.GetReference(): {pad.GetNumber(): pad.GetNetname() for pad in part.Pads()}
          for part in board.GetFootprints()}
assert len(actual) == len(expected['parts'])
for part in expected['parts']:
    assert {number: '/' + expected['nets'][net] for number, net in part['pads']} == actual[part['ref']]
assert len(board.GetTracks()) == 0
report = json.loads((folder / 'drc.json').read_text())
assert report['kicad_version'] == '9.0.2'
assert len(report['unconnected_items']) == 8
print('Round-trip pad identities and eight unrouted connections verified')
