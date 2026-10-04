# Circuit Lab MCP: circuit collaboration and verified assistance

Date: 2026-10-04. Status: repository-grounded design, not implemented.
Baseline: local main `13e481e`; observation/AC is committed but not pushed.

## 1. Confirmed requirements and decisions still needed

Chris wants a comprehensive interface through which a user's own AI can get,
understand, modify and simulate their circuit. The following decisions were
explicitly confirmed in this conversation:

1. Support saved projects and the circuit currently open in the browser.
2. Browser circuits are shared explicitly, not silently uploaded or discoverable.
3. The AI may edit directly; provide visible history and reliable undo rather
   than requiring acceptance of every ordinary circuit edit.

Remaining implementation choices: which external AI clients to verify first,
and approval of new dependencies. Initially suggested Psycopg, but its LGPL
license conflicts with the house permissive-license preference; recommend
`asyncpg` instead. No package has been added. Do not infer approval of a revised
dependency from approval of a different package.

The proposed first version covers the existing ideal analog schematic editor
and its real transient/AC engine. Curated recipes are also discoverable and
simulatable; unsupported devices do not become available just because an AI asks.
This is bring-your-own-AI, not an embedded paid LLM service. The model runs in
the user's chosen client; Circuit Lab exposes validated actions and evidence.

## 2. What exists, and the architectural gap

Source inspection at the baseline establishes:

1. `frontend/src/schematic-files.ts` persists an account-scoped localStorage
   draft and imports/exports a bounded circuit JSON envelope. The backend has
   no saved-project database. A remote AI cannot see that browser memory.
2. `backend/schematic_models.py` bounds R/C/L, DC/pulse/sine and ground,
   component IDs, positions, terminals and timing. `schematic_topology.py`
   derives electrical nodes from explicit connections, not wire crossings.
3. `/api/schematic/simulate` and `/api/schematic/ac` already validate numeric
   input and invoke the isolated worker. Recipes have a separate bounded API.
4. Hosted identity currently comes from OAuth2 Proxy's trusted headers behind
   Apache. An MCP client cannot substitute arbitrary identity headers or rely
   on a browser's login cookie. There is no MCP bearer-token boundary yet.
5. Audit events cover simulations; browser edit history is not durable undo.
   Account export currently returns no saved projects. Keycloak's database is
   for identity, not circuit storage.

Therefore project persistence, revisions/undo and delegated authorization are
foundations of this interface, not optional wrappers around the existing routes.

## 3. One service layer, two front doors

The browser REST API and MCP adapter call the same application services:
principal/permission checks -> project/revision service -> validation or
measurement service -> existing isolated simulation gateway.

MCP-specific code only handles protocol schemas, authentication context and
response formatting. It does not maintain a second circuit model, duplicate
solver implementation, or call browser-cookie routes as an impersonated user.

Proposed remote endpoint: `https://circuit-lab.christopherrehm.de/mcp` using
Streamable HTTP. This address is a proposal, not a deployed endpoint.
Use the official Python SDK and negotiate supported protocol versions; start
from the published 2025-11-25 protocol contract, not an unpinned evolving draft.
Test initialize, discovery, tools, resources and prompts using a real SDK client.
Optional local stdio adapter may follow; remote HTTP is the first delivery.

Apache must route `/mcp` and OAuth metadata before its static-site handling.
MCP requests must not redirect into browser login HTML. Preserve existing
browser/proxy defenses; give MCP its own validated bearer boundary. Accept only
explicit configured Origins when an Origin is supplied; absence is allowed for
authenticated native clients. Apply independent bounded protocol/graph limits.

## 4. Persistent projects and explicitly shared live workspaces

Create a separate application PostgreSQL database/role and volume. Never use
Keycloak tables or identity administrator credentials for circuit storage.
Proposed entities:

