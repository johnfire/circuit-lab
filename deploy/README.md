# Deployment runbook

The public hostname is circuit-lab.christopherrehm.de. Apache is the actual VPS
front door; nginx is inactive. Only Circuit Lab's virtual hosts are changed.
TLS uses a dedicated Let's Encrypt certificate, webroot renewal, and a
site-specific Apache reload hook. Existing certificates remain untouched.

## Application releases

Pushes to main run lint, strict types, Python unit/integration tests (70% minimum
coverage), browser/mobile/accessibility regressions, dependency vulnerability
audits, and real simulations of all nine recipes in restricted containers.
After these checks pass, GitHub sends the exact Git archive to the restricted
VPS receiver. It builds the API and worker once and deploys them to private
staging. GitHub runs the live browser gate, then promotes those same image IDs
to production. The receiver rejects promotion if staging is running a different
revision or its image IDs have changed.
Dependabot auto-PRs are intentionally not configured because this project uses
main-only development; dependency audits are mandatory on every push.

The dedicated circuit-deploy account has a locked password and a restricted
public key. It cannot run arbitrary SSH commands or forwarding. Its sole sudo
capability is the root-owned release receiver. Repository main write access is
deployment authority: trusted source builds necessarily execute on the host.
The deploy key must not be reused for another repository.

GitHub secrets DEPLOY_SSH_KEY and DEPLOY_HOST_KEY contain the dedicated key and
the already-verified VPS host key. The production GitHub environment also
holds STAGING_TLS_CERT and STAGING_TLS_KEY for a staging-only client identity.
Application, identity, and SMTP credentials stay on the VPS.
/opt/circuit-lab/.env is root-only; do not print it or run compose config in logs.

Releases are retained under /opt/circuit-lab/releases/FULL_SHA. The current and
previous symlinks identify verified revisions. Images are tagged with the full
revision. Every deployment validates /api/health's build_id and runs a real
simulation with AI-agent attribution. Service failures restore the previous
verified release. A first-ever failed release stops only these new services.
No release contents, audit volumes, or old images are deleted automatically.

For manual rollback, on the VPS resolve /opt/circuit-lab/previous, then use its
compose.yaml and its revision as CIRCUIT_IMAGE_TAG with project circuit-lab and
--env-file /opt/circuit-lab/.env. Run up -d --wait, verify health plus simulation,
and update current only after success. Do not delete identity/database volumes.

## Private staging and agent tests

Staging runs at https://staging.circuit-lab.christopherrehm.de on the same VPS.
Apache requires a staging client certificate on every HTTPS route. The API,
OAuth2 Proxy and Keycloak bind to loopback ports 8112, 8113 and 8114.
The application database, Keycloak database, worker socket and audit log
belong to separate staging Compose projects and Docker volumes. Keycloak
delivers only to the staging Mailpit instance on loopback port 8056. Its
search and message endpoints are available through the certificate gate.

To bootstrap on a new VPS, point the staging DNS record at the VPS and install
the staging HTTP vhost. Issue the public certificate with the Apache webroot,
then install the staging HTTPS vhost and a dedicated staging client CA.
Issue separate client certificates to CI and authorized agents. Keep the CA
private key off the VPS. Install the root-owned receiver and forced command
from `deploy_release.py` and `ssh_gateway.py` after validating and backing up
any existing receiver.

Run `sudo python3 -m deploy.prepare_staging environment` from the repository
on the VPS to create staging credentials. Send the initial release archive to
the receiver with `stage FULL_SHA` to create the application network, then
run `sudo python3 -m deploy.prepare_staging identity` from the extracted staging
release. This starts staging Keycloak, OAuth2 Proxy, and Mailpit and configures
the staged OAuth clients and lifecycle roles. Identity administration follows
the existing separate release process.

Agents with certificates in `~/.local/share/circuit-lab/staging-tls/` can run
the same browser gate with the following command. Use `agent.pem` and
`agent.key`, or override their paths with `STAGING_TLS_CERT_PATH` and
`STAGING_TLS_KEY_PATH`.

