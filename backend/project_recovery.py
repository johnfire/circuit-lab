"""Operator-only disaster restore invalidation; never exposed as a browser/MCP tool."""

import time
from uuid import UUID, uuid4

from backend.project_access import audit_action
from backend.project_database import ProjectDatabase
from backend.project_models import Principal


async def invalidate_restored_access(database: ProjectDatabase) -> None:
    """A restored backup must not resurrect grants or stale tokens revoked after that backup."""
    minimum = int(time.time()) + 1
    async with database.available_pool().acquire() as connection, connection.transaction():
        await connection.execute("UPDATE collaboration_grants SET revoked_at=clock_timestamp() WHERE revoked_at IS NULL")
        await connection.execute("UPDATE collaboration_accounts SET minimum_token_iat=GREATEST(minimum_token_iat,$1)", minimum)
        documents = await connection.fetch("SELECT id,owner,head FROM collaboration_documents")
        correlation = str(uuid4())
        for document in documents:
            actor = Principal(str(document["owner"]), "operator:restore-recovery", correlation)
            revision = UUID(str(document["head"]))
            await audit_action(connection, actor, UUID(str(document["id"])), "backup.restored_access_invalidated", (revision, revision))
