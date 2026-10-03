#!/usr/bin/env python3
"""Root-owned, fixed-scope release receiver. Only trusted main may deploy."""

import fcntl
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import urllib.request
from pathlib import Path

ROOT = Path('/opt/circuit-lab')
MAX_ARCHIVE = 20 * 1024 * 1024


def validate_revision(revision: str) -> str:
    """Never turn an SSH argument into a shell expression or path."""
    if not re.fullmatch(r'[0-9a-f]{40}', revision):
        raise ValueError('Expected a full Git revision')
    return revision


def unpack_release(revision: str, payload: bytes) -> Path:
    """Reject oversized archives, traversal, links, devices, and duplicates."""
    destination = ROOT / 'releases' / validate_revision(revision)
    with tarfile.open(fileobj=io.BytesIO(payload)) as archive:
        members = archive.getmembers()
        if len(members) > 2000 or sum(item.size for item in members) > MAX_ARCHIVE:
            raise ValueError('Release exceeds extraction limits')
        names: set[str] = set()
        for item in members:
            path = Path(item.name)
            if (path.is_absolute() or '..' in path.parts or item.name in names
                    or not (item.isfile() or item.isdir())):
                raise ValueError('Unsafe archive entry')
            names.add(item.name)
        if destination.exists():
            raise ValueError('Release already received; use a fresh commit')
        destination.mkdir(parents=True)
        archive.extractall(destination, filter='data')
    return destination


def compose(release: Path, *arguments: str) -> None:
    """Use fixed service scope and a per-revision image tag."""
    registry_config = ROOT / 'docker-client'
    registry_config.mkdir(mode=0o700, exist_ok=True)
    environment = dict(os.environ, CIRCUIT_IMAGE_TAG=release.name,
                       DOCKER_CONFIG=str(registry_config))
    subprocess.run(['docker', 'compose', '-p', 'circuit-lab', '--env-file',
                    str(ROOT / '.env'), '-f', str(release / 'compose.yaml'), *arguments],
                   env=environment, check=True, timeout=600)


def check_live(revision: str) -> None:
    """Check revision plus a real isolated simulation, not just container liveness."""
    with urllib.request.urlopen('http://127.0.0.1:8102/api/health', timeout=5) as response:
        if json.load(response)['build_id'] != revision:
            raise ValueError('Running revision does not match release')
    settings = dict(line.split('=', 1) for line in (ROOT / '.env').read_text().splitlines()
                    if line and not line.startswith('#'))
    request = urllib.request.Request(
        'http://127.0.0.1:8102/api/circuits/voltage_divider/simulate', data=b'{}',
        headers={'Content-Type': 'application/json', 'X-Circuit-Actor': 'ai-agent:deployment',
                 'X-Circuit-Proxy-Token': settings['CIRCUIT_PROXY_TOKEN']})
    with urllib.request.urlopen(request, timeout=25) as response:
        report = json.load(response)
    if report['status'] != 'passed' or not report['signals']:
        raise ValueError('Deployment simulation did not pass')


def point_release(name: str, release: Path) -> None:
    """Atomically update a pointer without removing release contents."""
    temporary = ROOT / (name + '.next')
    temporary.unlink(missing_ok=True)
    temporary.symlink_to(release)
    temporary.replace(ROOT / name)


def publish_landing(release: Path) -> None:
    """Publish only the two public assets, never the release or its configuration."""
    source = release / 'frontend' / 'public'
    if not (source / 'landing.html').is_file():
        return
    destination = Path('/var/www/circuit-lab-pages') / release.name
    destination.mkdir(parents=True, mode=0o755, exist_ok=True)
    for name in ('landing.html', 'landing.css'):
        shutil.copyfile(source / name, destination / name)
        (destination / name).chmod(0o644)
    temporary = Path('/var/www/circuit-lab-public.next')
    temporary.unlink(missing_ok=True)
    temporary.symlink_to(destination)
    temporary.replace('/var/www/circuit-lab-public')


def deploy(release: Path) -> None:
    """Build first; roll back service failures to the previously verified revision."""
    current = ROOT / 'current'
    previous = current.resolve() if current.is_symlink() else None
    compose(release, 'build', '--build-arg', 'CIRCUIT_BUILD_ID=' + release.name)
    try:
        compose(release, 'up', '-d', '--wait', '--wait-timeout', '90')
        check_live(release.name)
        publish_landing(release)
    except (subprocess.SubprocessError, OSError, ValueError, KeyError):
        if previous:
            compose(previous, 'up', '-d', '--wait', '--wait-timeout', '90')
            check_live(previous.name)
        else:
            compose(release, 'stop')
        raise
    if previous:
        point_release('previous', previous)
    point_release('current', release)
    print('Verified release ' + release.name, flush=True)


def main() -> None:
    """Serialize deployments and consume at most one bounded stdin archive."""
    revision = validate_revision(sys.argv[1])
    payload = sys.stdin.buffer.read(MAX_ARCHIVE + 1)
    if len(payload) > MAX_ARCHIVE:
        raise ValueError('Release archive is too large')
    with (ROOT / 'deploy.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        current = ROOT / 'current'
        if current.is_symlink() and current.resolve().name == revision:
            check_live(revision)
            print('Already running verified release ' + revision)
            return
        deploy(unpack_release(revision, payload))


if __name__ == '__main__':
    main()
