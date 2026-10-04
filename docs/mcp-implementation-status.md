# MCP implementation status — 2026-10-04

This is the local collaboration implementation of the
[approved circuit collaboration design](plans/2026-10-04-mcp-circuit-collaboration.md).
The application code is deployed on the VPS. OAuth entries, native MCP routes
and separate application storage are staged, but saved-circuit access remains
disabled pending an encrypted off-host backup destination. The actual Codex
connection has not yet been installed, authenticated or verified.

## Rollout progress

- Chris authorized push and activation. `e3178a6` was pushed; its first CI run
  correctly blocked deployment when the database browser suite reached a 404
  because frontend assets had not yet been built.
- `9dad83e1fbe819e53d1c4d796e107dea2aa03abb` moves the existing frontend build
  before pytest and adds a build-order regression test. No browser assertion or
  test timeout was weakened. All CI jobs passed, including 295 pytest checks
  with 82.66% coverage, real Keycloak lifecycle checks and container isolation.
- [Verified CI/deployment run](https://github.com/johnfire/circuit-lab/actions/runs/37199435278)
  delivered that exact revision. Loopback health and the current release pointer
  confirm it is live. Landing 200, protected workbench 302 and identity admin 403
  remain correct.
- Root-private configuration and identity database backups are retained at
  `/opt/circuit-lab/mcp-rollout-20261004`. The reviewed receiver and this site's
  Apache MCP route additions were installed after CI passed and Apache validated.
- Public resource metadata returns 200 with the expected issuer/resource.
  MCP without a bearer, including a forged actor header, returns a native 401
  with a resource-metadata challenge, not an HTML login redirect.
- The reviewed `circuit-lab-codex` and `circuit-lab-mcp-resource` entries, scopes,
  audiences, browser basic scope and read-only role/scope mappings are installed.
  Actual resource credentials can read users and lifecycle events. Existing
  browser-client settings, registration, password policy and SMTP were preserved.
- A new `circuit-lab_application-db` volume and application-only database are
  healthy. Both migrations are applied; there are zero customer documents.
  The initial private dump was restored into `circuit_restore_20261004`, and
  restored-access invalidation/interrupted-run recovery entrypoints passed.
  This is an **empty-schema VPS restore**, not recovery of customer history;
  the populated content/grant restoration test passed separately in CI.
- `CIRCUIT_ENABLE_PROJECTS=false` remains explicit. The running API has not
  received the collaboration overlay, and `/api/projects/status` reports disabled.
  No off-host backup, retention job, Codex configuration or user OAuth sign-in
  was installed. No production volume, backup or test database was deleted.

Next: choose an encrypted off-host destination/retention policy, install and test
backup scheduling, then enable the overlay and perform real browser/Codex
save/share/edit/simulate/view/undo/revoke checks. Confirm whether Codex on this
computer is the first connection; its staged callback is
`http://127.0.0.1:8124/callback`.

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

The initial local implementation step changed no production services or Codex
settings; the subsequent authorized rollout is recorded above.

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

1. Configure and verify encrypted off-host backups, retention and monitoring.
   An initial VPS schema restore and populated CI restoration are complete; a
   scheduled off-host backup/recovery system is not.
2. Enable the collaboration overlay only after that gate, preserving separate
   identity/application stores and VPS-only secrets.
3. Verify production browser save/share/revoke and account lifecycle, then sign
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
