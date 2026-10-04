"""Actual grant/revision-bound view delivery and interrupted-run recovery in PostgreSQL."""

import asyncio
from uuid import UUID, uuid4

import pytest

from backend.project_grants import create_grant, revoke_grants
from backend.project_identity import PERMISSIONS
from backend.project_models import NewGrant, Principal, ProjectFailure
from backend.project_runs import get_run, recover_interrupted_runs
from backend.project_views import (
    ObservationCommand,
    acknowledge_view,
    pending_view,
    set_view,
    view_status,
)
from tests.test_project_services import browser_identity, database_session, saved_circuit


def test_live_view_is_grant_bound_acknowledged_and_not_replayed_after_revocation(project_database_url, analog_request):
    async def scenario():
        async with database_session(project_database_url) as database:
            owner = browser_identity()
            saved = await saved_circuit(database, owner, analog_request)
            document, revision = UUID(saved["document"]), UUID(saved["revision"])
            async with database.available_pool().acquire() as connection:
                await connection.execute("UPDATE collaboration_documents SET kind='workspace' WHERE id=$1", document)
            ai = Principal(owner.owner, "ai-agent:view-test", uuid4().hex, client="view-test", scopes=PERMISSIONS, issued_at=owner.issued_at)
            await create_grant(database, owner, document, NewGrant(client="view-test", scopes=list(PERMISSIONS),
                               lifetime_minutes=5), frozenset({"view-test"}))
            queued = await set_view(database, ai, document, ObservationCommand(revision=revision, time=.02))
            command = UUID(queued["command"])
            assert (await pending_view(database, owner, document))["id"] == str(command)
            assert (await view_status(database, ai, document, command))["status"] == "pending_browser_acknowledgement"
            with pytest.raises(ProjectFailure, match="Only the browser"):
                await acknowledge_view(database, ai, document, command)
            await acknowledge_view(database, owner, document, command)
            assert (await view_status(database, ai, document, command))["status"] == "acknowledged"
            assert await pending_view(database, owner, document) is None
            with pytest.raises(ProjectFailure, match="only one physical cursor"):
                await set_view(database, ai, document, ObservationCommand(revision=revision, time=.02, frequency=100))
            await set_view(database, ai, document, ObservationCommand(revision=revision, frequency=100))
            await revoke_grants(database, owner, document)
            assert await pending_view(database, owner, document) is None
            with pytest.raises(ProjectFailure, match="expired"):
                await view_status(database, ai, document, command)
    asyncio.run(scenario())


def test_restart_never_labels_unfinished_samples_as_completed(project_database_url, analog_request):
    async def scenario():
        async with database_session(project_database_url) as database:
            owner = browser_identity()
            saved = await saved_circuit(database, owner, analog_request)
            document, revision, run = UUID(saved["document"]), UUID(saved["revision"]), uuid4()
            async with database.available_pool().acquire() as connection:
                await connection.execute("INSERT INTO collaboration_runs(id,document,revision,analysis,settings,status,actor,correlation_id,build_id) "
                    "VALUES($1,$2,$3,'transient','{}','running',$4,$5,'test')", run, document, revision, owner.actor, owner.correlation_id)
            await recover_interrupted_runs(database)
            recovered = await get_run(database, owner, document, run)
            assert recovered["status"] == "interrupted" and recovered["report"] is None
            async with database.available_pool().acquire() as connection:
                assert await connection.fetchval("SELECT actor FROM collaboration_actions WHERE target=$1 AND action='simulation.interrupted'", document) == "service:run-recovery"
    asyncio.run(scenario())
