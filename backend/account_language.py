"""Synchronize only the authenticated person's locale through Keycloak's own account API."""

import json
import logging
import os
import urllib.request
from threading import Lock
from typing import Literal

from fastapi import APIRouter, HTTPException, Request

from backend.account_export import own_profile
from backend.audit_log import record_action
from backend.model_primitives import StrictModel
from backend.project_identity import NoIdentityRedirect
from backend.request_security import public_url
from backend.simulation_engine import SimulationFailure

LOGGER = logging.getLogger("circuit-lab.account-language")
ACCOUNT_LANGUAGE_LOCK = Lock()
router = APIRouter()


class LanguagePreference(StrictModel):
    language: Literal["de", "en"]


def account_request(token: str, profile: dict[str, object] | None = None) -> dict[str, object]:
    endpoint = ("http://identity:8080" if os.environ.get("CIRCUIT_WORKER_SOCKET") else public_url())
    if not endpoint:
        raise ValueError("Hosted account service is unavailable")
    submitted = urllib.request.Request(endpoint + "/auth/realms/circuit-lab/account/",
        data=json.dumps(profile).encode() if profile is not None else None,
        headers={"Authorization": "Bearer " + token, "Accept": "application/json", "Content-Type": "application/json"})
    opener = urllib.request.build_opener(NoIdentityRedirect())
    with opener.open(submitted, timeout=5) as response:
        encoded = response.read(65537)
    if len(encoded) > 65536:
        raise ValueError("Account profile exceeded its response budget")
    if not encoded:
        return {}
    decoded: object = json.loads(encoded)
    if not isinstance(decoded, dict):
        raise ValueError("Invalid account profile")
    return decoded


def profile_with_language(profile: dict[str, object], language: str) -> dict[str, object]:
    """Keycloak requires its other profile fields; preserve them and all custom attributes."""
    attributes = profile.get("attributes", {})
    if not isinstance(attributes, dict):
        raise ValueError("Invalid profile attributes")
    return {**{key: profile[key] for key in ("username", "email", "firstName", "lastName") if key in profile},
            "attributes": {**attributes, "locale": [language]}}


@router.post("/api/account/language")
def save_account_language(preference: LanguagePreference, request: Request) -> dict[str, str]:
    """Use the gateway token and bound subject, with no administrator privileges."""
    try:
        verified = own_profile(request)
        token = request.headers.get("x-circuit-access-token", "")
        with ACCOUNT_LANGUAGE_LOCK:
            current = account_request(token)
            if current.get("id") != verified.get("sub"):
                raise ValueError("Account profile subject mismatch")
            updated = profile_with_language(current, preference.language)
            if current.get("attributes") != updated["attributes"]:
                record_action("account.language", "own-profile", request.state.correlation_id, "started", request.state.actor)
                account_request(token, updated)
                verified_account = account_request(token)
                if verified_account.get("attributes") != updated["attributes"]:
                    raise ValueError("Account language update was not persisted")
                record_action("account.language", "own-profile", request.state.correlation_id, "completed", request.state.actor)
        return {"language": preference.language}
    except (OSError, ValueError, SimulationFailure) as failure:
        LOGGER.warning("Account language unavailable correlation=%s kind=%s", request.state.correlation_id, type(failure).__name__)
        try:
            record_action("account.language", "own-profile", request.state.correlation_id, "error", request.state.actor)
        except SimulationFailure:
            LOGGER.error("Account language failure audit unavailable correlation=%s", request.state.correlation_id)
        raise HTTPException(status_code=503, detail="Account email language could not be saved") from failure