| Entity | Responsibility |
| --- | --- |
| Project | Owner, bounded name, current saved revision, timestamps |
| Revision | Immutable graph/settings snapshot, parent, reason, author, hashes |
| Workspace | Explicit browser-tab identity, project/base revision, current revision |
| Connection grant | Authorized principal/client, project/workspace allow-list, scopes, expiry/revocation |
| Simulation run | Immutable target revision, analysis/settings, status, engine/build provenance |
| Run samples/checks | Bounded actual solver output and deterministic measurements |
| Action event | Append-only owner + client attribution, change summary and correlation ID |

Persist incomplete editor graphs too: construction validity is distinct from
simulation readiness. Validate known fields, finite values, IDs, pins and bounds
on saves; missing ground or disconnected terminals produce diagnostics rather
than preventing a user or AI from assembling a circuit incrementally.

Saved projects are private by default. AI connection alone does not grant access
to every project. The user selects project and/or workspace grants in the app.
Sharing the current draft first creates a recoverable snapshot and binds the
grant to that workspace, not to an ambiguous global "current circuit".

Browser UX: Save project, Share with my AI, connection status, sync status,
Stop sharing, change history and Undo. Explain that shared graphs/results can
be received by the user's external AI provider; revoking access cannot erase
content already received by that provider.

While sharing, synchronize acknowledged revisions. Report local unsent edits,
offline status and the last server revision explicitly. An AI read returns
the acknowledged snapshot and freshness information, never claims unseen
browser edits are synchronized. Poll revision/version endpoints initially;
notifications can enhance this without becoming a correctness dependency.

Multiple tabs get independent workspace IDs. Do not infer the active tab from
the most recently polled one. Both the UI and AI select a target explicitly.
Project saves and workspace edits are distinct: live changes do not silently
replace another workspace's draft or the saved project's head.

## 5. Direct editing, transactions and undo

Every mutation includes target, expected revision, bounded reason and an
idempotency key. Owner/client identity comes exclusively from authorization.
Typed edit operations include add/update/move/rotate/remove component,
connect/disconnect terminals, timing and excitation/sweep settings.

Apply an operation batch atomically, validate the resulting editor graph,
append a new revision/action event and update the head with compare-and-swap in
one transaction. Never partially apply a batch. A revision conflict returns
the new head and instructs the client to reread; do not silently merge electrical
changes or retry them against different inputs.

Store idempotency by principal, grant and target, with a request hash. Same key
and same request returns the original result; changed request returns conflict.
Failed authorization/validation consumes no project revision or worker slot.

Component removal reports and retains the removed component plus all affected
wires in revision history. These ordinary reversible edits are covered by the
direct-edit grant. Project/account deletion, permissions, billing, hardware I/O
and model verification are not AI editing tools.

Undo creates a new revision containing the previous snapshot; it does not
delete history. Default undo targets only the latest acknowledged change and
requires the current head, so it cannot erase intervening human edits unnoticed.
Explicit restore of an older revision shows a diff and uses the same conflict
checks. Both AI and human edits appear with before/after revision IDs and a
human-readable summary; UI Undo remains available without an AI connection.

Electrical graph/settings edits invalidate affected displayed reports. Layout
edits preserve validity only when the appropriate electrical/settings hashes
match. Historical runs remain readable but are clearly labeled historical.

## 6. Proposed tool catalog

These names describe the planned public contract; none is available yet.
Schemas have bounded input/output objects, physical units and explicit errors.

