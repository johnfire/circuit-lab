"""Real SDK discovery/guide round trips must not advertise unfinished collaboration."""

import asyncio

from mcp import Client

from backend.component_catalog import COMPONENTS
from backend.mcp_server import create_mcp_server


def test_real_sdk_discovers_only_implemented_orientation_tools() -> None:
    async def round_trip() -> None:
        async with Client(create_mcp_server()) as client:
            catalog = await client.list_tools()
            assert {tool.name for tool in catalog.tools} == {
                "get_app_guide", "get_capabilities", "list_components", "get_component", "list_examples"}
            for tool in catalog.tools:
                assert tool.annotations is not None
                assert tool.annotations.read_only_hint is True
            capabilities = await client.call_tool("get_capabilities", {})
            assert capabilities.structured_content is not None
            assert capabilities.structured_content["collaboration_enabled"] is False
            assert capabilities.structured_content["arbitrary_netlists"] is False
    asyncio.run(round_trip())


def test_real_sdk_component_catalog_and_unknown_device_failure() -> None:
    async def round_trip() -> None:
        async with Client(create_mcp_server()) as client:
            response = await client.call_tool("get_component", {"kind": "R"})
            assert response.structured_content is not None
            assert response.structured_content["standard_values"] == COMPONENTS["R"].standard_values
            assert response.structured_content["maximum"] == 1e8
            assert len((await client.call_tool("list_examples", {})).content) > 0
            unknown = await client.call_tool("get_component", {"kind": "arbitrary-shell"})
            assert unknown.is_error is True
            assert "Unsupported component" in str(unknown.content)
    asyncio.run(round_trip())


def test_real_sdk_resources_and_prompts_explain_boundaries() -> None:
    async def round_trip() -> None:
        async with Client(create_mcp_server()) as client:
            resources = await client.list_resources()
            assert any(str(resource.uri) == "circuit-lab://guide" for resource in resources.resources)
            guide = await client.read_resource("circuit-lab://guide")
            assert "orientation tools only" in str(guide.contents)
            prompts = await client.list_prompts()
            assert {prompt.name for prompt in prompts.prompts} == {
                "get_started", "explain_circuit", "debug_circuit", "improve_circuit"}
            for prompt in prompts.prompts:
                response = await client.get_prompt(prompt.name)
                assert "Do not invent" in str(response.messages) or "Do not invent" in str(response).replace("do not", "Do not")
                assert "Raspberry Pi" in str(response.messages)
                assert "expected_revision" in str(response.messages)
    asyncio.run(round_trip())
