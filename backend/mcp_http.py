"""Authenticated SDK Streamable HTTP integrated without browser-cookie impersonation."""

from typing import cast

from mcp.server import MCPServer
from mcp.server.auth.settings import AuthSettings
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import AnyHttpUrl
from starlette.responses import Response
from starlette.types import ASGIApp, Receive, Scope, Send

from backend.mcp_projects import register_collaboration
from backend.project_runtime import CollaborationRuntime
from backend.request_security import allowed_hosts, public_url


def create_authenticated_server(runtime: CollaborationRuntime) -> MCPServer[None]:
    """Resource audience is enforced by both introspection and the SDK middleware."""
    auth = AuthSettings(issuer_url=AnyHttpUrl(runtime.verifier.issuer),
                        resource_server_url=AnyHttpUrl(runtime.verifier.resource),
                        required_scopes=["circuit:read"], validate_token_resource=True)
    server: MCPServer[None] = MCPServer("Circuit Lab", version="0.2.0", auth=auth,
        token_verifier=runtime.verifier, instructions="Read capabilities, choose an explicitly shared target, "
        "reread its revision before editing, and explain only real simulation evidence.")
    register_collaboration(server, runtime)
    return server


def create_http_app(server: MCPServer[None]) -> ASGIApp:
    """Bound protocol input and permit only the configured app origin or native clients."""
    hosts = [entry for hostname in allowed_hosts() for entry in (hostname, hostname + ":*")]
    origins = [public_url()] if public_url() else ["http://127.0.0.1:*", "http://localhost:*"]
    return cast(ASGIApp, server.streamable_http_app(streamable_http_path="/mcp", stateless_http=True,
        json_response=True, max_request_body_size=65536,
        transport_security=TransportSecuritySettings(allowed_hosts=hosts, allowed_origins=origins)))


class MCPResponse(Response):
    """Delegate only exact MCP/metadata routes to the SDK's own authenticated ASGI app."""

    def __init__(self, application: ASGIApp) -> None:
        super().__init__()
        self.application = application

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        await self.application(scope, receive, send)
