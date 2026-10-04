# Circuit Lab MCP activation — Codex first

This runbook describes the next **operator-reviewed** rollout. The local build
does not execute these steps on the VPS or install a Codex connection.

## Order of operations

1. Get push authorization and require all CI jobs on the exact commit to pass.
2. Inspect existing root-owned receiver, Apache vhost, `.env` and identity
   configuration. Back them up privately; never copy their secrets into Git.
3. Provision the new application database, reviewed identity entries and backup
   jobs before exposing saved-circuit access. Do not modify the Keycloak database
   directly or replace an existing realm with an import.
4. Review/apply the new Apache routes and optional release overlay. Verify the
   browser and native MCP boundaries separately, then link Codex.

## Separate application database

`compose.projects.yaml` extends `compose.yaml`. It creates `application-db` with
database/user `circuit_application` and its own persistent volume, no public port.
It must not reuse `database`, `circuit_identity`, or `identity-db`.

Add the documented variables from `production.env.example` to the protected VPS
application environment. Generate distinct URL-safe secrets for PostgreSQL and
the introspection client. The application's hosted DSN must point to
`application-db/circuit_application`; other targets fail closed.

Keep `CIRCUIT_ENABLE_PROJECTS=false` until dependencies, backup/restore and
identity configuration are verified. The updated receiver opts into the overlay
only on literal `true`. Older immutable releases without the overlay can still
be selected for application rollback; the new database is not deleted.
Run one API instance: restart recovery assumes no other API owns active jobs.

## Reviewed identity configuration

Generate a nonsecret configuration manifest:

```sh
uv run python -m deploy.mcp_identity_configuration \
  https://circuit-lab.christopherrehm.de \
  http://127.0.0.1:8124/callback circuit-lab-codex
```

The output is an **additions manifest**, not a realm replacement/import file.
Apply the new client scopes and clients using the admin API or private console:

- Public `circuit-lab-codex`: authorization code, S256 PKCE, exact callback,
  consent, basic/profile/email plus `circuit:read/edit/simulate/view` scopes.
  Disable password grants and service accounts; do not permit wildcard redirects.
- Two separate audience mappers: MCP resource URI
  `https://circuit-lab.christopherrehm.de/mcp`, and confidential client ID
  `circuit-lab-mcp-resource`. A single Keycloak mapper configured with both
  audience fields does not supply both audiences in the tested version.
- Confidential `circuit-lab-mcp-resource`: unique VPS-only secret, no interactive
  or password login. Its service account receives only realm-management
  `view-users` and `view-events`. Assign the same two roles to the client's role
  scope mappings; keep full scope disabled. Never grant realm-admin/manage-users.
- Existing `circuit-lab-web`: **add**, without replacing existing mappers/scopes,
  the introspection-client audience mapper and `basic` scope. This permits fresh
  browser tokens to supply the verified subject and be introspected. It does not
  grant the browser client MCP access; approved-client checks still apply.
- Retain enabled user/admin events with admin event details disabled. Preserve
  SMTP, registration, verification, recovery, opt-in 2FA and deletion settings.

Sign out and sign back in after modifying token mappers. Check discovery's exact
issuer and PKCE support. The verifier never enables Keycloak's backwards
compatibility option that bypasses introspection audience validation.

The local real-Keycloak check verifies active subject/scopes, both resource
audiences, mounted HTTP bearer acceptance, password event visibility with these
read-only roles, and logged-out token rejection. It uses a synthetic password
grant **only for test fixtures**; it does not verify Codex's complete OAuth UI.

## Proxy and API checks

Apply the reviewed changes to the active vhost; merely deploying a new template
does not update a root-owned Apache configuration or receiver automatically.

- `/mcp` and `/.well-known/oauth-protected-resource/mcp` go directly to the
  loopback API, not through the browser login redirect.
- Existing browser `/api/`, assets and workbench stay behind the login proxy.
- Strip incoming identity headers. MCP uses its own verified bearer, never a
  forged browser actor or gateway secret.
- MCP body budget: 64 KiB; browser projects: 16 KiB; existing simulation: 8 KiB.
- Verify metadata 200 with the expected issuer/resource; unauthenticated MCP
  returns 401 and a resource-metadata challenge, not HTML or a 302.
- Verify no-bearer and wrong-audience/client tokens cannot read a shared circuit;
  cross-account UUIDs, revoked grants and old password tokens must be denied.

Application liveness is independent of collaboration readiness. Require
`/api/projects/status` to report enabled after a real browser sign-in. Database
or lifecycle outages must leave the local editor available while denying saved
project access. Never interpret `/api/health` alone as MCP readiness.

## Backups and restoration

Configure encrypted off-host application backups and an explicit retention
policy before relying on saved projects. Back up application and identity stores
separately. No automatic retention/delete job is installed by this commit.

Restore a dump into a **new, explicitly named application test database**, not
over identity or the live database. Verify immutable heads, history, content
hashes, reports and owner isolation. CI performs an actual pg_dump/psql restoration
and reads restored circuit contents through the repository services.

Before bringing a disaster-restored application store online, invoke the
operator-only `backend.project_recovery.invalidate_restored_access` service on
that restored store and run interrupted-job recovery. It revokes all restored
grants, invalidates pre-restoration account tokens and records recovery audit
events. Require fresh sign-in and explicit re-sharing. Old backups must not
resurrect grants revoked after their creation. Keep the original volume and dump
until restored operation has been verified; do not automatically delete either.

Production restore, backup scheduling, monitoring, retention and capacity are
still rollout gates. A successful synthetic restoration is not proof of a VPS
backup schedule or disaster-recovery readiness.

## Connect Codex after activation

`codex-mcp.toml.example` supplies an uninstalled connection recipe. Review the
exact callback/client ID against the configured Keycloak entry before adding it
to Codex's MCP settings. No bearer or secret belongs in that TOML or in a chat.
The loopback recipe is for Codex running on this computer; other host surfaces
may need a different exact callback, reviewed as a separate client.

Complete the OAuth sign-in, then on the grid explicitly choose
`circuit-lab-codex` and click **Share this grid with my AI** or **Share saved
project**. The connection alone does not share any project. Ask Codex to list
shared targets and confirm the intended workspace ID before editing.

Smoke-test: read → validate → resistor edit → simulate the returned revision →
read measurements → show a paused cursor/probes → confirm acknowledgement →
undo → stop sharing → confirm the next read is rejected. Repeat after logout,
password change and deletion. Verify conflict handling with unsent local edits.

Sharing permits the external AI provider to receive circuit/results. Revocation
blocks further access but cannot retract information already sent to that provider.

## Documentation checked

- [Codex MCP configuration](https://learn.chatgpt.com/docs/config-file/config-reference)
  defines predefined client ID, resource, scopes and callback/listener settings.
- [OpenAI MCP authentication](https://developers.openai.com/plugins/build/auth)
  describes protected-resource discovery, PKCE, exact issuer/callback validation
  and resource-audience checks.
- [Keycloak 26.8 upgrade guidance](https://www.keycloak.org/docs/26.8.0/upgrading/)
  documents the introspection-client audience check and least-privilege role
  scope mapping requirements.
