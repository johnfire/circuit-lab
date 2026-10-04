"""Bounded application PostgreSQL connections, migrations and JSON record conversion."""

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import asyncpg

from backend.project_models import ProjectFailure

MIGRATIONS = Path(__file__).with_name("migrations")


@dataclass
class ProjectDatabase:
    """One application pool, independent of identity and the simulation worker."""

    pool: asyncpg.Pool | None = None

    def available_pool(self) -> asyncpg.Pool:
        """Fail one collaboration operation without breaking offline circuit editing."""
        if self.pool is None:
            raise ProjectFailure("Saved circuits are unavailable; your local draft is unchanged", 503)
        return self.pool


async def connect_database(dsn: str) -> asyncpg.Pool:
    """Create a small bounded pool, then migrate under one advisory lock."""
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=4, command_timeout=10)
    try:
        async with pool.acquire() as connection:
            async with connection.transaction():
                await connection.execute("SELECT pg_advisory_xact_lock(582349105)")
                await connection.execute("CREATE TABLE IF NOT EXISTS collaboration_schema_versions "
                                         "(version text PRIMARY KEY, applied_at timestamptz DEFAULT now())")
                for migration in sorted(MIGRATIONS.glob("*.sql")):
                    applied = await connection.fetchval(
                        "SELECT version FROM collaboration_schema_versions WHERE version=$1", migration.name)
                    if applied is None:
                        await connection.execute(migration.read_text())
                        await connection.execute("INSERT INTO collaboration_schema_versions(version) VALUES($1)",
                                                 migration.name)
        return pool
    except (asyncpg.PostgresError, OSError, TimeoutError):
        await pool.close()
        raise


def encode_json(submitted: object) -> str:
    """Serialize bounded contracts at the database edge, never executable text."""
    return json.dumps(submitted, default=str, separators=(",", ":"), allow_nan=False)


def decode_record(submitted: object) -> dict[str, object]:
    """Read JSON objects only; reject malformed stored or external evidence."""
    decoded: object = json.loads(submitted) if isinstance(submitted, str) else submitted
    if not isinstance(decoded, dict):
        raise ProjectFailure("Stored circuit record is invalid", 503)
    return cast(dict[str, object], decoded)


def owner_hash(owner: str) -> str:
    """Keep audit ownership opaque and stable across account-content deletion."""
    return hashlib.sha256(owner.encode()).hexdigest()
