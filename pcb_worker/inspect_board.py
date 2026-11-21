"""Extract bounded component references using KiCad's own board parser."""
import json
import sys

import pcbnew

board = pcbnew.LoadBoard(sys.argv[1])
footprints = sorted(({'reference': item.GetReference(), 'value': item.GetValue(),
                     'x_mm': pcbnew.ToMM(item.GetPosition().x),
                     'y_mm': pcbnew.ToMM(item.GetPosition().y)}
                     for item in board.GetFootprints()), key=lambda part: part['reference'])
if len(footprints) > 5000:
    raise ValueError('Too many footprints')
with open(sys.argv[2], 'w', encoding='utf8') as output:
    json.dump({'components': footprints, 'track_items': len(board.GetTracks())}, output)
