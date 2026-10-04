"""Bounded, acknowledged browser observation commands; never JavaScript or autoplay."""

from uuid import UUID, uuid4

from pydantic import Field

from backend.project_access import audit_action, authorize
from backend.project_database import ProjectDatabase, decode_record
from backend.project_documents import read_snapshot
from backend.project_models import DocumentContents, Principal, ProjectFailure
from backend.schematic_models import Finite, Pin, StrictModel


class ObservationCommand(StrictModel):
    """Seek physical time/frequency and highlight up to eight existing stable pins."""

    revision: UUID
    pins: list[Pin] = Field(default_factory=list, max_length=8)
    time: Finite | None = Field(default=None, ge=0, le=10)
    frequency: Finite | None = Field(default=None, ge=.001, le=1e6)


async def set_view(database: ProjectDatabase, principal: Principal, document: UUID,
                   command: ObservationCommand) -> dict[str, object]:
    """Queue for one granted workspace; queued is not a claim that the UI moved."""
    if not principal.client:
        raise ProjectFailure("Observation commands require a verified AI connection", 403)
    async with database.available_pool().acquire() as connection, connection.transaction():
        owned = await authorize(connection, principal, document, "view")
        if owned["kind"] != "workspace" or str(owned["head"]) != str(command.revision):
            raise ProjectFailure("Select a live shared workspace at its current revision", 409)
        snapshot = await read_snapshot(connection, document, command.revision)
        contents = DocumentContents.model_validate(snapshot["contents"])
        pins = {f"{part.id}:{terminal}" for part in contents.circuit.parts
                for terminal in range(1 if part.kind == "GND" else 2)}
        if any(f"{pin.part}:{pin.terminal}" not in pins for pin in command.pins) or (
                command.time is not None and command.frequency is not None):
            raise ProjectFailure("Choose existing pins and only one physical cursor axis")
        count = await connection.fetchval("SELECT count(*) FROM collaboration_view_commands")
        if int(str(count)) >= 2000:
            raise ProjectFailure("Observation command quota reached", 429)
        grant = await connection.fetchval("SELECT id FROM collaboration_grants WHERE document=$1 AND client=$2 "
            "AND owner=$3 AND mode='oauth' AND revoked_at IS NULL AND expires_at>clock_timestamp() AND 'view'=ANY(scopes) "
            "ORDER BY created_at DESC LIMIT 1", document, principal.client, principal.owner)
        identifier = uuid4()
        await connection.execute("INSERT INTO collaboration_view_commands(id,document,grant_id,revision,command) "
            "VALUES($1,$2,$3,$4,$5::jsonb)", identifier, document, grant, command.revision, command.model_dump_json())
        await audit_action(connection, principal, document, "view.queued")
        return {"command": str(identifier), "status": "pending_browser_acknowledgement", "expires_in_seconds": 30}


async def pending_view(database: ProjectDatabase, principal: Principal, document: UUID) -> dict[str, object] | None:
    """Stale/revoked commands are not delivered to the current tab or another tab."""
    async with database.available_pool().acquire() as connection, connection.transaction():
        owned = await authorize(connection, principal, document, "read")
        rows = await connection.fetch("SELECT v.id,v.command FROM collaboration_view_commands v JOIN collaboration_grants g "
            "ON g.id=v.grant_id WHERE v.document=$1 AND v.revision=$2 AND v.acknowledged_at IS NULL "
            "AND v.expires_at>clock_timestamp() AND g.revoked_at IS NULL AND g.expires_at>clock_timestamp() "
            "ORDER BY v.expires_at DESC LIMIT 1", document, owned["head"])
        return {"id": str(rows[0]["id"]), "command": decode_record(rows[0]["command"])} if rows else None


async def acknowledge_view(database: ProjectDatabase, principal: Principal,
                           document: UUID, command: UUID) -> dict[str, object]:
    """A human browser acknowledges only a live command on this exact workspace head."""
    if principal.client:
        raise ProjectFailure("Only the browser can acknowledge a displayed view", 403)
    async with database.available_pool().acquire() as connection, connection.transaction():
        owned = await authorize(connection, principal, document, "read")
        identifier = await connection.fetchval("UPDATE collaboration_view_commands v SET acknowledged_at=clock_timestamp() "
            "FROM collaboration_grants g WHERE v.id=$1 AND v.document=$2 AND v.revision=$3 "
            "AND g.id=v.grant_id AND v.expires_at>clock_timestamp() AND g.revoked_at IS NULL "
            "AND g.expires_at>clock_timestamp() RETURNING v.id", command, document, owned["head"])
        if identifier is None:
            raise ProjectFailure("Observation command expired or the circuit changed", 409)
        await audit_action(connection, principal, document, "view.acknowledged")
        return {"status": "acknowledged", "command": str(identifier)}


async def view_status(database: ProjectDatabase, principal: Principal, document: UUID, command: UUID) -> dict[str, object]:
    """Let the requesting client distinguish displayed, expired and merely queued views."""
    async with database.available_pool().acquire() as connection, connection.transaction():
        await authorize(connection, principal, document, "view")
        row = await connection.fetchrow("SELECT v.acknowledged_at,v.expires_at>clock_timestamp() AS live,g.client "
            "FROM collaboration_view_commands v JOIN collaboration_grants g ON v.grant_id=g.id "
            "WHERE v.id=$1 AND v.document=$2", command, document)
        if row is None or (principal.client and row["client"] != principal.client):
            raise ProjectFailure("Observation command not found", 404)
        status = "acknowledged" if row["acknowledged_at"] else "pending_browser_acknowledgement" if row["live"] else "expired"
        return {"command": str(command), "status": status}
