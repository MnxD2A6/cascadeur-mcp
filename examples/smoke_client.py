"""Real SDK/stdio calls. Never substitutes a fake Cascadeur for a missing host."""

import argparse
import asyncio
import importlib.metadata
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def smoke():
    report = {"time_utc": datetime.now(timezone.utc).isoformat(),
              "sdk_version": importlib.metadata.version("mcp"),
              "client": "official Python SDK (not Codex)", "calls": []}
    params = StdioServerParameters(command=sys.executable, args=["-m", "cascadeur_mcp.server"])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            report["protocol_version"] = init.protocolVersion
            report["tools"] = [tool.name for tool in (await session.list_tools()).tools]
            for name, arguments in [("ping_cascadeur", {}), ("get_scene_info", {}),
                                    ("get_objects", {"offset": 0, "limit": 10})]:
                result = await session.call_tool(name, arguments)
                report["calls"].append({"tool": name, "arguments": arguments,
                                        "result": result.model_dump(mode="json")})
    report["all_tools_succeeded"] = all(not c["result"]["isError"] for c in report["calls"])
    report["codex_acceptance"] = "NOT_TESTED_BY_THIS_SCRIPT"
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = asyncio.run(smoke())
    encoded = json.dumps(report, ensure_ascii=True, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)
    raise SystemExit(0 if report["all_tools_succeeded"] else 1)