| Group | Tools | Purpose |
| --- | --- | --- |
| Orientation | `get_app_guide`, `get_capabilities` | Exact supported actions, limits, units/signs, model limitations and workflows |
| Parts/examples | `list_components`, `get_component`, `list_examples`, `get_example` | Supported kinds, pins, standard values, ranges and ideal-model provenance |
| Projects | `list_projects`, `get_project`, `create_project`, `copy_project` | Authorized private designs; creation is within explicit connection scope |
| Live state | `list_shared_workspaces`, `get_workspace` | Only explicitly granted workspace snapshots and sync freshness |
| Circuit inspection | `get_circuit`, `inspect_connectivity`, `validate_circuit` | Graph, positions, terminal-to-net mapping, diagnostics and run readiness |
| Circuit editing | `apply_circuit_edits`, `replace_circuit` | Bounded typed atomic edits or validated full replacement with a diff |
| History | `list_revisions`, `compare_revisions`, `undo_last_change`, `restore_revision` | Version evidence and non-destructive restoration |
| Simulation | `simulate_transient`, `simulate_ac`, `get_simulation` | Real runs of an explicit immutable revision/settings snapshot |
| Evidence | `read_samples`, `measure_signals`, `compare_simulations`, `evaluate_checks` | Selected waveforms, numerical measurements and intent-check evidence |
| Browser view | `set_observation_view` | Highlight authorized pins/parts, select probes or seek time/frequency without changing the graph |
| Export | `export_circuit`, `export_simulation` | Versioned structured graph, generated netlist and bounded numerical output |

Avoid dozens of one-property tool wrappers. `apply_circuit_edits` uses a
discriminated operation list; an AI can place/wire a whole small circuit as
one understandable undoable action. `replace_circuit` returns the same complete
diff and is not an unbounded import escape hatch.

`set_observation_view` targets a currently shared workspace and report revision;
the browser acknowledges applied commands. Without a live browser it reports
not delivered rather than claiming it changed the screen. It cannot execute
JavaScript, open external URLs or read other tabs. Never auto-start playback.

Use honest MCP read-only/destructive/idempotency annotations as client guidance;
annotations are not authorization. Simulation writes a run and consumes budget,
so it is not described as read-only. Enforce every permission server-side.

## 7. Evidence and numerical contract

All reads and run outputs identify project/workspace, immutable revision,
graph/settings hashes and a correlation ID. Runs include analysis, simulation
engine/build identity, excitation/DC bias, units, warnings and model provenance.
Don't accept an AI-provided netlist, expression evaluator or shell command.

Use stable component/pin references for queries. Solver-generated node names
are revision-local; return pin-to-net mappings and reject stale references.
Current direction is terminal 0 -> 1; voltage drop is V0 - V1. No fabricated
ideal-wire segment currents or physical electron speeds.

Default responses are compact summaries with authorized resource links, not
all sample vectors. `read_samples` requests explicit signals, time/frequency
window and pagination. Plot decimation is labeled and never used for statistics
or checks. Full bounded solver samples remain retrievable for export.

Server-side measurement services mirror the existing tested browser semantics:
window mean, total and AC-only RMS, peak-to-peak, current/voltage extrema,
qualified settled sine phase, AC amplitude/gain/dB/phase. Cross-language golden
fixtures prevent browser and MCP disagreeing. Insufficient sampling/settling or
undefined zero-amplitude phase returns unavailable with a reason, not zero.

Intent checks are bounded declarative predicates over named signals and
windows, with unit-compatible numeric thresholds and pass/fail/unavailable.
No Python, JavaScript, SPICE or arbitrary formulas. Return the actual measured
value, evaluated threshold, supporting run and method, not an LLM's verdict.
Simple cross-run comparisons require compatible quantities/settings or state
the mismatch. Bounded parameter experiments may be built on these operations;
unbounded optimization/Monte Carlo is outside this first version.

Generic ideal simulation is not a datasheet rating check or hardware approval.
Separate numeric solver bounds (currently up to +/-100 V) from the product's
low-voltage maker safety policy. The AI cannot claim a design is safe to connect
to a Raspberry Pi 3B/4B based solely on these runs. No GPIO/hardware control,
mains design, manufacturer certification or writeable model-verification tool.

## 8. Resources and app-guide prompts

Provide authenticated resource templates for a project revision, shared
workspace, component, run summary and bounded run trace. The same access checks
apply to tools, resources, exports and subscriptions; guessed IDs/URIs confer
no access. Never expose a private result as an unauthenticated public URL.

Provide `get_started`, `explain_circuit`, `debug_circuit` and `improve_circuit`
MCP prompts with exact tool sequences and grounding rules. `get_app_guide`
offers the same instructions as a tool for clients that don't discover prompts.

