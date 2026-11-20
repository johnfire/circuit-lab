"""Existing realms are patched narrowly; realm import never replaces customer state."""

import json
from pathlib import Path

import pytest

from deploy.identity_localization import LOCALIZATION_SETTINGS, migrate_localization


class RealmFixture:
    def __init__(self):
        self.realm = {"registrationAllowed": True, "smtpServer": {"host": "private"},
                      "defaultLocale": "fr", "internationalizationEnabled": False}
        self.writes = []

    def request(self, path, body=None, method="GET"):
        assert path == ""
        if method == "PUT":
            self.writes.append(body)
            self.realm.update(body)
            return None
        return dict(self.realm)


def test_migration_preserves_accounts_and_security_and_is_idempotent(tmp_path: Path):
    admin = RealmFixture()
    backup = tmp_path / "locale-before.json"
    assert migrate_localization(admin, backup)
    assert admin.writes == [LOCALIZATION_SETTINGS]
    assert admin.realm["registrationAllowed"] is True
    assert admin.realm["smtpServer"] == {"host": "private"}
    assert backup.stat().st_mode & 0o077 == 0
    previous = json.loads(backup.read_text())
    assert previous["defaultLocale"] == "fr" and "smtpServer" not in previous
    assert not migrate_localization(admin, backup)
    assert len(admin.writes) == 1


def test_migration_can_retry_after_snapshot_and_failed_write(tmp_path: Path):
    admin = RealmFixture()
    backup = tmp_path / "locale-before.json"
    original = admin.request
    failed = False

    def interrupted(path, body=None, method="GET"):
        nonlocal failed
        if method == "PUT" and not failed:
            failed = True
            raise ConnectionError("interrupted write")
        return original(path, body, method)

    admin.request = interrupted
    with pytest.raises(ConnectionError):
        migrate_localization(admin, backup)
    snapshot = backup.read_bytes()
    assert migrate_localization(admin, backup)
    assert backup.read_bytes() == snapshot


def test_migration_rejects_unrelated_existing_snapshot(tmp_path: Path):
    admin = RealmFixture()
    backup = tmp_path / "locale-before.json"
    backup.write_text('{}')
    backup.chmod(0o600)
    with pytest.raises(ValueError, match="snapshot"):
        migrate_localization(admin, backup)
    assert not admin.writes
