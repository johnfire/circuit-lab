#!/usr/bin/env python3
"""Forced SSH command: no shell, forwarding, arbitrary paths, or arbitrary sudo."""

import os
import re


def main() -> None:
    """Allow only a full commit ID and the root-owned deployment receiver."""
    match = re.fullmatch(r'deploy ([0-9a-f]{40})', os.environ.get('SSH_ORIGINAL_COMMAND', ''))
    if not match:
        raise SystemExit('Only deploy <full commit ID> is permitted')
    os.execv('/usr/bin/sudo', ['sudo', '-n', '/usr/local/sbin/circuit-lab-deploy', match[1]])


if __name__ == '__main__':
    main()