Teach the AI: read capabilities -> obtain the user's specific shared target ->
read its revision -> validate -> inspect/run -> explain from measurements ->
edit within the delegated grant -> rerun -> compare -> report changes and undo.
Example: change the RC filter's R1 from 1 kOhm to an allowed standard value,
simulate both revisions, report the observed response change and point the
user to the new grid revision and Undo. No invented simulation success.

Project names, descriptions and imported content are untrusted data, never
instructions that can broaden scopes or override this guide. MCP cannot make
an arbitrary AI reliable; server-enforced permissions, validation and limits
are the guarantees. Helpful prompts are guidance, not a security boundary.

## 9. Identity, sharing and account lifecycle

For normal user onboarding, use the existing self-hosted Keycloak identity
with dedicated MCP OAuth client/resource configuration, PKCE, consent and
protected-resource metadata. Validate issuer, resource audience, expiry,
account validity and required scopes on every operation. Preserve the browser
client configuration. Don't pass browser access tokens through to unrelated
services or accept client-provided owner/actor headers.

Account-level scopes (read, edit, simulate, view) are intersected with explicit
project/workspace grants. Direct-edit permission doesn't imply access to all
account content. Client-reported model names are unverified metadata; record
the authenticated owner, verified client/grant ID and optional declared model
separately, never manufacture an authenticated model identity.

Client registration/discovery must be tested against the chosen clients.
Start with reviewed registrations where supported; dynamic registration needs
its own bounded policy and redirect protections, not an unrestricted switch.
For clients supporting manual headers, optionally offer narrowly scoped,
expiring, revocable personal connection tokens stored only as digests. No
password-grant shortcut or instruction to paste a token into a chat. OAuth
support and header-token support are distinct compatibility claims.

Stopping a grant blocks subsequent reads, edits, simulation admission, queued
browser view commands and resource subscriptions. Check before committing edits
and releasing results, not only during MCP initialization. Revocation cannot
withdraw information already delivered. Account password change/deletion must
invalidate application connection tokens and grants as well as browser access.

Extend self-service export to projects, revisions, grants metadata, runs and
dual-attributed actions, never credential material. Integrate native Keycloak
account deletion through a reliable idempotent lifecycle event/reconciliation
path; delete owned graphs/reports and revoke connections. Until propagation is
complete, deny that account access. Test user deletion end to end, not merely
the presence of a delete button. Retention/PII handling for minimal audit events
and backup expiry need a documented policy before commercial launch.

## 10. Limits, isolation and commercial foundations

Retain current graph/frame/sweep bounds and the shared two-worker-job ceiling
across browser, recipes and MCP. Add fair per-account/client admission and
rate/storage quotas; a looped AI must not starve other users or fill disk.
Bound edit batches, protocol payloads, list pages, returned samples, reasons,
workspace/view-command lifetime and retry/experiment budgets. Concrete quota
defaults belong in tested configuration, not model-written instructions.

Use durable run records with bounded retention and explicit queued/running/
completed/failed/cancelled states. Recover interrupted jobs honestly on restart.
No endless queue; return typed busy/quota errors. Long work returns a run ID
and is fetched via `get_simulation`, so broad client compatibility doesn't
depend on optional MCP task support or a permanent SSE connection.

Keep simulation in the nonroot/read-only/no-network worker. MCP has no shell,
filesystem browsing, package installer, arbitrary web fetch or identity-admin
tools. Database/MCP failures should not prevent offline drafts/export or take
down unrelated catalog/health features; write failures must not become silent
success. Revision write and immutable audit insertion must commit together.

Back up only the new application database with reviewed credentials and verify
restoration before claiming persistence is dependable. Version migrations,
test the real engine from the first migration, and use expand/contract changes
compatible with immutable release rollback. Never overwrite existing identity
realms/volumes during application deployment. No VPS mutation in this design.

## 11. Build order and acceptance gates

1. Shared domain contracts and PostgreSQL migrations/repositories; private
   projects, incomplete graphs, immutable revisions, atomic edits and UI undo.
