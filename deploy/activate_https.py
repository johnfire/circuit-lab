"""Render only this site's protected proxy configuration, with safe reload."""

import os
import shutil
import subprocess
from pathlib import Path


def main() -> None:
    """Validate a replacement before reloading; restore configuration on failure."""
    source = Path(__file__).resolve().parent
    settings = dict(line.split('=', 1) for line in Path('/opt/circuit-lab/.env').read_text().splitlines()
                    if line and not line.startswith('#'))
    target = Path('/etc/apache2/sites-available/circuit-lab-ssl.conf')
    before = target.read_text()
    rendered = (source / 'apache-https.conf.template').read_text()
    target.write_text(rendered.replace('__PROXY_TOKEN__', settings['CIRCUIT_PROXY_TOKEN']))
    try:
        subprocess.run(['apachectl', 'configtest'], check=True)
    except subprocess.CalledProcessError:
        target.write_text(before)
        raise
    shutil.copyfile(source / 'apache-http.conf', '/etc/apache2/sites-available/circuit-lab.conf')
    subprocess.run(['apachectl', 'configtest'], check=True)
    hook = Path('/etc/letsencrypt/renewal-hooks/deploy/circuit-lab-reload')
    shutil.copyfile(source / 'renew_certificate.sh', hook)
    os.chmod(hook, 0o755)
    subprocess.run(['systemctl', 'reload', 'apache2'], check=True)


if __name__ == '__main__':
    main()
