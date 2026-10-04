"""Real sine/AC physics and fail-closed analysis boundaries."""

import json
import math
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier, BoundedSemaphore, Event
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.application import app
from backend.schematic_ac_engine import compile_ac, read_complex_frames, simulate_ac
from backend.schematic_ac_gateway import launch_ac
from backend.schematic_ac_models import ACRequest, ACResponse, Sweep
from backend.schematic_engine import simulate_schematic
from backend.schematic_models import Part, SchematicRequest
from backend.simulation_engine import SimulationFailure
from backend.worker_gateway import launch_schematic


@pytest.fixture
def ac_request(analog_request: SchematicRequest) -> ACRequest:
    """Use the real RC graph, with explicit independent AC excitation."""
    return ACRequest(circuit=analog_request, sweep=Sweep(source="V1", amplitude=1.0, phase=0.0,
                     start=1.0, stop=1000.0, spacing="log", points=50))


def test_real_ac_rc_gain_phase_current_and_cutoff(ac_request: ACRequest) -> None:
    cutoff = 1 / (2 * math.pi * .01)
    sweep = ac_request.sweep.model_copy(update={"start": cutoff, "stop": cutoff * 10})
    report = launch_ac(ac_request.model_copy(update={"sweep": sweep}), "ac-physics")
    traces = {trace.name: complex(trace.real[0], trace.imaginary[0]) for trace in report.traces}
    output = traces[f"V:{report.pin_nodes['C1:0']}"]
    assert abs(output) == pytest.approx(1 / math.sqrt(2), rel=1e-6)
    assert math.degrees(math.atan2(output.imag, output.real)) == pytest.approx(-45, abs=1e-6)
    assert traces["I:R1"] == pytest.approx(traces["I:C1"], abs=1e-12)
    assert traces["I:V1"] == pytest.approx(-traces["I:R1"], abs=1e-12)
    assert len(report.frequencies) == 51
    assert report.analysis == "ac"


@pytest.mark.parametrize("spacing,stop", [("linear", 137.0), ("log", 137.0)])
def test_actual_sweep_axis_and_amplitude_phase_normalization(ac_request: ACRequest, spacing: str, stop: float) -> None:
    sweep = Sweep(source="V1", amplitude=2.0, phase=37.0, start=1.0, stop=stop,
                  spacing=spacing, points=20)  # type: ignore[arg-type]
    report = launch_ac(ac_request.model_copy(update={"sweep": sweep}), "normalization")
    node = report.pin_nodes["V1:0"]
    source = next(trace for trace in report.traces if trace.name == f"V:{node}")
    assert abs(complex(source.real[0], source.imaginary[0])) == pytest.approx(2)
    assert math.degrees(math.atan2(source.imaginary[0], source.real[0])) == pytest.approx(37)
    assert report.frequencies == pytest.approx(sweep.frequencies())


def test_rl_phase_and_non_excited_sources_have_zero_ac(ac_request: ACRequest) -> None:
    circuit = ac_request.circuit.model_dump()
    circuit["parts"][2].update(kind="L", value=10.0)
    submitted = ACRequest.model_validate({"circuit": circuit, "sweep": ac_request.sweep.model_dump()})
    report = launch_ac(submitted, "rl")
    current = next(trace for trace in report.traces if trace.name == "I:R1")
    assert current.real[50] > 0 and current.imaginary[50] < 0
    circuit["parts"][2].update(kind="R", value=1000.0)
    circuit["parts"][1].update(kind="V", value=3.0)
    submitted = ACRequest.model_validate({"circuit": circuit, "sweep": ac_request.sweep.model_dump()})
    netlist, _, _ = compile_ac(submitted)
    assert "DC 3 AC 0 0" in netlist
    assert simulate_ac(submitted, "biases").dc_biases == {"V1": 0, "R1": 3}


def test_actual_sine_voltage_current_reversal_and_dc_offset(analog_request: SchematicRequest) -> None:
    circuit = analog_request.model_dump()
    circuit["parts"][0].update(kind="SIN", pulse=None, sine={"offset": 1.0, "frequency": 10.0, "phase": 0.0})
    circuit["parts"][2].update(kind="R", value=1000.0)
    circuit["timing"] = {"stop": .4, "step": .001}
    report = simulate_schematic(SchematicRequest.model_validate(circuit), "sine-physics")
    traces = {trace.name: trace.values for trace in report.traces}
    for time in [.025, .075, .125]:
        index = min(range(len(report.times)), key=lambda index: abs(report.times[index] - time))
        expected = 1 + 5 * math.sin(2 * math.pi * 10 * report.times[index])
        assert traces[f"V:{report.pin_nodes['V1:0']}"][index] == pytest.approx(expected, abs=.01)
        assert traces["I:R1"][index] == pytest.approx(expected / 2000, abs=1e-5)
    assert min(traces["I:R1"]) < 0 < max(traces["I:R1"])


