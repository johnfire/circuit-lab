"""Explicit local/hosted request policy; hosted requests require a trusted proxy."""

import hmac
import os
import re
from urllib.parse import urlparse

from fastapi import Request
from fastapi.responses import JSONResponse

LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


def public_url() -> str:
    """Return the configured HTTPS origin or reject a dangerous deployment."""
    configured = os.environ.get("CIRCUIT_PUBLIC_URL", "").rstrip("/")
    if configured:
        parsed = urlparse(configured)
        if (parsed.scheme != "https" or not parsed.hostname or parsed.path or parsed.username
                or parsed.query or parsed.fragment):
            raise ValueError("CIRCUIT_PUBLIC_URL must be an HTTPS origin")
    return configured


def allowed_hosts() -> list[str]:
    """Keep the trusted-host check separate from forwarded request headers."""
    hosted_name = urlparse(public_url()).hostname
    return ["localhost", "127.0.0.1", "[::1]", *([hosted_name] if hosted_name else [])]


def reject_unsafe_request(request: Request) -> JSONResponse | None:
    """Fail closed on proxy bypass, foreign origins, or missing private identity."""
    configured = public_url()
    request.state.actor = "user:local"
    origin = request.headers.get("origin")
    if configured:
        if request.url.path == "/api/health" and request.url.hostname in LOCAL_HOSTS:
            return None
        expected = os.environ.get("CIRCUIT_PROXY_TOKEN", "")
        submitted = request.headers.get("x-circuit-proxy-token", "")
        if len(expected) < 32 or not hmac.compare_digest(expected.encode(), submitted.encode()):
            return JSONResponse({"detail": "Trusted proxy access required"}, status_code=403)
        actor = request.headers.get("x-circuit-actor", "")
        if not actor and os.environ.get("CIRCUIT_ACCESS_MODE", "private") != "public":
            return JSONResponse({"detail": "Authentication required"}, status_code=401)
        if actor and not re.fullmatch(r"[a-zA-Z0-9:@._/-]{1,80}", actor):
            return JSONResponse({"detail": "Invalid authenticated actor"}, status_code=403)
        request.state.actor = actor if actor.startswith("ai-agent:") else "user:" + (actor or "public-demo")
        if origin and origin != configured:
            return JSONResponse({"detail": "Foreign origin rejected"}, status_code=403)
    elif origin and (urlparse(origin).scheme not in {"http", "https"}
                     or urlparse(origin).hostname not in LOCAL_HOSTS):
        return JSONResponse({"detail": "This prototype accepts local requests only"}, status_code=403)
    return None
