"""Backed-up, idempotent localization settings for the existing identity realm."""

import argparse
import json
import os
import shlex
import stat
from pathlib import Path
from typing import Protocol

from deploy.staging_identity import RealmAdmin

LOCALIZATION_SETTINGS: dict[str, object] = {
    "internationalizationEnabled": True, "supportedLocales": ["de", "en"], "defaultLocale": "en",
    "loginTheme": "circuit-lab", "accountTheme": "circuit-lab",
}


class RealmAdministration(Protocol):
    def request(self, path: str, body: object = None, method: str = "GET") -> object: ...


def migrate_localization(admin: RealmAdministration, snapshot: Path) -> bool:
    current = admin.request("")
    if not isinstance(current, dict):
        raise ValueError("Identity realm is unavailable")
    if all(current.get(key) == expected for key, expected in LOCALIZATION_SETTINGS.items()):
        return False
    before = {key: current.get(key) for key in LOCALIZATION_SETTINGS}
    snapshot.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    preserve_snapshot(snapshot, before)
    admin.request("", LOCALIZATION_SETTINGS, "PUT")
    verified = admin.request("")
    if not isinstance(verified, dict) or any(verified.get(key) != expected
                                            for key, expected in LOCALIZATION_SETTINGS.items()):
        raise ValueError("Identity localization update was not verified; retain its settings snapshot")
    return True


def preserve_snapshot(snapshot: Path, before: dict[str, object]) -> None:
    try:
        descriptor = os.open(snapshot, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        if snapshot.is_symlink() or not stat.S_ISREG(snapshot.stat().st_mode) or snapshot.stat().st_mode & 0o077:
            raise ValueError("Existing localization snapshot must be a private regular file") from None
        if json.loads(snapshot.read_text()) != before:
            raise ValueError("Existing localization snapshot differs; use a new snapshot path") from None
        return
    with os.fdopen(descriptor, "w") as destination:
        json.dump(before, destination, indent=2)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", required=True, choices=["http://127.0.0.1:8104", "http://127.0.0.1:8114"])
    parser.add_argument("--settings", type=Path, required=True)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--database-backup", type=Path, required=True)
    arguments = parser.parse_args()
    if arguments.settings.stat().st_mode & 0o077:
        raise ValueError("Identity settings must be private")
    with arguments.database_backup.open("rb") as backup:
        if backup.read(5) != b"PGDMP":
            raise ValueError("Take a custom-format identity database backup first")
    settings = dict(line.split("=", 1) for line in arguments.settings.read_text().splitlines()
                    if line and not line.startswith("#"))
    password = shlex.split(settings["CIRCUIT_IDENTITY_ADMIN_PASSWORD"])[0]
    changed = migrate_localization(RealmAdmin(arguments.endpoint, password), arguments.snapshot)
    print("Identity localization verified" if changed else "Identity localization already matches")


if __name__ == "__main__":
    main()
