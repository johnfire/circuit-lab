import json
import pcbnew as pcb

spec = json.load(open('/work/components.json'))
board = pcb.BOARD()
networks = {}
for identifier, name in spec['nets'].items():
    network = pcb.NETINFO_ITEM(board, '/' + name)
    board.Add(network)
    networks[identifier] = network
for index, part in enumerate(spec['parts']):
    library, name = part['footprint'].split(':')
    footprint = pcb.FootprintLoad('/usr/share/kicad/footprints/' + library + '.pretty', name)
    if footprint is None:
        raise ValueError('Missing footprint ' + part['footprint'])
    footprint.SetReference(part['ref'])
    footprint.SetValue(part['value'])
    footprint.SetPosition(pcb.VECTOR2I(pcb.FromMM(15 + index * 15), pcb.FromMM(25)))
    board.Add(footprint)
    for number, net in part['pads']:
        pad = next((item for item in footprint.Pads() if item.GetNumber() == number), None)
        if pad is None:
            raise ValueError('Missing pad ' + part['ref'] + ':' + number)
        pad.SetNet(networks[net])
for start, end in [((5,5),(95,5)),((95,5),(95,50)),((95,50),(5,50)),((5,50),(5,5))]:
    edge = pcb.PCB_SHAPE()
    edge.SetShape(pcb.SHAPE_T_SEGMENT)
    edge.SetStart(pcb.VECTOR2I(*[pcb.FromMM(value) for value in start]))
    edge.SetEnd(pcb.VECTOR2I(*[pcb.FromMM(value) for value in end]))
    edge.SetLayer(pcb.Edge_Cuts)
    edge.SetWidth(pcb.FromMM(.1))
    board.Add(edge)
pcb.SaveBoard('/work/generated.kicad_pcb',board)
print('footprints',len(board.GetFootprints()),'tracks',len(board.GetTracks()))
