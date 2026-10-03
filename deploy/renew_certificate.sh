#!/usr/bin/env bash
set -euo pipefail
if [[ "${RENEWED_LINEAGE:-}" == /etc/letsencrypt/live/circuit-lab.christopherrehm.de ]]; then
  apachectl configtest
  systemctl reload apache2
fi