@pytest.mark.parametrize("change", ["amplitude", "frequency", "phase", "offset", "injection"])
def test_sine_source_is_strict_numeric_and_bounded(change: str) -> None:
    part = {"id": "V1", "kind": "SIN", "value": 5, "x": 4, "y": 4,
            "sine": {"offset": 0, "frequency": 10, "phase": 0}}
    if change == "amplitude":
        part["value"] = -1
    elif change == "injection":
        part["sine"]["frequency"] = "10; shell whoami"  # type: ignore[index]
    else:
        part["sine"][change] = {"frequency": 1e8, "phase": 400, "offset": 100}[change]  # type: ignore[index]
    with pytest.raises(ValidationError):
        Part.model_validate(part)


@pytest.mark.parametrize("change", [{"source": "R1"}, {"start": 0}, {"stop": 1}, {"points": 1000},
                                    {"amplitude": 0}, {"phase": float("inf")}, {"netlist": "shell"}])
def test_invalid_ac_input_never_launches_worker(ac_request: ACRequest, change: dict[str, object]) -> None:
    payload = ac_request.model_dump()
    payload["sweep"].update(change)
    with patch("backend.schematic_routes.launch_ac") as worker:
        with TestClient(app, base_url="http://localhost") as client:
            assert client.post("/api/schematic/ac", json=payload if "phase" not in change else
                               {**payload, "sweep": {**payload["sweep"], "phase": "NaN"}}).status_code == 422
        worker.assert_not_called()


@pytest.mark.parametrize("change", ["correlation", "nodes", "units", "axis", "excitation", "biases"])
def test_swapped_or_malformed_ac_worker_reports_are_rejected(ac_request: ACRequest, monkeypatch: pytest.MonkeyPatch, change: str) -> None:
    payload = simulate_ac(ac_request, "matched").model_dump()
    if change == "correlation":
        payload["correlation_id"] = "wrong"
    elif change == "nodes":
        payload["pin_nodes"]["R1:0"] = "wrong"
    elif change == "units":
        payload["traces"][0]["unit"] = "A"
    elif change == "axis":
        payload["frequencies"] = [frequency * 2 for frequency in payload["frequencies"]]
    elif change == "excitation":
        payload["excitation"]["amplitude"] = 2
    else:
        payload["dc_biases"]["V1"] = 5
    monkeypatch.setenv("CIRCUIT_WORKER_SOCKET", "/unused.sock")
    with patch("backend.schematic_ac_gateway.exchange_frame", return_value=payload):
        with pytest.raises(SimulationFailure):
            launch_ac(ac_request, "matched")


