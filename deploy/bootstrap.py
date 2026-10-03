"""Explicit administrator bootstrap; never called by the CI deploy key."""

import grp
import os
import secrets
import shutil
import subprocess
from pathlib import Path

SOURCE = Path(__file__).resolve().parent
ROOT = Path('/opt/circuit-lab')


def create_file(path: Path, content: str, mode: int) -> None:
    """Create protected configuration only when its target does not exist."""
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(descriptor, 'w') as target:
        target.write(content)


def configure_receiver() -> None:
    """Give a new locked account one forced, fixed-scope deployment capability."""
    if subprocess.run(['id', 'circuit-deploy'], capture_output=True).returncode == 0:
        raise ValueError('Deploy account already exists; inspect before changing it')
    subprocess.run(['useradd', '--create-home', '--shell', '/bin/sh', 'circuit-deploy'], check=True)
    subprocess.run(['passwd', '--lock', 'circuit-deploy'], check=True)
    for source, target in [('deploy_release.py', '/usr/local/sbin/circuit-lab-deploy'),
                           ('ssh_gateway.py', '/usr/local/bin/circuit-lab-ssh')]:
        shutil.copyfile(SOURCE / source, target)
        os.chmod(target, 0o755)
    ssh_directory = Path('/home/circuit-deploy/.ssh')
    ssh_directory.mkdir(mode=0o700)
    key = (SOURCE / 'deploy-key.pub').read_text().strip()
    if not key.startswith('ssh-ed25519 ') or '\n' in key:
        raise ValueError('Expected one dedicated Ed25519 public key')
    create_file(ssh_directory / 'authorized_keys',
                'restrict,command="/usr/local/bin/circuit-lab-ssh" ' + key + '\n', 0o600)
    shutil.chown(ssh_directory, user='circuit-deploy', group='circuit-deploy')
    shutil.chown(ssh_directory / 'authorized_keys', user='circuit-deploy', group='circuit-deploy')
    rule = Path('/etc/sudoers.d/circuit-lab-deploy')
    create_file(rule, 'circuit-deploy ALL=(root) NOPASSWD: /usr/local/sbin/circuit-lab-deploy *\n', 0o440)
    subprocess.run(['visudo', '-cf', str(rule)], check=True)


def configure_private_site(token: str) -> None:
    """Stage a locked HTTPS gate; login provisioning remains a human action."""
    password_file = Path('/etc/apache2/circuit-lab.htpasswd')
    create_file(password_file, '', 0o640)
    os.chown(password_file, 0, grp.getgrnam('www-data').gr_gid)
    template = (SOURCE / 'apache-https.conf.template').read_text()
    create_file(Path('/etc/apache2/sites-available/circuit-lab-ssl.conf'),
                template.replace('__PROXY_TOKEN__', token), 0o640)
    shutil.copyfile(SOURCE / 'apache-http.conf',
                    '/etc/apache2/sites-available/circuit-lab.conf')


def main() -> None:
    """Create only Circuit Lab resources, then validate before reloading Apache."""
    if ROOT.exists():
        raise ValueError('Circuit Lab directory already exists; inspect before bootstrapping')
    ROOT.mkdir(mode=0o750)
    (ROOT / 'releases').mkdir(mode=0o750)
    token = secrets.token_urlsafe(48)
    create_file(ROOT / '.env', 'CIRCUIT_PUBLIC_URL=https://circuit-lab.christopherrehm.de\n'
                'CIRCUIT_PORT=8102\nCIRCUIT_ACCESS_MODE=private\nCIRCUIT_PROXY_TOKEN=' + token + '\n',
                0o600)
    configure_receiver()
    configure_private_site(token)
    subprocess.run(['a2ensite', 'circuit-lab.conf'], check=True)
    subprocess.run(['apachectl', 'configtest'], check=True)
    subprocess.run(['systemctl', 'reload', 'apache2'], check=True)
    print('Circuit Lab bootstrap complete; HTTPS remains disabled until certificate issuance')


if __name__ == '__main__':
    main()