2. Shared workspaces/synchronization, explicit grants, conflict/offline states,
   browser acknowledgement and live grid/change-history updates.
3. Delegated authentication and MCP HTTP adapter; scoped tools, resources,
   prompts, connection settings/revocation and lifecycle/export integration.
4. Snapshot-bound transient/AC runs, durable evidence, deterministic measurement
   and intent checks, browser observation controls and compact exports.
5. Client-specific onboarding, all-tier tests, isolated deployment checks,
   dependency audit and backup/recovery evidence. Commit on main; wait for push.

Must-pass tests include:

1. Real PostgreSQL migrations, ownership filters, atomic revisions/audit,
   concurrent compare-and-swap, retry idempotency and restart recovery.
2. Two real accounts: guessed project/run/resource IDs, forged actor headers,
   missing scopes, wrong issuer/audience, expired/revoked tokens and deleted
   accounts cannot cross tenant boundaries. Test exports/subscriptions too.
3. Explicit sharing, two tabs, offline/unsent edits, direct AI edit visible on
   the grid, complete component+wire Undo and safe human/AI conflicts.
4. Actual SDK initialize/list/call/read/get-prompt round trips and chosen-client
   login/consent/connection. A config entry or green health check is not proof.
5. Real ngspice transient/AC, independently checked golden numerical fixtures,
   revision-specific sample reads, invalidation, unsuitable phase/statistics,
   partial/failed run honesty and malicious executable input rejection.
6. Two-slot worker capacity shared with browser/recipes, per-account fairness,
   bounded queries/queues/storage, worker crash and DB outage isolation.
7. Password-change/account-deletion revocation, own-account export and data
   cleanup; automated keyboard/mobile/contrast/axe and reduced-motion checks.
8. All preexisting tests retained, lint/strict types/build/coverage and resolved
   dependency vulnerability scans; restoration drill before hosted persistence.

## 12. Dependency proposal and references

Metadata checked directly against PyPI/GitHub on 2026-10-04:

1. `mcp` 2.3.0: official Python SDK, MIT, approximately 24,476 repository stars;
   released 2026-10-02. Use release-matched documentation, not obsolete v1 APIs.
2. `asyncpg` 0.31.0: PostgreSQL driver, Apache-2.0, approximately 8,096 stars;
   released 2025-11-24, repository active 2026-10-03. Fits the existing async API.

Recommendation: adopt both rather than hand-writing protocol or database-driver
code. The alternative is a smaller read-only/stateless adapter that requires
manual circuit upload and cannot satisfy shared live editing/undo. User approval,
resolved dependency audit, image compatibility and any additional crypto/OAuth
dependencies still require verification before adoption. These metadata checks
are not a vulnerability audit or legal opinion. No dependency changed here.

Primary references checked for this design:

1. [MCP Streamable HTTP](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports)
2. [MCP authorization](https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization)
3. [MCP tools](https://modelcontextprotocol.io/specification/2025-11-25/server/tools),
   [resources](https://modelcontextprotocol.io/specification/2025-11-25/server/resources),
   [prompts](https://modelcontextprotocol.io/specification/2025-11-25/server/prompts)
4. [Official Python SDK](https://github.com/modelcontextprotocol/python-sdk),
   [PyPI release metadata](https://pypi.org/pypi/mcp/json)
5. [asyncpg](https://github.com/MagicStack/asyncpg),
   [license](https://github.com/MagicStack/asyncpg/blob/master/LICENSE),
   [PyPI release metadata](https://pypi.org/pypi/asyncpg/json)
6. [Psycopg LGPL license](https://github.com/psycopg/psycopg/blob/master/LICENSE.txt)
7. [Keycloak OIDC endpoints](https://www.keycloak.org/securing-apps/oidc-layers)

Planning evidence only: application source inspected and upstream protocol/
dependency metadata checked. No MCP implementation, client connection, migration,
new-package audit, production change or new test pass is claimed by this document.