def test_ac_remote_failure_has_no_local_execution_fallback(ac_request: ACRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CIRCUIT_WORKER_SOCKET", "/missing-circuit-ac.sock")
    with patch("backend.worker_gateway.subprocess.Popen") as process:
        with pytest.raises(SimulationFailure, match="unavailable"):
            launch_ac(ac_request, "remote")
        process.assert_not_called()


@pytest.mark.parametrize("contents", ["", "0 NaN 0\n" * 2, "1 2\n" * 2, "bad\n" * 2])
def test_bad_complex_frames_fail_closed(tmp_path: Path, contents: str) -> None:
    path = tmp_path / "frequencies.csv"
    path.write_text(contents)
    with pytest.raises(SimulationFailure):
        read_complex_frames(path, ["V:n1"])


@pytest.mark.parametrize("change", ["length", "decreasing", "zero", "duplicate", "nan"])
def test_ac_contract_rejects_invalid_shared_axis(ac_request: ACRequest, change: str) -> None:
    payload = simulate_ac(ac_request, "axis").model_dump()
    if change == "length":
        payload["traces"][0]["imaginary"].pop()
    elif change == "decreasing":
        payload["frequencies"][1] = .5
    elif change == "zero":
        payload["frequencies"][0] = 0
    elif change == "duplicate":
        payload["traces"][1]["name"] = payload["traces"][0]["name"]
    else:
        payload["traces"][0]["real"][0] = float("nan")
    with pytest.raises(ValidationError):
        ACResponse.model_validate(payload)


def test_ac_http_audits_and_recovers_from_failed_worker(ac_request: ACRequest, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    audit = tmp_path / "audit.jsonl"
    monkeypatch.setenv("CIRCUIT_AUDIT_PATH", str(audit))
    with TestClient(app, base_url="http://localhost") as client:
        with patch("backend.schematic_routes.launch_ac", side_effect=SimulationFailure("busy")):
            assert client.post("/api/schematic/ac", json=ac_request.model_dump()).status_code == 503
        response = client.post("/api/schematic/ac", json=ac_request.model_dump())
        assert response.status_code == 200
        assert response.json()["correlation_id"] == response.headers["X-Correlation-ID"]
        assert client.get("/api/health").status_code == 200
    entries = [json.loads(line) for line in audit.read_text().splitlines()]
    assert [entry["outcome"] for entry in entries] == ["started", "error", "started", "completed"]
    assert all(entry["actor"] == "user:local" for entry in entries)


def test_ac_audit_storage_failure_blocks_execution(ac_request: ACRequest, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CIRCUIT_AUDIT_PATH", str(tmp_path / "missing" / "audit.jsonl"))
    with patch("backend.schematic_routes.launch_ac") as worker:
        with TestClient(app, base_url="http://localhost") as client:
            assert client.post("/api/schematic/ac", json=ac_request.model_dump()).status_code == 503
        worker.assert_not_called()


def test_ac_and_transient_share_the_same_two_job_ceiling(ac_request: ACRequest) -> None:
    ac_report = simulate_ac(ac_request, "shared").model_dump_json()
    transient_report = simulate_schematic(ac_request.circuit, "shared").model_dump_json()
    started, finish = Barrier(3), Event()

    def communicate(payload: str, timeout: int) -> tuple[str, str]:
        started.wait(timeout=5)
        assert finish.wait(timeout=5)
        return (ac_report if json.loads(payload)["operation"] == "schematic_ac" else transient_report), ""

    process = Mock(returncode=0)
    process.__enter__ = Mock(return_value=process)
    process.__exit__ = Mock(return_value=False)
    process.communicate.side_effect = communicate
    with patch("backend.worker_gateway.WORKER_SLOTS", BoundedSemaphore(2)):
        with patch("backend.worker_gateway.subprocess.Popen", return_value=process) as launch:
            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = [executor.submit(launch_ac, ac_request, "shared"),
                           executor.submit(launch_schematic, ac_request.circuit, "shared")]
                try:
                    started.wait(timeout=5)
                    with pytest.raises(SimulationFailure, match="already running"):
                        launch_ac(ac_request, "third")
                    assert launch.call_count == 2
                finally:
                    finish.set()
                assert all(future.result(timeout=5).status == "completed" for future in futures)


def test_missing_complex_output_and_solver_timeout_fail_closed(ac_request: ACRequest, tmp_path: Path) -> None:
    with pytest.raises(SimulationFailure, match="missing"):
        read_complex_frames(tmp_path / "missing.csv", ["V:n1"])
    with patch("backend.schematic_ac_engine.run_ngspice", return_value=(-99, "TIMEOUT", "")):
        with pytest.raises(SimulationFailure, match="solver failed"):
            simulate_ac(ac_request, "timeout")


def test_invalid_ac_topology_is_rejected_before_worker(ac_request: ACRequest) -> None:
    payload = ac_request.model_dump()
    payload["circuit"]["wires"] = payload["circuit"]["wires"][:1]
    with patch("backend.schematic_routes.launch_ac") as worker:
        with TestClient(app, base_url="http://localhost") as client:
            response = client.post("/api/schematic/ac", json=payload)
            assert response.status_code == 422
            assert "every terminal" in response.json()["detail"]
        worker.assert_not_called()


def test_transient_worker_units_cannot_be_swapped(ac_request: ACRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    payload = simulate_schematic(ac_request.circuit, "units").model_dump()
    payload["traces"][0]["unit"] = "A"
    monkeypatch.setenv("CIRCUIT_WORKER_SOCKET", "/unused.sock")
    with patch("backend.worker_gateway.exchange_frame", return_value=payload):
        with pytest.raises(SimulationFailure, match="units"):
            launch_schematic(ac_request.circuit, "units")


@pytest.mark.parametrize("change,expected", [("forged", 403), ("no_actor", 401), ("origin", 403)])
def test_hosted_ac_rejects_proxy_bypass_and_foreign_origins(ac_request: ACRequest, monkeypatch: pytest.MonkeyPatch, change: str, expected: int) -> None:
    secret = "ac-test-only-proxy-token-not-production"
    monkeypatch.setenv("CIRCUIT_PUBLIC_URL", "https://circuit-lab.christopherrehm.de")
    monkeypatch.setenv("CIRCUIT_PROXY_TOKEN", secret)
    headers = {"X-Circuit-Proxy-Token": secret, "X-Circuit-Actor": "test-account",
               "Origin": "https://circuit-lab.christopherrehm.de"}
    if change == "forged":
        headers["X-Circuit-Proxy-Token"] = "forged"
    elif change == "no_actor":
        del headers["X-Circuit-Actor"]
    else:
        headers["Origin"] = "https://foreign.example"
    with patch("backend.schematic_routes.launch_ac") as worker:
        with TestClient(app, base_url="http://localhost") as client:
            assert client.post("/api/schematic/ac", json=ac_request.model_dump(), headers=headers).status_code == expected
        worker.assert_not_called()


def test_maximum_frequency_budget_runs_real_engine(ac_request: ACRequest) -> None:
    sweep = Sweep(source="V1", amplitude=1.0, phase=0.0, start=.001, stop=1e6,
                  spacing="linear", points=1000)
    report = launch_ac(ac_request.model_copy(update={"sweep": sweep}), "maximum-ac")
    assert len(report.frequencies) == 1000
    assert report.frequencies[0] == pytest.approx(.001)
    assert report.frequencies[-1] == pytest.approx(1e6)
