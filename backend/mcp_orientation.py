"""Honest live orientation, matching the actual authenticated tool catalog."""

from mcp.server import MCPServer
from mcp_types import ToolAnnotations

from backend.mcp_guide import GUIDE, get_component, list_components, list_examples
from backend.project_runtime import CollaborationRuntime

LIVE_GUIDE = GUIDE
LIVE_GUIDE = LIVE_GUIDE.replace("inspect_connectivity and validate_circuit", "validate_circuit")
LIVE_GUIDE = LIVE_GUIDE.replace("simulate_transient or simulate_ac", "simulate_circuit with analysis transient or ac")
LIVE_GUIDE += "\nCreate/copy private projects and change sharing in the browser, not through AI tools."
LIVE_GUIDE += "\nTime-domain settled sine-phase qualification is currently available in the browser, not MCP measurements."


def register_orientation(server: MCPServer[None], runtime: CollaborationRuntime) -> None:
    """Tools and resource/prompts describe implemented, not imagined, workflows."""
    annotation = ToolAnnotations(read_only_hint=True, destructive_hint=False, open_world_hint=False)
    for handler in (list_components, get_component, list_examples):
        server.tool(annotations=annotation)(handler)

    @server.tool(annotations=annotation)
    def get_app_guide() -> str:
        """Read the actual verified workflow, physical signs/units and hardware boundaries."""
        return LIVE_GUIDE

    server.resource("circuit-lab://guide", mime_type="text/plain")(get_app_guide)

    @server.tool(annotations=annotation)
    def get_capabilities() -> dict[str, object]:
        """Discover actual operations and limits; explicit grants still govern every action."""
        return {"collaboration_enabled": runtime.database.pool is not None and runtime.identity_ready,
                "analyses": ["transient", "ac"], "max_parts": 20, "max_wires": 40, "max_samples_per_page": 256,
                "manual_tokens": False, "hardware_control": False, "arbitrary_netlists": False,
                "current_reference": "terminal 0 -> 1", "units": "SI", "project_creation": "browser only",
                "view_delivery": "requires browser acknowledgement", "time_sine_phase": "browser only"}
    register_workflow_prompts(server)


def register_workflow_prompts(server: MCPServer[None]) -> None:
    """Readable prompts are guidance, not authorization or a promise of simulation success."""
    @server.prompt(name="get_started")
    def started() -> str:
        return LIVE_GUIDE

    @server.prompt(name="explain_circuit")
    def explain() -> str:
        return LIVE_GUIDE + "\nRead the selected revision and explain behavior from actual measurements."

    @server.prompt(name="debug_circuit")
    def debug() -> str:
        return LIVE_GUIDE + "\nValidate first, repair bounded graph errors, then rerun and verify."

    @server.prompt(name="improve_circuit")
    def improve() -> str:
        return LIVE_GUIDE + "\nClarify the goal, measure a baseline, edit, rerun and compare numerical evidence."
