"""Real MCP stdio protocol; a deliberately absent host, never a mock success."""

import asyncio
import os
import sys

import pytest

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


@pytest.mark.skipif(os.name != "nt", reason="Windows runtime isolation uses LOCALAPPDATA")
def test_stdio_schema_and_absent_host(tmp_path):
    async def run():
        params = StdioServerParameters(command=sys.executable,
            args=["-m", "cascadeur_mcp.server"], env={"LOCALAPPDATA": str(tmp_path)})
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = (await session.list_tools()).tools
                assert {"ping_cascadeur", "get_scene_info", "get_objects"} <= {t.name for t in tools}
                missing = await session.call_tool("ping_cascadeur", {})
                assert missing.isError and "BRIDGE_UNAVAILABLE" in missing.content[0].text
                for args in [{"limit": True}, {"limit": 201}, {"code": "anything"}]:
                    invalid = await session.call_tool("get_objects", args)
                    assert invalid.isError
                    assert "BRIDGE_UNAVAILABLE" not in invalid.content[0].text
                unknown = await session.call_tool("execute_python", {"code": "anything"})
                assert unknown.isError
    asyncio.run(run())
