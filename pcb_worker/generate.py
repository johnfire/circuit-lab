"""Create a preliminary KiCad board; preserve every expected pad-to-net mapping."""
import json
import sys

import pcbnew as pcb


def generate(source, destination):
    job = json.load(open(source, encoding='utf8'))
    board = pcb.BOARD()
    networks = {}
    for identifier, name in job['nets'].items():
        network = pcb.NETINFO_ITEM(board, '/' + name)
        board.Add(network)
        networks[identifier] = network
    width, height = job['width_mm'], job['height_mm']
    count = len(job['parts'])
    for index, part in enumerate(job['parts']):
        library, name = part['footprint'].split(':')
        if not all(all(character.isalnum() or character in '_-.' for character in text)
                   and '..' not in text for text in (library, name)):
            raise ValueError('Invalid footprint name')
        footprint = pcb.FootprintLoad('/usr/share/kicad/footprints/' + library + '.pretty', name)
        if footprint is None:
            raise ValueError('Footprint unavailable')
        footprint.SetReference(part['ref'])
        footprint.SetValue(part['value'])
        footprint.SetPosition(pcb.VECTOR2I(pcb.FromMM(width * (index + 1) / (count + 1)), pcb.FromMM(height / 2)))
        board.Add(footprint)
        for number, net in part['pads']:
            pad = next((item for item in footprint.Pads() if item.GetNumber() == number), None)
            if pad is None:
                raise ValueError('Footprint pad unavailable')
            pad.SetNet(networks[net])
    points = [((0, 0), (width, 0)), ((width, 0), (width, height)),
              ((width, height), (0, height)), ((0, height), (0, 0))]
    for start, end in points:
        edge = pcb.PCB_SHAPE()
        edge.SetShape(pcb.SHAPE_T_SEGMENT)
        edge.SetStart(pcb.VECTOR2I(*[pcb.FromMM(value) for value in start]))
        edge.SetEnd(pcb.VECTOR2I(*[pcb.FromMM(value) for value in end]))
        edge.SetLayer(pcb.Edge_Cuts)
        edge.SetWidth(pcb.FromMM(.1))
        board.Add(edge)
    pcb.SaveBoard(destination, board)


if __name__ == '__main__':
    generate(sys.argv[1], sys.argv[2])
