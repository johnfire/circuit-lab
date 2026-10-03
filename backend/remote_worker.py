"""Client boundary for the separately containerized, network-disabled worker."""

from pydantic import ValidationError

from backend.simulation_engine import SimulationFailure
from backend.simulation_models import SimulationRequest, SimulationResponse
from backend.worker_protocol import exchange_frame


def request_worker_simulation(socket_path: str, circuit_id: str,
                              submitted: SimulationRequest,
                              correlation_id: str) -> SimulationResponse:
    """Send structured values only; never fall back to execution in the API."""
    try:
        payload = exchange_frame(socket_path, {
            "circuit_id": circuit_id, "request": submitted.model_dump(),
            "correlation_id": correlation_id,
        })
        if "error" in payload:
            raise SimulationFailure(str(payload["error"]))
        report = SimulationResponse.model_validate(payload)
        if report.circuit_id != circuit_id or report.correlation_id != correlation_id:
            raise SimulationFailure("Simulation worker returned a mismatched report")
        return report
    except (OSError, ValueError, ValidationError) as error:
        raise SimulationFailure("Simulation worker is unavailable or returned invalid output") from error
