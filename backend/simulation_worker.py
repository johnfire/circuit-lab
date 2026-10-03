"""Short-lived, resource-limited process for a single curated simulation."""

import json
import resource
import sys

from backend.simulation_engine import simulate
from backend.simulation_models import SimulationRequest


def run_worker() -> None:
    """Bound resources before executing ngspice and serialize one response."""
    resource.setrlimit(resource.RLIMIT_CPU, (12, 12))
    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_FSIZE, (32 * 1024 * 1024, 32 * 1024 * 1024))
    payload = json.loads(sys.stdin.read(8192))
    request = SimulationRequest.model_validate(payload["request"])
    report = simulate(payload["circuit_id"], request, payload["correlation_id"])
    sys.stdout.write(report.model_dump_json())


if __name__ == "__main__":
    run_worker()
