# Deployment runbook

The public hostname is circuit-lab.christopherrehm.de. Apache is the actual VPS
front door; nginx is inactive. Only Circuit Lab's virtual hosts are changed.
TLS uses a dedicated Let's Encrypt certificate, webroot renewal, and a
site-specific Apache reload hook. Existing certificates remain untouched.

## Application releases

Pushes to main run lint, strict types, Python unit/integration tests (70% minimum
coverage), browser/mobile/accessibility regressions, dependency vulnerability
audits, and real simulations of all nine recipes in restricted containers.
Only after these checks pass does GitHub send the exact Git archive to the VPS.
Dependabot auto-PRs are intentionally not configured because this project uses
main-only development; dependency audits are mandatory on every push.

The dedicated circuit-deploy account has a locked password and a restricted
public key. It cannot run arbitrary SSH commands or forwarding. Its sole sudo
capability is the root-owned release receiver. Repository main write access is
deployment authority: trusted source builds necessarily execute on the host.
The deploy key must not be reused for another repository.

GitHub secrets DEPLOY_SSH_KEY and DEPLOY_HOST_KEY contain the dedicated key and
the already-verified VPS host key. No app or email secrets enter GitHub.
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

## Isolation and model boundaries

The API is published only on 127.0.0.1:8102. The worker has no network,
no privileges or capabilities, a read-only root filesystem, bounded writable
temporary storage, CPU/memory/process ceilings, and two concurrent job slots.
Only curated recipe IDs and bounded numerical overrides cross its Unix socket.
The API never falls back to local execution if the worker fails.

ngspice 47 is built headless with XSPICE from a SHA-256-pinned official source
tarball. Debian ngspice 39.3 returns failure exit codes for these control-script
recipes, so it is deliberately not used. Failures are not ignored.

## Authentication rollout

An empty-password-file Basic gateway keeps staging locked until the separate
commercialization-oriented identity service is verified. It is not a customer
account system. The agreed target is self-hosted open registration with verified
email, password reset, account management, optional 2FA, and deletion/export.
Identity configuration and database state must not be overwritten by each app
release. No billing, subscription enforcement, or AI design loop exists yet.

To pause delivery, disable the GitHub workflow/deployment environment. To revoke
the deploy capability, remove its one public key or lock the dedicated account's
SSH access; don't change shared VPS user keys. To hide the website, disable only
circuit-lab and circuit-lab-ssl sites, validate Apache, and reload gracefully.
Stop only the circuit-lab Compose project; preserve its volumes for recovery.
