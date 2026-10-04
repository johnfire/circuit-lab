# MCP implementation status — 2026-10-04

This is the first implementation slice of the
[approved circuit collaboration design](plans/2026-10-04-mcp-circuit-collaboration.md).
It is not yet a connectable remote MCP service.

## Implemented locally

- Official Python MCP SDK 2.3.0, pinned in the lockfile; dependency audit passed.
- Real SDK tool/resource/prompt discovery, verified with the SDK's in-process client.
- Five read-only orientation tools: `get_app_guide`, `get_capabilities`,
  `list_components`, `get_component`, and `list_examples`.
- Four workflow prompts and the `circuit-lab://guide` resource. Capabilities
  explicitly report that circuit collaboration and MCP simulation are disabled.
- One canonical component catalog used by Python and the grid's TypeScript code;
  existing values and limits are preserved.
- Strict construction-valid circuit snapshots and bounded, declarative edit
  operations. An unfinished circuit can be represented without claiming that it
  can simulate. Revision/idempotency identifiers and actor/correlation metadata
  are typed contracts, not yet durable concurrency or undo services.
- Full-sample paginated measurements, signed differential voltages, branch
  currents, time-weighted transient statistics and declarative numerical checks.
  AC summaries preserve complex samples, excitation-relative phase, frequency
  units and actual sampled windows; they do not invent time-domain RMS.
- Initial application-only PostgreSQL schema with same-circuit revision/grant
  references, immutable revision updates and append-only audit records. The
  migration is checked against a real isolated PostgreSQL 17 container in CI,
  including reapplication, deferred heads and cross-circuit reference rejection.

No new routes are mounted in the existing FastAPI application. No production
database, Keycloak realm, VPS configuration or browser sharing UI is changed.

## Approval needed

The SDK was approved. Approval for `asyncpg` (Apache-2.0) is still pending. It is
not installed or imported. This additional driver is needed for the proposed
PostgreSQL repository and transactional services.

## Remaining before users can connect an AI

1. Add the approved database driver and implement/test transactional persistence,
   owner isolation, grant checks, atomic expected-revision writes and retry safety.
2. Integrate verified OAuth client identity with Keycloak, bounded scoped access,
   revocation, account deletion and data export. Neither raw user headers nor an
   unauthenticated SDK endpoint may authorize access.
3. Implement saved projects and explicit live-workspace sharing in the browser,
   conflict handling, refresh/acknowledgement and undo as new revisions.
4. Register circuit/revision/run/measurement/view tools through the same services
   as browser requests. Bind reports to the exact circuit revision and build.
5. Mount authenticated Streamable HTTP, test an external AI client, configure the
   separate application database, and verify account security and deployment.

Public deployment is not enabled by this slice. Commit locally; push and live
configuration require the user's authorization.

## Local verification

```sh
uv run ruff check backend harness tests deploy
uv run mypy backend deploy
uv run pytest --cov=backend --cov=harness --cov-report=term-missing --cov-fail-under=70
uv run python -m deploy.project_schema_checks
npm run lint --prefix frontend
npm run test:unit --prefix frontend
npm run build --prefix frontend
npm run test:e2e --prefix frontend
```

The schema checker creates only a uniquely named, network-isolated test
container. It stops and retains that container after the check; it does not use
production ports, identity volumes or application credentials.
