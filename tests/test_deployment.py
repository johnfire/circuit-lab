"""The release receiver rejects unsafe transport before touching service state."""

import io
import json
import re
import tarfile
from pathlib import Path
from xml.etree import ElementTree

import pytest

from deploy import deploy_release


def test_ci_builds_frontend_before_real_database_browser_suite() -> None:
    """The pytest-launched browser needs built assets on a clean runner."""
    workflow = Path(__file__).resolve().parents[1] / '.github' / 'workflows' / 'ci.yml'
    configuration = workflow.read_text()
    build_step = configuration.index('- name: Frontend lint and production build')
    python_step = configuration.index('- name: Python lint, strict types, and unit/integration tests')
    assert build_step < python_step
    assert 'npm run build' in configuration[build_step:python_step]


def test_ci_runs_staging_browser_gate_before_promotion() -> None:
    workflow = Path('.github/workflows/ci.yml').read_text()
    stage = workflow.index('"stage $GITHUB_SHA"')
    browser = workflow.index('npm run test:staging')
    promote = workflow.index('"promote $GITHUB_SHA"')
    assert stage < browser < promote
    assert 'continue-on-error' not in workflow[stage:promote]


def test_promotion_requires_the_current_staging_release(tmp_path: Path,
                                                         monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(deploy_release, 'ROOT', tmp_path)
    monkeypatch.setattr(deploy_release, 'STAGING_ROOT', tmp_path / 'staging')
    with pytest.raises(ValueError, match='current staging release'):
        deploy_release.promote_release('b' * 40)


@pytest.mark.parametrize('changed_images', [True, False])
def test_promotion_uses_the_staged_image_ids(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                            changed_images: bool) -> None:
    staging = tmp_path / 'staging'
    staging.mkdir()
    revision = 'a' * 40
    release = tmp_path / 'releases' / revision
    release.mkdir(parents=True)
    (staging / 'current').symlink_to(release)
    image_ids = ['sha256:' + 'a' * 64, 'sha256:' + 'b' * 64]
    (release / '.staged-images.json').write_text(json.dumps(image_ids))
    monkeypatch.setattr(deploy_release, 'ROOT', tmp_path)
    monkeypatch.setattr(deploy_release, 'STAGING_ROOT', staging)
    monkeypatch.setattr(deploy_release, 'release_image_ids',
                        lambda _: image_ids[::-1] if changed_images else image_ids)
    deployments: list[tuple[Path, str]] = []
    monkeypatch.setattr(deploy_release, 'deploy',
                        lambda path, target: deployments.append((path, target.project)))
    if changed_images:
        with pytest.raises(ValueError, match='staged images'):
            deploy_release.promote_release(revision)
        assert not deployments
    else:
        deploy_release.promote_release(revision)
        assert deployments == [(release, 'circuit-lab')]


def test_favicon_is_self_contained_brand_svg() -> None:
    icon_path = Path(__file__).resolve().parents[1] / 'frontend' / 'public' / 'favicon.svg'
    icon = ElementTree.fromstring(icon_path.read_text())
    namespace = '{http://www.w3.org/2000/svg}'
    assert icon.tag == namespace + 'svg'
    assert icon.attrib['viewBox'] == '0 0 64 64'
    assert icon.findtext(namespace + 'title') == 'Circuit Lab'
    assert all(element.tag in {namespace + tag for tag in
                              ('svg', 'title', 'rect', 'g', 'path', 'circle')}
               for element in icon.iter())
    assert all('href' not in attribute for element in icon.iter()
               for attribute in element.attrib)


@pytest.mark.parametrize('has_favicon', [True, False])
@pytest.mark.parametrize('has_theme', [True, False])
@pytest.mark.parametrize('has_analytics', [True, False])
def test_publish_landing_exposes_only_allowlisted_assets(tmp_path: Path,
                                                        monkeypatch: pytest.MonkeyPatch,
                                                        has_favicon: bool,
                                                        has_theme: bool,
                                                        has_analytics: bool) -> None:
    release = tmp_path / 'releases' / ('a' * 40)
    source = release / 'frontend' / 'public'
    source.mkdir(parents=True)
    expected_names = {'landing.html', 'landing.css'}
    if has_favicon:
        expected_names.add('favicon.svg')
    if has_theme:
        expected_names.add('theme.css')
    if has_analytics:
        expected_names.add('landing-analytics.js')
    for name in expected_names:
        (source / name).write_text(name)
    (source / '.env').write_text('private-fixture-do-not-publish')
    public_link = tmp_path / 'public'
    monkeypatch.setattr(deploy_release, 'PUBLIC_PAGES', tmp_path / 'pages')
    monkeypatch.setattr(deploy_release, 'PUBLIC_LINK', public_link)
    deploy_release.publish_landing(release)
    assert public_link.is_symlink()
    assert {asset.name for asset in public_link.iterdir()} == expected_names
    assert all((public_link / name).read_text() == name for name in expected_names)
    assert all((public_link / name).stat().st_mode & 0o777 == 0o644 for name in expected_names)


def test_missing_landing_does_not_create_public_pointer(tmp_path: Path,
                                                       monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(deploy_release, 'PUBLIC_LINK', tmp_path / 'public')
    deploy_release.publish_landing(tmp_path / 'empty-release')
    assert not (tmp_path / 'public').exists()


def test_failed_publish_preserves_previous_public_pointer(tmp_path: Path,
                                                          monkeypatch: pytest.MonkeyPatch) -> None:
    previous = tmp_path / 'previous'
    previous.mkdir()
    public_link = tmp_path / 'public'
    public_link.symlink_to(previous)
    release = tmp_path / 'release'
    source = release / 'frontend' / 'public'
    source.mkdir(parents=True)
    (source / 'landing.html').write_text('new landing with missing stylesheet')
    monkeypatch.setattr(deploy_release, 'PUBLIC_PAGES', tmp_path / 'pages')
    monkeypatch.setattr(deploy_release, 'PUBLIC_LINK', public_link)
    with pytest.raises(FileNotFoundError):
        deploy_release.publish_landing(release)
    assert public_link.resolve() == previous


@pytest.mark.parametrize('revision', ['main', '../evil', 'a' * 39, 'a' * 40 + ';id'])
def test_deploy_rejects_non_commit_revision(revision: str) -> None:
    with pytest.raises(ValueError):
        deploy_release.validate_revision(revision)


@pytest.mark.parametrize('name', ['../escape', '/etc/escape'])
def test_archive_rejects_path_traversal(name: str, tmp_path: Path,
                                       monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(deploy_release, 'ROOT', tmp_path)
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w') as archive:
        archive.addfile(tarfile.TarInfo(name))
    with pytest.raises(ValueError, match='Unsafe'):
        deploy_release.unpack_release('a' * 40, stream.getvalue())
    assert not (tmp_path / 'releases').exists()


def test_archive_rejects_symlink(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(deploy_release, 'ROOT', tmp_path)
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w') as archive:
        item = tarfile.TarInfo('link')
        item.type = tarfile.SYMTYPE
        item.linkname = '/etc'
        archive.addfile(item)
    with pytest.raises(ValueError, match='Unsafe'):
        deploy_release.unpack_release('a' * 40, stream.getvalue())


def test_valid_archive_has_immutable_destination(tmp_path: Path,
                                               monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(deploy_release, 'ROOT', tmp_path)
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w') as archive:
        item = tarfile.TarInfo('README.md')
        item.size = 5
        archive.addfile(item, io.BytesIO(b'hello'))
    release = deploy_release.unpack_release('a' * 40, stream.getvalue())
    assert (release / 'README.md').read_text() == 'hello'
    with pytest.raises(ValueError, match='already received'):
        deploy_release.unpack_release('a' * 40, stream.getvalue())


def test_docker_frontend_stage_copies_every_circuits_file_the_frontend_imports() -> None:
    imported = {match for source in Path("frontend/src").glob("*.ts*")
                for match in re.findall(r"'\.\./\.\./circuits/([^']+)'", source.read_text())}
    copy_line = next(line for line in Path("Dockerfile").read_text().splitlines()
                     if line.startswith("COPY circuits/") and "/build/circuits/" in line)
    assert imported and imported <= {Path(item).name for item in copy_line.split()[1:-1]}


def test_public_translations_publish_only_allowed_languages_and_catalogues(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    release = tmp_path / 'release'
    source = release / 'frontend' / 'public'
    source.mkdir(parents=True)
    for name in ('landing.html', 'landing.css', 'landing-language.js', 'language-preference.js'):
        (source / name).write_text(name)
    for language in ('de', 'en', 'private'):
        folder = release / 'locales' / language
        folder.mkdir(parents=True)
        for name in ('landing', 'identity', 'messages', 'private'):
            (folder / (name + '.json')).write_text(language + '-' + name)
    public_link = tmp_path / 'public'
    monkeypatch.setattr(deploy_release, 'PUBLIC_PAGES', tmp_path / 'pages')
    monkeypatch.setattr(deploy_release, 'PUBLIC_LINK', public_link)
    deploy_release.publish_landing(release)
    actual = {str(path.relative_to(public_link)) for path in public_link.rglob('*') if path.is_file()}
    assert actual == {'landing.html', 'landing.css', 'landing-language.js', 'language-preference.js',
                      'locales/de/landing.json', 'locales/en/landing.json',
                      'locales/de/identity.json', 'locales/en/identity.json'}
    assert (public_link / 'locales/de/landing.json').read_text() == 'de-landing'
    assert (public_link / 'locales/en/identity.json').stat().st_mode & 0o777 == 0o644
