"""Application-owned database/jobs/identity health, with unrelated routes kept independent."""

import asyncio
import logging
import os
import urllib.parse
from dataclasses import dataclass, field

import asyncpg
from fastapi import Request

from backend.project_database import ProjectDatabase, connect_database
from backend.project_identity import KeycloakVerifier, browser_principal, configured_verifier
from backend.project_lifecycle import reconcile_accounts
from backend.project_models import Principal, ProjectFailure
from backend.project_runs import RunJobs, recover_interrupted_runs
from backend.request_security import public_url

LOGGER = logging.getLogger("circuit-lab.collaboration")


@dataclass
class CollaborationRuntime:
    """Only actual healthy dependencies enable saved circuits and MCP invocation."""

    database: ProjectDatabase = field(default_factory=ProjectDatabase)
    verifier: KeycloakVerifier = field(default_factory=configured_verifier)
    identity_ready: bool = False
    lifecycle: asyncio.Task[None] | None = None
    jobs: RunJobs = field(init=False)

    def __post_init__(self) -> None:
        self.jobs = RunJobs(self.database, os.environ.get("CIRCUIT_BUILD_ID", "local"))

    async def start(self) -> None:
        """Do not take down catalog/offline drafts if application storage fails."""
        dsn = os.environ.get("CIRCUIT_DATABASE_URL", "")
        if not dsn:
            return
        try:
            parsed = urllib.parse.urlparse(dsn)
            if public_url() and (parsed.hostname != "application-db" or parsed.path != "/circuit_application"):
                LOGGER.error("Hosted storage must use the separate application database; collaboration disabled")
                return
            self.database.pool = await connect_database(dsn)
            await recover_interrupted_runs(self.database)
            if not public_url():
                self.identity_ready = True
            else:
                self.lifecycle = asyncio.create_task(self.reconcile_loop())
        except (asyncpg.PostgresError, OSError, ValueError, TimeoutError):
            LOGGER.error("Application database unavailable; collaboration disabled")

    async def reconcile_loop(self) -> None:
        """On lifecycle outage deny collaboration, then recover without restarting the app."""
        while True:
            try:
                await reconcile_accounts(self.database, self.verifier)
                self.identity_ready = True
            except (ProjectFailure, asyncpg.PostgresError, OSError, ValueError, TimeoutError):
                self.identity_ready = False
                LOGGER.error("Identity lifecycle unavailable; collaboration access denied")
            await asyncio.sleep(15)

    def require_ready(self) -> None:
        """A login cookie alone cannot bypass lifecycle/account checks."""
        self.database.available_pool()
        if not self.identity_ready:
            raise ProjectFailure("Account security synchronization is unavailable; try again shortly", 503)

    async def browser(self, request: Request) -> Principal:
        """Use the same verified principal for all browser collaboration requests."""
        self.require_ready()
        principal = await browser_principal(request, self.verifier)
        await self.check_identity(principal)
        return principal

    async def check_identity(self, principal: Principal) -> None:
        """Password/deletion lifecycle is checked on each operation, not only by a timer."""
        if not public_url():
            return
        try:
            await reconcile_accounts(self.database, self.verifier, principal.owner)
        except (ProjectFailure, asyncpg.PostgresError, OSError, ValueError, TimeoutError) as failure:
            self.identity_ready = False
            raise ProjectFailure("Account security synchronization failed; access denied", 503) from failure

    async def close(self) -> None:
        """Drain owned jobs, cancel polling and close only the application pool."""
        if self.lifecycle:
            self.lifecycle.cancel()
            await asyncio.gather(self.lifecycle, return_exceptions=True)
        await self.jobs.close()
        if self.database.pool:
            await self.database.pool.close()
            self.database.pool = None
