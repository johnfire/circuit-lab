"""Create VPS-only identity credentials and reuse the authorized outgoing SMTP."""

import base64
import json
import os
import secrets
import smtplib
import ssl
import subprocess
import sys
from pathlib import Path


def active_smtp_settings() -> dict[str, str]:
    """Read the active app's environment without displaying any values."""
    inspected = subprocess.run(
        ['docker', 'inspect', 'notes-world-app-app-1', '--format', '{{json .Config.Env}}'],
        capture_output=True, text=True, check=True)
    environment = dict(entry.split('=', 1) for entry in json.loads(inspected.stdout))
    required = ['MAIL_HOST', 'MAIL_USER', 'MAIL_PASS']
    if not all(environment.get(name) for name in required):
        raise ValueError('Authorized SMTP source is missing required settings')
    with smtplib.SMTP(environment['MAIL_HOST'], int(environment.get('MAIL_PORT') or 587),
                      timeout=15) as connection:
        connection.starttls(context=ssl.create_default_context())
        connection.login(environment['MAIL_USER'], environment['MAIL_PASS'])
    return environment


def quote_environment(value: str) -> str:
    """Preserve secrets literally in Compose env files, including dollar signs."""
    if '\n' in value or '\r' in value:
        raise ValueError('Multiline credentials are unsupported')
    return "'" + value.replace('\\', '\\\\').replace("'", "\\'") + "'"


def migrate_gateway_setting(root: Path) -> None:
    """Add the explicit gateway setting without rotating existing identity secrets."""
    target = root / '.identity.env'
    if target.stat().st_mode & 0o077:
        raise ValueError('Identity settings must remain root-only')
    if any(line.startswith('CIRCUIT_PROXY_TOKEN=') for line in target.read_text().splitlines()):
        return
    application = dict(line.split('=', 1) for line in (root / '.env').read_text().splitlines()
                       if line and not line.startswith('#'))
    with target.open('a') as destination:
        destination.write('CIRCUIT_PROXY_TOKEN='
                          + quote_environment(application['CIRCUIT_PROXY_TOKEN']) + '\n')
    print('Gateway setting migrated; existing identity credentials preserved')


def main() -> None:
    """Create an exclusive protected file; existing identity secrets are immutable."""
    root = Path('/opt/circuit-lab')
    if sys.argv[1:] == ['--migrate-gateway']:
        migrate_gateway_setting(root)
        return
    target = root / '.identity.env'
    if target.exists():
        raise ValueError('Identity configuration already exists; inspect before changing it')
    smtp = active_smtp_settings()
    application = dict(line.split('=', 1) for line in (root / '.env').read_text().splitlines()
                       if line and not line.startswith('#'))
    settings = {
        'CIRCUIT_PUBLIC_URL': application['CIRCUIT_PUBLIC_URL'],
        'CIRCUIT_IDENTITY_DATABASE_PASSWORD': secrets.token_urlsafe(40),
        'CIRCUIT_IDENTITY_ADMIN_PASSWORD': secrets.token_urlsafe(40),
        'CIRCUIT_OIDC_CLIENT_SECRET': secrets.token_urlsafe(40),
        'CIRCUIT_SESSION_SECRET': base64.urlsafe_b64encode(secrets.token_bytes(32)).decode(),
        'CIRCUIT_PROXY_TOKEN': application['CIRCUIT_PROXY_TOKEN'],
        'CIRCUIT_SMTP_HOST': smtp['MAIL_HOST'],
        'CIRCUIT_SMTP_PORT': smtp.get('MAIL_PORT') or '587',
        'CIRCUIT_SMTP_USER': smtp['MAIL_USER'],
        'CIRCUIT_SMTP_PASSWORD': smtp['MAIL_PASS'],
    }
    descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'w') as destination:
        destination.write(''.join(name + '=' + quote_environment(value) + '\n'
                                  for name, value in settings.items()))
    print('SMTP authentication verified; identity settings saved privately on VPS')


if __name__ == '__main__':
    main()
