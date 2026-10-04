"""Real pg_dump/psql restoration of immutable history; restored grants cannot revive access."""

import asyncio
import subprocess
import time
from uuid import UUID, uuid4

import pytest

from backend.project_documents import get_document
from backend.project_grants import create_grant
from backend.project_identity import PERMISSIONS
from backend.project_models import NewGrant, Principal, ProjectFailure
from backend.project_recovery import invalidate_restored_access
from tests.test_project_services import browser_identity, database_session, saved_circuit


def test_real_dump_restore_and_access_invalidation(project_database_url, project_database_container, analog_request):
    async def scenario():
        async with database_session(project_database_url) as source:
            owner = browser_identity()
            saved = await saved_circuit(source, owner, analog_request)
            document = UUID(saved["document"])
            await create_grant(source, owner, document, NewGrant(client="restore-test", scopes=list(PERMISSIONS),
                               lifetime_minutes=5), frozenset({"restore-test"}))
        backup = subprocess.run(["docker", "exec", project_database_container, "pg_dump", "-U", "postgres", "--no-owner", "postgres"],
                                check=True, capture_output=True, timeout=30).stdout
        subprocess.run(["docker", "exec", project_database_container, "createdb", "-U", "postgres", "restore_check"], check=True, timeout=10)
        subprocess.run(["docker", "exec", "-i", project_database_container, "psql", "-U", "postgres", "-d", "restore_check", "-v", "ON_ERROR_STOP=1"],
                       input=backup, check=True, capture_output=True, timeout=30)
        async with database_session(project_database_url.rsplit("/", 1)[0] + "/restore_check") as restored:
            assert (await get_document(restored, owner, document))["contents"] == saved["contents"]
            await invalidate_restored_access(restored)
            ai = Principal(owner.owner, "ai-agent:restore-test", uuid4().hex, client="restore-test", scopes=PERMISSIONS, issued_at=owner.issued_at)
            with pytest.raises(ProjectFailure, match="revoked"):
                await get_document(restored, ai, document)
            fresh = Principal(owner.owner, owner.actor, uuid4().hex, scopes=PERMISSIONS, issued_at=int(time.time()) + 2)
            assert (await get_document(restored, fresh, document))["revision"] == saved["revision"]
    asyncio.run(scenario())
