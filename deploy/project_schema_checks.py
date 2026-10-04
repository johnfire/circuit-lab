"""Exercise the first collaboration migration against isolated real PostgreSQL."""

import subprocess
import time
from pathlib import Path
from uuid import uuid4

POSTGRES_IMAGE = "postgres:17-alpine@sha256:b0f9560a2de083e2cc7382e75f808c7381a32852a7ec49117deedb300e552b24"
MIGRATION = Path(__file__).resolve().parents[1] / "backend/migrations/001_collaboration.sql"

SCHEMA_CHECKS = """
BEGIN;
INSERT INTO collaboration_documents(id, owner, name, kind, head) VALUES
('00000000-0000-0000-0000-000000000001', 'schema-owner', 'private project', 'project',
 '00000000-0000-0000-0000-000000000002');
INSERT INTO collaboration_revisions(id, document, contents, contents_hash, actor, reason, correlation_id)
VALUES ('00000000-0000-0000-0000-000000000002', '00000000-0000-0000-0000-000000000001',
 '{}', 'schema-hash', 'user:schema-check', 'initial', 'schema-check');
INSERT INTO collaboration_actions(id, owner_hash, target, actor, action, correlation_id)
VALUES ('00000000-0000-0000-0000-000000000003', 'schema-owner-hash',
 '00000000-0000-0000-0000-000000000001', 'ai-agent:schema-check', 'document.create', 'schema-check');
COMMIT;
BEGIN;
INSERT INTO collaboration_documents(id, owner, name, kind, head) VALUES
('00000000-0000-0000-0000-000000000011', 'other-owner', 'other project', 'project',
 '00000000-0000-0000-0000-000000000012');
INSERT INTO collaboration_revisions(id, document, contents, contents_hash, actor, reason, correlation_id)
VALUES ('00000000-0000-0000-0000-000000000012', '00000000-0000-0000-0000-000000000011',
 '{}', 'other-hash', 'user:schema-check', 'initial', 'schema-check');
COMMIT;
DO $$ BEGIN
    BEGIN
        UPDATE collaboration_revisions SET contents = '{"tampered":true}';
        RAISE EXCEPTION 'Revision update unexpectedly succeeded';
    EXCEPTION WHEN OTHERS THEN
        IF SQLERRM <> 'Collaboration revisions are immutable' THEN RAISE; END IF;
    END;
    BEGIN
        UPDATE collaboration_actions SET action = 'tampered';
        RAISE EXCEPTION 'Audit update unexpectedly succeeded';
    EXCEPTION WHEN OTHERS THEN
        IF SQLERRM <> 'Collaboration audit is append-only' THEN RAISE; END IF;
    END;
    BEGIN
        DELETE FROM collaboration_actions;
        RAISE EXCEPTION 'Audit delete unexpectedly succeeded';
    EXCEPTION WHEN OTHERS THEN
        IF SQLERRM <> 'Collaboration audit is append-only' THEN RAISE; END IF;
    END;
    BEGIN
        UPDATE collaboration_documents SET head = '00000000-0000-0000-0000-000000000004';
        SET CONSTRAINTS collaboration_document_head IMMEDIATE;
        RAISE EXCEPTION 'Dangling document head unexpectedly succeeded';
    EXCEPTION WHEN foreign_key_violation THEN NULL;
    END;
    BEGIN
        INSERT INTO collaboration_runs(id, document, revision, analysis, settings, status,
                                       actor, correlation_id, build_id)
        VALUES ('00000000-0000-0000-0000-000000000021', '00000000-0000-0000-0000-000000000001',
                '00000000-0000-0000-0000-000000000012', 'transient', '{}', 'running',
                'ai-agent:schema-check', 'schema-check', 'local');
        RAISE EXCEPTION 'Cross-circuit simulation revision unexpectedly succeeded';
    EXCEPTION WHEN foreign_key_violation THEN NULL;
    END;
END $$;
SELECT 'real migration, deferred heads, immutable history and cross-circuit isolation checks passed';
"""


def run_command(arguments: list[str], submitted: str | None = None) -> str:
    """Bound each Docker/psql operation and surface failures without hiding them."""
    completed_process = subprocess.run(arguments, input=submitted, text=True, capture_output=True,
                                       check=False, timeout=90)
    if completed_process.returncode:
        raise RuntimeError(f"Schema-check operation failed: {completed_process.stderr.strip()}")
    return completed_process.stdout


def wait_for_database(container: str) -> None:
    """Wait briefly for only the container created by this check."""
    for _ in range(50):
        ready = subprocess.run(["docker", "exec", container, "pg_isready", "-U", "postgres"],
                               capture_output=True, timeout=3)
        if ready.returncode == 0:
            return
        time.sleep(.2)
    raise RuntimeError("Isolated schema-check PostgreSQL did not become ready")


def check_schema() -> None:
    """Retain and stop the test container; never touch identity or production volumes."""
    container = f"circuit-lab-schema-check-{uuid4().hex[:12]}"
    run_command(["docker", "run", "-d", "--name", container, "--network", "none",
                 "--memory", "256m", "--cpus", "0.5", "--pids-limit", "100",
                 "-e", "POSTGRES_HOST_AUTH_METHOD=trust", POSTGRES_IMAGE])
    try:
        wait_for_database(container)
        psql = ["docker", "exec", "-i", container, "psql", "-U", "postgres", "-v", "ON_ERROR_STOP=1"]
        migration = MIGRATION.read_text()
        run_command(psql, migration)
        run_command(psql, migration)
        print(run_command(psql, SCHEMA_CHECKS).strip())
    finally:
        run_command(["docker", "stop", container])
        print(f"Stopped retained schema-check container: {container}")


if __name__ == "__main__":
    check_schema()
