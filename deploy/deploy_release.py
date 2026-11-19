#!/usr/bin/env python3
"""Root-owned, fixed-scope release receiver. Only trusted main may deploy."""

import fcntl
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path

ROOT = Path('/opt/circuit-lab')
STAGING_ROOT = Path('/opt/circuit-lab-staging')
PUBLIC_PAGES = Path('/var/www/circuit-lab-pages')
PUBLIC_LINK = Path('/var/www/circuit-lab-public')
MAX_ARCHIVE = 20 * 1024 * 1024


@dataclass(frozen=True)
class DeploymentTarget:
    root: Path
    project: str
    port: int
    origin: str
    pages: Path
    public_link: Path


def production_target() -> DeploymentTarget:
    return DeploymentTarget(ROOT, 'circuit-lab', 8102, 'https://circuit-lab.christopherrehm.de',
                            PUBLIC_PAGES, PUBLIC_LINK)


def staging_target() -> DeploymentTarget:
    return DeploymentTarget(STAGING_ROOT, 'circuit-lab-staging', 8112,
                            'https://staging.circuit-lab.christopherrehm.de',
                            Path('/var/www/circuit-lab-staging-pages'),
                            Path('/var/www/circuit-lab-staging-public'))


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
                    or path in (Path('.received-sha256'), Path('.staged-images.json'))
                    or not (item.isfile() or item.isdir())):
                raise ValueError('Unsafe archive entry')
            names.add(item.name)
        if destination.exists():
            raise ValueError('Release already received; use a fresh commit')
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=destination.parent) as temporary:
            extracted = Path(temporary) / 'source'
            extracted.mkdir()
            archive.extractall(extracted, filter='data')
            (extracted / '.received-sha256').write_text(hashlib.sha256(payload).hexdigest())
            extracted.rename(destination)
    return destination


def target_settings(target: DeploymentTarget) -> dict[str, str]:
    configured = dict(line.split('=', 1) for line in (target.root / '.env').read_text().splitlines()
                      if line and not line.startswith('#'))
    if (configured['CIRCUIT_PUBLIC_URL'] != target.origin
            or configured['CIRCUIT_PORT'] != str(target.port)
            or configured['CIRCUIT_ACCESS_MODE'] != 'private'):
        raise ValueError('Environment does not match the deployment target')
    return configured


def compose(release: Path, target: DeploymentTarget, *arguments: str) -> None:
    """Use fixed service scope and a per-revision image tag."""
    registry_config = ROOT / 'docker-client'
    registry_config.mkdir(mode=0o700, exist_ok=True)
    environment = dict(os.environ, CIRCUIT_IMAGE_TAG=release.name,
                       DOCKER_CONFIG=str(registry_config))
    configured = target_settings(target)
    project_overlay = release / 'compose.projects.yaml'
    overlays = ['-f', str(project_overlay)] if configured.get('CIRCUIT_ENABLE_PROJECTS') == 'true' and project_overlay.is_file() else []
    subprocess.run(['docker', 'compose', '-p', target.project, '--env-file',
                    str(target.root / '.env'), '-f', str(release / 'compose.yaml'), *overlays,
                    *arguments],
                   env=environment, check=True, timeout=600)


def check_live(revision: str, target: DeploymentTarget) -> None:
    """Check revision plus a real isolated simulation, not just container liveness."""
    base = f'http://127.0.0.1:{target.port}'
    with urllib.request.urlopen(base + '/api/health', timeout=5) as response:
        if json.load(response)['build_id'] != revision:
            raise ValueError('Running revision does not match release')
    settings = target_settings(target)
    request = urllib.request.Request(
        base + '/api/circuits/voltage_divider/simulate', data=b'{}',
        headers={'Content-Type': 'application/json', 'X-Circuit-Actor': 'ai-agent:deployment',
                 'X-Circuit-Proxy-Token': settings['CIRCUIT_PROXY_TOKEN']})
    with urllib.request.urlopen(request, timeout=25) as response:
        report = json.load(response)
    if report['status'] != 'passed' or not report['signals']:
        raise ValueError('Deployment simulation did not pass')


def point_release(name: str, release: Path, target: DeploymentTarget) -> None:
    """Atomically update a pointer without removing release contents."""
    temporary = target.root / (name + '.next')
    temporary.unlink(missing_ok=True)
    temporary.symlink_to(release)
    temporary.replace(target.root / name)


