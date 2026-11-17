"""Smoke test: pornește serverul real prin stdio (ca Claude Desktop) și listează tool-urile + schemele."""
import asyncio
import json
import os
import sys

from mcp.client.client import Client, StdioServerParameters


async def main():
    params = StdioServerParameters(command=sys.executable, args=["-m", "aviator_mcp.server"],
                                   env={**os.environ, "AVIATOR_API_TOKEN": "", "PYTHONPATH": "src"})
    async with Client(params) as c:
        tools = (await c.list_tools()).tools
        bad = [t.name for t in tools if t.input_schema.get("type") != "object"]
        print(json.dumps({"tools": len(tools), "invalid_schemas": bad,
                          "names": sorted(t.name for t in tools)}, indent=1))
        r = await c.call_tool("get_queue_stats", {"repo": "acme/api"})
        print("call without token ->", r.is_error, r.content[0].text[:120])


asyncio.run(main())
