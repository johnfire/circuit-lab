#!/usr/bin/env bash
# Back up Circuit Lab's application and identity databases plus the audit log into one dated folder.
# Each dump is checked with pg_restore --list and fingerprinted; nothing old is ever deleted here.
# On-host copies protect against corruption, bad migrations and mistakes, not against losing the VPS:
# copy /var/backups/circuit-lab off the host as well.
set -euo pipefail

DESTINATION=${CIRCUIT_BACKUP_ROOT:-/var/backups/circuit-lab}
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
TARGET="$DESTINATION/$STAMP"
umask 077
mkdir -p "$TARGET"

dump_database() {
  local container=$1 user=$2 database=$3 file=$4
  docker exec "$container" pg_dump -U "$user" -d "$database" -Fc > "$TARGET/$file"
  docker exec -i "$container" pg_restore --list > /dev/null < "$TARGET/$file"
}

dump_database circuit-lab-application-db-1 circuit_application circuit_application application.dump
dump_database circuit-lab-identity-database-1 circuit_identity circuit_identity identity.dump
# Reuse the already-present pinned PostgreSQL image for its tar, rather than pulling a new image.
ARCHIVER=postgres:17-alpine@sha256:b0f9560a2de083e2cc7382e75f808c7381a32852a7ec49117deedb300e552b24
docker run --rm --network none -v circuit-lab_audit-log:/audit:ro --entrypoint tar "$ARCHIVER" \
  -C /audit -czf - . > "$TARGET/audit-log.tar.gz"

(cd "$TARGET" && sha256sum application.dump identity.dump audit-log.tar.gz > SHA256SUMS)
date -u +%Y-%m-%dT%H:%M:%SZ > "$DESTINATION/last-success"
echo "circuit-lab backup ok: $TARGET ($(du -sh "$TARGET" | cut -f1))"
