"""The release receiver rejects unsafe transport before touching service state."""

import io
import tarfile
from pathlib import Path
from xml.etree import ElementTree

import pytest

from deploy import deploy_release


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
def test_publish_landing_exposes_only_allowlisted_assets(tmp_path: Path,
                                                        monkeypatch: pytest.MonkeyPatch,
                                                        has_favicon: bool,
                                                        has_theme: bool) -> None:
    release = tmp_path / 'releases' / ('a' * 40)
    source = release / 'frontend' / 'public'
    source.mkdir(parents=True)
    expected_names = {'landing.html', 'landing.css'}
    if has_favicon:
        expected_names.add('favicon.svg')
    if has_theme:
        expected_names.add('theme.css')
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
