# MCP implementation status — 2026-10-04

This is the local collaboration implementation of the
[approved circuit collaboration design](plans/2026-10-04-mcp-circuit-collaboration.md).
The application mounts an authenticated Streamable HTTP server, but the VPS
dependencies and actual Codex connection have not been activated or verified.

## Implemented locally

- Approved pinned dependencies: MCP SDK 2.3.0 and asyncpg 0.31.0. Runtime and
  frontend dependency audits are clean.
- Transactional application-only PostgreSQL services shared by REST and MCP:
  private projects, independently shared workspaces, immutable complete
  revisions, expected-revision writes, idempotent retries, actor/correlation
  audit, non-destructive undo/restore, and credential-free account export.
- Exact owner/client/scope checks on every operation. OAuth grant creation and
  revocation belong to the human browser, not AI edit tools. Grants are bounded
  and expire; a guessed UUID, resource URI or forged actor does not grant access.
- Native Keycloak introspection checks issuer, active session, verified email,
  subject, expiry, resource audience and approved client. Password-event
  reconciliation invalidates old tokens/grants; actual account deletion cascades
  application content. Hosted access fails closed if lifecycle checks fail.
- Browser save/open, explicit sharing, workspace recovery, history, server undo
  and conflict choices. Unsent local edits are preserved. Saved projects are
  manually saved; live workspaces synchronize acknowledged snapshots.
- Revision-bound asynchronous real ngspice transient and AC runs, bounded
  admission, durable run IDs and honest interrupted/failed statuses. Results
  appear on the grid only while its circuit/settings still match that revision.
- Full-sample measurement and paginated evidence: node/differential voltage,
  signed branch current, transient RMS/AC-only RMS, AC complex samples and
  excitation-relative phase, declarative checks and simulation comparisons.
- Revision-bound probe/cursor requests. The browser applies them without
  autoplay and acknowledges after rendering. Unavailable axes/results leave
  the request pending; the AI can inspect pending/acknowledged/expired status.
- Authenticated `/mcp`, protected resource metadata, live orientation, four
  prompts, and authorized circuit/run resources. The separate in-process
  foundation server still reports its orientation-only boundary truthfully.
- Opt-in Compose overlay, proxy routes, reviewed Codex OAuth recipe and
  least-privilege identity configuration generator. Defaults remain disabled.
- Real PostgreSQL schema/repository, real SDK editing/solver, real-database
  browser flow, real Keycloak verification and pg_dump/psql restore checks.
  CI runs these alongside the unchanged existing suites and coverage gate.

No production database, Keycloak realm, VPS configuration or Codex settings were
changed. No commit from this task was pushed by this implementation step.

## Capability boundaries

AI tools can discover shared targets, inspect/validate, edit/replace, compare
revisions, undo/restore, run transient/AC jobs, recover recent run IDs, read
samples, measure, evaluate checks, compare runs, export and request observation
views. Creating/copying projects and changing sharing remain browser actions.

Manual access tokens, unrestricted dynamic client registration, embedded AI
chat, arbitrary SPICE/code, semiconductor graph models and hardware/GPIO control
are not enabled. Curated recipe examples are not editable graph templates.
Time-domain settled sine-phase qualification remains a browser feature; AC
phase evidence is available through MCP. Simulation is not hardware approval.

Prototype quotas: 20 documents/account, 250 revisions/document, 10,000 revisions
globally; one active run/account, two globally, ten admitted runs/account/minute,
2,000 stored runs globally. Pagination is bounded. Production retention and
capacity planning are operator work, not silently enabled deletion jobs.

## Remaining activation gates

1. Push only when Chris requests it; verify CI on the exact revision.
2. Provision application storage separately from the identity database; configure
   secrets only in protected VPS environment files.
3. Add reviewed OAuth clients/scopes, both audience mappers, the basic identity
   scope, read-only service-account roles **and** role scope mappings. Preserve
   the existing browser client, SMTP settings and account lifecycle features.
4. Install/review proxy and receiver changes, test live backup restoration and
   restored-access invalidation, and configure encrypted backups/retention.
5. Verify production browser save/share/revoke and account lifecycle, then sign
   Codex in and exercise a shared circuit. A genuine Keycloak bearer was tested
   locally, but the actual Codex app's OAuth sign-in is not yet verified.

See [activation runbook](../deploy/MCP.md). Commercial readiness, live backups,
production deletion latency and an external Codex connection are not claimed.

## Local verification

Final local checks: 294 pytest checks passed with 82.66% aggregate coverage
(original 70% gate unchanged), 22 frontend unit tests, 16 existing desktop/mobile
browser tests, lint/strict typing/production build, both real PostgreSQL migrations,
actual dump restoration, real Keycloak HTTP bearer/lifecycle checks, clean
dependency audits and a successful production-style API image build.

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

`pytest` includes the separate real-database browser suite, supplying its own
loopback PostgreSQL fixture. Run `test:projects` through that fixture, not against
production. CI also runs `deploy.mcp_identity_checks` against its disposable
identity stack; production clients never enable its synthetic password grant.

The real identity test found and fixed missing introspection-client audience
and basic-subject scope configuration. Test fixture corrections preserved
assertions: normalized JSON fields, genuinely changed local timing, selected
component identity and the restoration database path. Existing test failures
were not hidden, skipped or weakened.

Schema and repository checkers stop and retain their uniquely named test
containers. The local identity check uses only synthetic fixture credentials on
loopback. Test resources are retained rather than deleted; no production volume
or application credential is used.
