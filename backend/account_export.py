"""Export only the authenticated person's profile and application audit events."""

import json
import logging
import os
import urllib.request
from pathlib import Path
from typing import cast

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from backend.request_security import public_url

LOGGER = logging.getLogger('circuit-lab.account')


def own_profile(request: Request) -> dict[str, object]:
    """Fetch the signed-in profile with a gateway-provided token, never client input."""
    token = request.headers.get('x-circuit-access-token', '')
    if not public_url() or not token or len(token) > 10000:
        raise HTTPException(status_code=503, detail='Account export is unavailable')
    endpoint = public_url() + '/auth/realms/circuit-lab/protocol/openid-connect/userinfo'
    if os.environ.get('CIRCUIT_WORKER_SOCKET'):
        endpoint = 'http://identity:8080/auth/realms/circuit-lab/protocol/openid-connect/userinfo'
    submitted = urllib.request.Request(endpoint, headers={'Authorization': 'Bearer ' + token})
    with urllib.request.urlopen(submitted, timeout=5) as response:
        profile = json.load(response)
    if not isinstance(profile, dict) or 'user:' + str(profile.get('sub')) != request.state.actor:
        raise ValueError('Identity does not match authenticated subject')
    return cast(dict[str, object], profile)


def own_audit_events(actor: str) -> list[dict[str, object]]:
    """Never expose other accounts' events in a self-service download."""
    audit_path = Path(os.environ.get('CIRCUIT_AUDIT_PATH', '/tmp/circuit-lab-audit.jsonl'))
    if not audit_path.exists():
        return []
    events = []
    with audit_path.open() as audit:
        for line in audit:
            event = json.loads(line)
            if event.get('actor') == actor:
                events.append(event)
    return events


def export_account(request: Request) -> JSONResponse:
    """Fail this feature safely if identity or audit storage is unavailable."""
    try:
        profile = own_profile(request)
        events = own_audit_events(request.state.actor)
    except (OSError, ValueError) as error:
        LOGGER.error('Account export unavailable: %s', type(error).__name__)
        raise HTTPException(status_code=503, detail='Account export is temporarily unavailable') from error
    return JSONResponse(
        {'profile': profile, 'simulation_events': events, 'saved_projects': [],
         'note': 'Designs are not stored on the server yet. Export your current simulation separately.'},
        headers={'Content-Disposition': 'attachment; filename="circuit-lab-account.json"'})
