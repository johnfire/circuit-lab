"""Runs the real-database browser suite explicitly in CI, never mocked or skipped."""

import os
import subprocess
from pathlib import Path


def test_real_database_browser_collaboration(project_database_url):
    environment = dict(os.environ, CIRCUIT_DATABASE_URL=project_database_url,
                       CIRCUIT_MCP_CLIENTS="codex-test", CIRCUIT_BROWSER_TEST="1")
    environment.pop("CIRCUIT_PUBLIC_URL", None)
    subprocess.run(["npm", "run", "test:projects"], cwd=Path(__file__).resolve().parents[1] / "frontend",
                   env=environment, check=True, timeout=120)
