"""Official MCP Python SDK v1 stdio server with strict argument validation."""

import asyncio
import json

import mcp.types as types
from mcp.server import Server
from mcp.server.stdio import stdio_server

from .bridge.client import BridgeClient
from .bridge.protocol import validate_params, BridgeError, METHODS
from .bridge.errors import describe_error
from .tools.animation_schema import SCHEMAS, DESCRIPTIONS, WRITE_METHODS

server = Server("cascadeur-mcp-c01")


@server.list_tools()
async def list_tools():
    empty = {"type": "object", "properties": {}, "additionalProperties": False}
    readonly = types.ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)
    return [
        types.Tool(name='get_bridge_capabilities', description='Read contracts from the actual loaded host; runtime rig and license preconditions remain unevaluated.',
                   inputSchema=empty, annotations=readonly),
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


@server.call_tool(validate_input=False)
async def call_tool(name, arguments):
    phase, completed = 'client_validation', False
    try:
        # The same strict allowlist validator runs again at the host. Handling it
        # here keeps SDK input errors within our structured error contract.
        arguments = validate_params(name, {} if arguments is None else arguments)
        phase = 'client_session'
        client = BridgeClient()
        # Unwrapped failures during a call cannot prove that publication failed.
        phase = 'client_publish'
        result = await asyncio.to_thread(client.call, name, arguments)
        phase, completed = 'client_response', True
        return types.CallToolResult(content=[types.TextContent(type="text", text=json.dumps(result))],
                                    structuredContent=result, isError=False)
    except Exception as exc:
        known = isinstance(name, str) and name in METHODS
        details = (exc.details if isinstance(exc, BridgeError) and exc.details is not None else
                   describe_error(exc, operation=name if known else 'unknown',
                                  is_write=known and name in WRITE_METHODS,
                                  phase=phase, completed=completed))
        return types.CallToolResult(content=[types.TextContent(type='text',
            text=details['code'] + ': ' + details['message'])],
            structuredContent={'error': details}, isError=True)


async def run():
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


def main():
    asyncio.run(run())


if __name__ == "__main__":
    main()
