#!/usr/bin/env python3
"""Forced SSH command: no shell, forwarding, arbitrary paths, or arbitrary sudo."""

import os
import re


def main() -> None:
    """Allow only a full commit ID and the root-owned deployment receiver."""
    match = re.fullmatch(r'(stage|promote|deploy) ([0-9a-f]{40})',
                         os.environ.get('SSH_ORIGINAL_COMMAND', ''))
    if not match:
        raise SystemExit('Expected stage or promote followed by a full commit ID')
    os.execv('/usr/bin/sudo', ['sudo', '-n', '/usr/local/sbin/circuit-lab-deploy', *match.groups()])


if __name__ == '__main__':
    main()
