"""MCP SDK server factory; not mounted publicly until delegated access is implemented."""

from mcp.server import MCPServer

from backend.mcp_guide import register_guide


def create_mcp_server() -> MCPServer[None]:
    """Build a real SDK-discoverable orientation server without exposing account data."""
    server: MCPServer[None] = MCPServer("Circuit Lab", version="0.1.0",
        instructions="Read get_capabilities before operating. Collaboration is not enabled yet.")
    register_guide(server)
    return server
