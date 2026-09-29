"""Official MCP Python SDK v1 stdio server with strict argument validation."""

import asyncio
import json

import mcp.types as types
from mcp.server import Server
from mcp.server.stdio import stdio_server

from .bridge.client import BridgeClient
from .tools.animation_schema import SCHEMAS, DESCRIPTIONS, WRITE_METHODS

server = Server("cascadeur-mcp-c01")


@server.list_tools()
async def list_tools():
    empty = {"type": "object", "properties": {}, "additionalProperties": False}
    readonly = types.ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)
    return [
        types.Tool(name="ping_cascadeur", description="Confirm a live response from the Cascadeur host bridge.",
                   inputSchema=empty, annotations=readonly),
        types.Tool(name="get_scene_info", description="Read current Cascadeur scene name, frame and object count.",
                   inputSchema=empty, annotations=readonly),
        types.Tool(name="get_objects", description="Read a bounded page of object names and types; names are not unique IDs.",
                   inputSchema={"type": "object", "additionalProperties": False, "properties": {
                       "offset": {"type": "integer", "minimum": 0, "maximum": 1000000, "default": 0},
                       "limit": {"type": "integer", "minimum": 1, "maximum": 200, "default": 100}}},
                   annotations=readonly),
    ] + [types.Tool(name=name, description=DESCRIPTIONS[name], inputSchema=spec,
                    annotations=types.ToolAnnotations(readOnlyHint=name not in WRITE_METHODS,
                        destructiveHint=name in WRITE_METHODS, openWorldHint=False))
         for name, spec in SCHEMAS.items()]


@server.call_tool()
async def call_tool(name, arguments):
    try:
        result = await asyncio.to_thread(BridgeClient().call, name, arguments)
        return types.CallToolResult(content=[types.TextContent(type="text", text=json.dumps(result))],
                                    structuredContent=result, isError=False)
    except Exception as exc:
        return types.CallToolResult(content=[types.TextContent(
            type="text", text=type(exc).__name__ + ": " + str(exc))], isError=True)


async def run():
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


def main():
    asyncio.run(run())


if __name__ == "__main__":
    main()
