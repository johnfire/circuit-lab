"""Administrator-only initialization of Circuit Lab's isolated staging identity."""

import base64
import secrets
import subprocess
import sys
from pathlib import Path

from deploy.bootstrap import create_file
from deploy.deploy_release import staging_target, target_settings
from deploy.staging_identity import configure_identity

SOURCE = Path(__file__).resolve().parents[1]
IDENTITY_ENDPOINT = 'http://127.0.0.1:8114'
MCP_CLIENT = 'circuit-lab-codex'
SMTP_SETTINGS = {
    'CIRCUIT_SMTP_HOST': 'test-mail',
    'CIRCUIT_SMTP_PORT': '1025',
    'CIRCUIT_SMTP_USER': 'circuit-lab@example.invalid',
    'CIRCUIT_SMTP_STARTTLS': 'false',
}


def write_environment(path: Path, settings: dict[str, str]) -> None:
    if not path.exists():
        create_file(path, ''.join(f'{key}={value}\n' for key, value in settings.items()), 0o600)
    if path.stat().st_mode & 0o077 or path.stat().st_uid != 0:
        raise ValueError('Staging configuration must remain root-only')


def prepare_environment() -> None:
    target = staging_target()
    target.root.mkdir(mode=0o750, exist_ok=True)
    application_password = secrets.token_urlsafe(40)
    write_environment(target.root / '.env', {
        'CIRCUIT_PUBLIC_URL': target.origin,
        'CIRCUIT_PORT': str(target.port),
        'CIRCUIT_ACCESS_MODE': 'private',
        'CIRCUIT_PROXY_TOKEN': secrets.token_urlsafe(40),
        'CIRCUIT_ENABLE_PROJECTS': 'true',
        'CIRCUIT_APPLICATION_DATABASE_PASSWORD': application_password,
        'CIRCUIT_DATABASE_URL': 'postgresql://circuit_application:' + application_password
                                + '@application-db:5432/circuit_application',
        'CIRCUIT_MCP_CLIENTS': MCP_CLIENT,
        'CIRCUIT_MCP_INTROSPECTION_SECRET': secrets.token_urlsafe(40),
    })
    application = target_settings(target)
    write_environment(target.root / '.identity.env', {
        'CIRCUIT_PUBLIC_URL': target.origin,
        'CIRCUIT_APP_NETWORK': target.project + '_default',
        'CIRCUIT_LOGIN_PORT': '8113',
        'CIRCUIT_IDENTITY_PORT': '8114',
        'CIRCUIT_PROXY_TOKEN': application['CIRCUIT_PROXY_TOKEN'],
        'CIRCUIT_IDENTITY_DATABASE_PASSWORD': secrets.token_urlsafe(40),
        'CIRCUIT_IDENTITY_ADMIN_PASSWORD': secrets.token_urlsafe(40),
        'CIRCUIT_OIDC_CLIENT_SECRET': secrets.token_urlsafe(40),
        'CIRCUIT_SESSION_SECRET': base64.urlsafe_b64encode(secrets.token_bytes(32)).decode(),
        'CIRCUIT_SMTP_PASSWORD': secrets.token_urlsafe(40),
        **SMTP_SETTINGS,
    })


def start_identity() -> None:
    target = staging_target()
    env_file = target.root / '.identity.env'
    identity = dict(line.split('=', 1) for line in env_file.read_text().splitlines())
    expected = {**SMTP_SETTINGS, 'CIRCUIT_PUBLIC_URL': target.origin,
                'CIRCUIT_APP_NETWORK': target.project + '_default', 'CIRCUIT_IDENTITY_PORT': '8114',
                'CIRCUIT_LOGIN_PORT': '8113'}
    if any(identity.get(key) != value for key, value in expected.items()):
        raise ValueError('Identity settings do not match the isolated staging stack')
    subprocess.run(['docker', 'compose', '-p', 'circuit-lab-staging-identity',
                    '--project-directory', str(SOURCE), '--env-file', str(env_file),
                    '-f', str(SOURCE / 'compose.identity.yaml'),
                    '-f', str(SOURCE / 'compose.staging-identity.yaml'),
                    'up', '-d', '--build', '--wait', '--wait-timeout', '180'],
                   check=True, timeout=600)
    application = target_settings(target)
    configure_identity(IDENTITY_ENDPOINT, target.origin, identity['CIRCUIT_IDENTITY_ADMIN_PASSWORD'],
                       application['CIRCUIT_MCP_INTROSPECTION_SECRET'], MCP_CLIENT)


if __name__ == '__main__':
    if sys.argv[1:] == ['environment']:
        prepare_environment()
    elif sys.argv[1:] == ['identity']:
        start_identity()
    else:
        raise SystemExit('Supply environment or identity')
