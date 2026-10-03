"""Private IPC health probe for Docker Compose readiness."""

import os

from backend.worker_protocol import exchange_frame


def check_worker() -> None:
    """Fail the container health check if the local worker is not responsive."""
    socket_path = os.environ.get("CIRCUIT_WORKER_LISTEN", "/run/circuit-lab/worker.sock")
    if exchange_frame(socket_path, {"operation": "health"}) != {"status": "ok"}:
        raise RuntimeError("Simulation worker is not healthy")


if __name__ == "__main__":
    check_worker()
