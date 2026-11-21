"""Process one board in a bounded temporary workspace; never access host paths."""
import base64
import json
import subprocess
import sys
import tempfile
from pathlib import Path

LAYERS = {'front': 'F.Cu,F.Silkscreen,Edge.Cuts', 'back': 'B.Cu,B.Silkscreen,Edge.Cuts',
          'outline': 'Edge.Cuts'}


def command(arguments):
    subprocess.run(arguments, check=True, timeout=25, stdin=subprocess.DEVNULL,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def process(job):
    with tempfile.TemporaryDirectory(prefix='pcb-', dir='/tmp') as directory:
        root = Path(directory)
        board = root / 'board.kicad_pcb'
        if job['operation'] == 'generate':
            source = root / 'job.json'
            source.write_text(json.dumps(job), encoding='utf8')
            command([sys.executable, '-m', 'pcb_worker.generate', str(source), str(board)])
        elif job['operation'] == 'review':
            raw = base64.b64decode(job['board'], validate=True)
            if len(raw) > 1_048_576:
                raise ValueError('Board too large')
            board.write_bytes(raw)
        else:
            raise ValueError('Unknown operation')
        report = root / 'drc.json'
        command(['kicad-cli', 'pcb', 'drc', '--format', 'json', '-o', str(report), str(board)])
        components = root / 'components.json'
        command([sys.executable, '-m', 'pcb_worker.inspect_board', str(board), str(components)])
        images = {}
        for layer, selection in LAYERS.items():
            svg, png = root / (layer + '.svg'), root / (layer + '.png')
            command(['kicad-cli', 'pcb', 'export', 'svg', '--mode-single', '--fit-page-to-board',
                     '--exclude-drawing-sheet', '--layers', selection, '-o', str(svg), str(board)])
            command(['rsvg-convert', '--width', '1600', '-o', str(png), str(svg)])
            images[layer] = base64.b64encode(png.read_bytes()).decode('ascii')
        evidence = json.loads(report.read_text())
        summary = json.loads(components.read_text())
        return {'board': board.read_text(), 'layers': images,
                'drc': {'violations': evidence.get('violations', []),
                        'unconnected_items': evidence.get('unconnected_items', [])},
                'components': summary['components'], 'track_items': summary['track_items'], 'warnings': []}
