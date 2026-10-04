"""Real isolated PostgreSQL for repository/protocol/browser tests, stopped and retained."""

import json
import subprocess
from uuid import uuid4

import pytest

from deploy.project_schema_checks import POSTGRES_IMAGE, wait_for_database


@pytest.fixture(scope="session")
def project_database_container():
    container = "circuit-lab-repository-test-" + uuid4().hex[:12]
    subprocess.run(["docker", "run", "-d", "--name", container, "--memory", "256m", "--cpus", "0.5",
        "--pids-limit", "100", "-p", "127.0.0.1::5432", "-e", "POSTGRES_HOST_AUTH_METHOD=trust",
        POSTGRES_IMAGE], check=True, capture_output=True, text=True, timeout=90)
    try:
        wait_for_database(container)
        yield container
    finally:
        subprocess.run(["docker", "stop", container], check=True, capture_output=True, timeout=30)
        print("Stopped retained repository-test PostgreSQL: " + container)


@pytest.fixture(scope="session")
def project_database_url(project_database_container):
    inspected = subprocess.run(["docker", "inspect", project_database_container], check=True, capture_output=True,
                               text=True, timeout=10)
    host_port = json.loads(inspected.stdout)[0]["NetworkSettings"]["Ports"]["5432/tcp"][0]["HostPort"]
    return "postgresql://postgres@127.0.0.1:" + host_port + "/postgres"
