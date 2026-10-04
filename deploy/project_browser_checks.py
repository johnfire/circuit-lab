"""Real browser test's AI peer: typed services against an isolated loopback test database."""

import asyncio
import json
import os
import sys
import urllib.parse
from uuid import UUID, uuid4

from backend.project_database import ProjectDatabase, connect_database
from backend.project_documents import get_document, mutate_document
from backend.project_identity import PERMISSIONS
from backend.project_models import DocumentContents, EditDocument, Principal
from backend.project_views import ObservationCommand, set_view
from backend.schematic_models import Pin


async def edit_test_workspace(document: UUID, value: float) -> None:
    """No network endpoint or bearer bypass; this helper only accepts explicit test configuration."""
    database = await open_test_database()
    try:
        ai = Principal("local", "ai-agent:codex-test", uuid4().hex, client="codex-test", scopes=PERMISSIONS)
        saved = await get_document(database, ai, document)
        contents = DocumentContents.model_validate(saved["contents"])
        part = next(part for part in contents.circuit.parts if part.id == "R1").model_dump(mode="json")
        updated = await mutate_document(database, ai, document, EditDocument.model_validate({
            "expected_revision": saved["revision"], "idempotency_key": str(uuid4()), "reason": "Browser-test AI resistor edit",
            "edits": [{"operation": "put_part", "part": {**part, "value": value}}]}))
        await set_view(database, ai, document, ObservationCommand(revision=UUID(str(updated["revision"])),
            time=.02, pins=[Pin(part="C1", terminal=0)]))
        print(json.dumps({"revision": updated["revision"]}))
    finally:
        await database.available_pool().close()


async def open_test_database() -> ProjectDatabase:
    """Only a deliberately enabled loopback fixture can host the synthetic AI actor."""
    address = os.environ.get("CIRCUIT_DATABASE_URL", "")
    parsed = urllib.parse.urlparse(address)
    if os.environ.get("CIRCUIT_BROWSER_TEST") != "1" or parsed.hostname != "127.0.0.1" or parsed.path != "/postgres":
        raise ValueError("Only an explicitly enabled isolated loopback test database is allowed")
    return ProjectDatabase(await connect_database(address))


async def request_test_view(document: UUID) -> None:
    """Seek an existing revision without changing the graph, testing user zoom interaction."""
    database = await open_test_database()
    try:
        ai = Principal("local", "ai-agent:codex-test", uuid4().hex, client="codex-test", scopes=PERMISSIONS)
        saved = await get_document(database, ai, document)
        await set_view(database, ai, document, ObservationCommand(revision=UUID(str(saved["revision"])), time=.02))
    finally:
        await database.available_pool().close()


if __name__ == "__main__":
    if sys.argv[1] == "view":
        asyncio.run(request_test_view(UUID(sys.argv[2])))
    else:
        asyncio.run(edit_test_workspace(UUID(sys.argv[1]), float(sys.argv[2])))