def publish_landing(release: Path, target: DeploymentTarget | None = None) -> None:
    """Publish only the public landing assets, never release configuration."""
    target = target or production_target()
    source = release / 'frontend' / 'public'
    if not (source / 'landing.html').is_file():
        return
    destination = target.pages / release.name
    destination.mkdir(parents=True, mode=0o755, exist_ok=True)
    optional_assets = ('favicon.svg', 'theme.css', 'landing-analytics.js')
    for name in ('landing.html', 'landing.css', *optional_assets):
        if name in optional_assets and not (source / name).is_file():
            continue  # Older immutable releases predate these optional assets.
        shutil.copyfile(source / name, destination / name)
        (destination / name).chmod(0o644)
    temporary = target.public_link.with_name(target.public_link.name + '.next')
    temporary.unlink(missing_ok=True)
    temporary.symlink_to(destination)
    temporary.replace(target.public_link)


def deploy(release: Path, target: DeploymentTarget) -> None:
    """Use already-built images and roll back only the affected application stack."""
    current = target.root / 'current'
    previous = current.resolve() if current.is_symlink() else None
    up = ('up', '-d', '--no-build', '--pull', 'never', '--wait', '--wait-timeout', '90')
    try:
        compose(release, target, *up)
        check_live(release.name, target)
        publish_landing(release, target)
    except (subprocess.SubprocessError, OSError, ValueError, KeyError):
        if previous:
            compose(previous, target, *up)
            check_live(previous.name, target)
        else:
            compose(release, target, 'stop')
        raise
    if previous and previous != release:
        point_release('previous', previous, target)
    point_release('current', release, target)
    print(f'Verified {target.project} release {release.name}', flush=True)


def release_image_ids(release: Path) -> list[str]:
    """Read the actual API and worker image IDs behind a release's local tags."""
    references = [f'circuit-lab-{service}:{release.name}' for service in ('api', 'worker')]
    inspected = subprocess.run(['docker', 'image', 'inspect', '--format', '{{.Id}}', *references],
                               capture_output=True, text=True, check=True, timeout=15)
    return inspected.stdout.splitlines()


def receive_release(revision: str, payload: bytes) -> Path:
    release = ROOT / 'releases' / revision
    if not release.exists():
        return unpack_release(revision, payload)
    if (release / '.received-sha256').read_text() != hashlib.sha256(payload).hexdigest():
        raise ValueError('Release archive has changed')
    return release


def stage_release(revision: str, payload: bytes) -> None:
    target = staging_target()
    release = receive_release(revision, payload)
    staged = target.root / 'current'
    image_record = release / '.staged-images.json'
    if staged.is_symlink() and staged.resolve() == release and image_record.is_file():
        if release_image_ids(release) != json.loads(image_record.read_text()):
            raise ValueError('Staged images changed')
        check_live(revision, target)
        return
    if (ROOT / 'current').resolve() == release:
        raise ValueError('An active production release cannot be rebuilt')
    compose(release, target, 'build', '--build-arg', 'CIRCUIT_BUILD_ID=' + revision)
    if target_settings(target).get('CIRCUIT_ENABLE_PROJECTS') == 'true':
        compose(release, target, 'pull', 'application-db')
    temporary = image_record.with_suffix('.next')
    temporary.write_text(json.dumps(release_image_ids(release)))
    temporary.replace(image_record)
    deploy(release, target)


def promote_release(revision: str) -> None:
    release = ROOT / 'releases' / revision
    staged = STAGING_ROOT / 'current'
    if not staged.is_symlink() or staged.resolve() != release:
        raise ValueError('Expected the current staging release')
    if release_image_ids(release) != json.loads((release / '.staged-images.json').read_text()):
        raise ValueError('Production promotion requires the staged images')
    deploy(release, production_target())


def main() -> None:
    """Serialize deployments and consume at most one bounded stdin archive."""
    action, supplied_revision = sys.argv[1:]
    revision = validate_revision(supplied_revision)
    with (ROOT / 'deploy.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if action == 'stage':
            payload = sys.stdin.buffer.read(MAX_ARCHIVE + 1)
            if len(payload) > MAX_ARCHIVE:
                raise ValueError('Release archive is too large')
            stage_release(revision, payload)
        elif action == 'promote':
            promote_release(revision)
        elif action == 'deploy' and (ROOT / 'current').resolve().name == revision:
            sys.stdin.buffer.read(MAX_ARCHIVE + 1)
            check_live(revision, production_target())
        else:
            raise ValueError('Expected stage or promote')


if __name__ == '__main__':
    main()
