"""The release receiver rejects unsafe transport before touching service state."""

import io
import tarfile
from pathlib import Path

import pytest

from deploy import deploy_release


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
