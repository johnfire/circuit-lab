"""PCB review uses bounded requests and never replaces source circuit data."""
from fastapi.testclient import TestClient

from backend.application import app
from backend.block_library import BLOCKS


def test_generated_board_passes_validated_circuit_and_explicit_dimensions(monkeypatch):
    captured = []
    from backend import pcb_review
    monkeypatch.setattr(pcb_review, 'request_board', lambda job: captured.append(job) or {
        'board': '(kicad_pcb)', 'layers': {}, 'drc': {'violations': [], 'unconnected_items': []},
        'footprints': [], 'warnings': []})
    circuit = BLOCKS['lm7805_5v_supply'].circuit.model_dump(mode='json')
    with TestClient(app, base_url="http://localhost") as client:
        response = client.post('/api/pcb/generate', json={'circuit': circuit, 'width_mm': 90, 'height_mm': 45})
        assert response.status_code == 200
        assert response.json()['origin'] == 'generated'
        assert captured[0]['width_mm'] == 90 and captured[0]['height_mm'] == 45
        assert {part['ref'] for part in captured[0]['parts']} == {'J1', 'C1', 'C2', 'U1', 'RL'}
        assert client.post('/api/pcb/generate', json={'circuit': circuit, 'width_mm': 0, 'height_mm': 45}).status_code == 422


def test_import_rejects_invalid_and_oversized_board_before_worker(monkeypatch):
    from backend import pcb_review
    called = []
    monkeypatch.setattr(pcb_review, 'request_board', lambda job: called.append(job))
    with TestClient(app, base_url="http://localhost") as client:
        assert client.post('/api/pcb/review', content=b'not a board').status_code == 422
        assert client.post('/api/pcb/review', content=b'(kicad_pcb ' + b'x' * 1_048_576).status_code == 413
    assert not called


def test_pcb_worker_outage_does_not_break_health(monkeypatch):
    monkeypatch.setenv('CIRCUIT_PCB_SOCKET', '/tmp/circuit-pcb-missing-worker.sock')
    circuit = BLOCKS['lm7805_5v_supply'].circuit.model_dump(mode='json')
    with TestClient(app, base_url='http://localhost') as client:
        response = client.post('/api/pcb/generate', json={'circuit': circuit, 'width_mm': 90, 'height_mm': 45})
        assert response.status_code == 503
        assert client.get('/api/health').status_code == 200


def test_uploaded_board_is_passed_unchanged_to_worker(monkeypatch):
    import base64
    from pathlib import Path

    from backend import pcb_review

    board = Path('tests/fixtures/pcb/partially-routed.kicad_pcb').read_bytes()
    received = []
    monkeypatch.setattr(pcb_review, 'request_board', lambda job: received.append(job) or {
        'board': board.decode(), 'layers': {}, 'drc': {'violations': [], 'unconnected_items': []},
        'components': [], 'warnings': []})
    with TestClient(app, base_url='http://localhost') as client:
        response = client.post('/api/pcb/review', content=board)
    assert response.status_code == 200 and response.json()['origin'] == 'imported'
    assert base64.b64decode(received[0]['board']) == board
    assert response.json()['board'].encode() == board
