"""Append-only action records with a correlation ID and explicit actor."""

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

from backend.simulation_engine import SimulationFailure

AUDIT_LOCK = Lock()
LOGGER = logging.getLogger("circuit-lab")


def record_simulation(circuit_id: str, correlation_id: str, outcome: str,
                      actor: str = "user:local") -> None:
    """Append an explicitly attributed action without storing submitted content."""
    event = {"timestamp": datetime.now(timezone.utc).isoformat(), "level": "INFO",
             "source": "simulation", "actor": actor, "action": "simulation.run",
             "target": circuit_id, "correlation_id": correlation_id, "outcome": outcome}
    audit_path = Path(os.environ.get("CIRCUIT_AUDIT_PATH", "/tmp/circuit-lab-audit.jsonl"))
    try:
        with AUDIT_LOCK:
            with audit_path.open("a", encoding="utf-8") as audit_file:
                audit_file.write(json.dumps(event) + "\n")
    except OSError as error:
        LOGGER.error("Simulation audit unavailable; correlation_id=%s", correlation_id)
        raise SimulationFailure("Simulation audit is unavailable; no unlogged jobs are accepted") from error
    LOGGER.info(json.dumps(event))