```bash
npm run test:staging --prefix frontend
```

The gate registers a synthetic account, verifies email through Mailpit,
runs a real ngspice simulation, saves a private circuit and checks the account
export. CI also checks the running revision against the commit being promoted.

## Isolation and model boundaries

The API is published only on 127.0.0.1:8102. The worker has no network,
no privileges or capabilities, a read-only root filesystem, bounded writable
temporary storage, CPU/memory/process ceilings, and two concurrent job slots.
Only curated recipe IDs and bounded numerical overrides cross its Unix socket.
The API never falls back to local execution if the worker fails.

ngspice 47 is built headless with XSPICE from a SHA-256-pinned official source
tarball. Debian ngspice 39.3 returns failure exit codes for these control-script
recipes, so it is deliberately not used. Failures are not ignored.

## Public landing and account service

Apache serves only landing.html, landing.css, theme.css, favicon.svg, and
landing-analytics.js publicly. The workbench, API,
and application assets pass through OAuth2 Proxy, which replaces incoming
identity headers. Keycloak provides open registration, required email
verification, password reset, account management, optional TOTP, and confirmed
account deletion. The application export checks that the token subject matches
the authenticated account and includes only that account's simulation events.

The identity service is a separate Compose project, circuit-lab-identity, with
its own PostgreSQL volume. This is a single-instance deployment using local
cache; a multi-node setup needs shared cache and a separate scaling review.
Keep /opt/circuit-lab/.identity.env root-only. prepare_identity.py verifies the
authorized existing SMTP credentials and writes this file without printing
them. Only loopback ports 8103/8104 are exposed; Apache denies public access to
the master realm and admin API.

Realm import runs only when the realm does not already exist. App delivery must
not replace customer identity state. Future realm updates require an explicit
database backup and a reviewed migration, not an overwrite import.
Daily database and audit-log backups run on the VPS (`deploy/backup/`, timer
`circuit-lab-backup.timer`), on-host for now; an off-host copy is still required.
Signup abuse controls, legal pages, and recovery drills are required before
commercial launch. No billing or subscriptions are enabled. Saved projects
and MCP collaboration were switched on 2026-10-22 (`CIRCUIT_ENABLE_PROJECTS=true`);
see `MCP.md` and `docs/mcp-implementation-status.md` for the exact state.

To pause delivery, disable the GitHub workflow/deployment environment. To revoke
the deploy capability, remove its one public key or lock the dedicated account's
SSH access; don't change shared VPS user keys. To hide the website, disable only
circuit-lab and circuit-lab-ssl sites, validate Apache, and reload gracefully.
Stop only the circuit-lab Compose project; preserve its volumes for recovery.

## Landing-page analytics

The existing self-hosted Umami at stats.christopherrehm.de owns website
c85d3632-ce92-4753-9505-5be8c9ca13c4 (Circuit Lab). Only the public landing
page loads its deferred tracker. Local/staging hosts are excluded, Do Not Track
is respected, and query strings/fragments are excluded. The before-send policy
accepts only anonymous landing pageviews, canonicalizes them to /, strips
referrer paths, and allowlists fields rather than forwarding arbitrary payloads.
No account identifiers, custom events, performance tracking, or session replay
are enabled. Blocking or losing Umami must not affect signup or the workbench.

The landing CSP permits only the exact Umami script and collector endpoints,
without inline JavaScript or wildcards. The root-owned receiver and this site's
Apache configuration require a verified, backed-up bootstrap update before
CI deploys these assets; the application release itself remains CI-only.
The existing VPS Umami retention job is configured for 90 days. Its effective
execution is a separate operational check, not a compliance guarantee.

View visits at https://stats.christopherrehm.de/websites/c85d3632-ce92-4753-9505-5be8c9ca13c4.
Counts start after deployment and can be reduced by DNT settings or blockers.
