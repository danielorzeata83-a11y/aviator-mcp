"""CLI the evaluating agent uses to call the real MCP server against the fake Aviator world.

  python eval/call.py --task N --list                 # tool names, descriptions, input schemas
  python eval/call.py --task N <tool> '<json args>'   # call a tool; prints the tool result

State and a call log are kept per task in eval/out/ (fresh world for every task).
"""
import asyncio
import json
import logging
import sys

logging.disable(logging.CRITICAL)
from pathlib import Path

HERE = Path(__file__).parent
sys.path[:0] = [str(HERE.parent / "src"), str(HERE)]

import httpx  # noqa: E402
from mcp.client.client import Client  # noqa: E402

from aviator_mcp.client import AviatorClient  # noqa: E402
from aviator_mcp.server import build_server  # noqa: E402
import world  # noqa: E402

OUT = HERE / "out"
NO_TOKEN_TASKS = {19}


async def main(argv):
    if len(argv) < 3 or argv[0] != "--task":
        print(__doc__)
        return 2
    task = int(argv[1])
    OUT.mkdir(exist_ok=True)
    sf = OUT / f"state_{task}.json"
    state = json.loads(sf.read_text()) if sf.exists() else world.fresh()
    token = "" if task in NO_TOKEN_TASKS else "eval-token"
    client = AviatorClient(token=token, transport=httpx.MockTransport(world.handler_for(state)), sleep=lambda s: None)
    server = build_server(client)
    async with Client(server) as c:
        if argv[2] == "--list":
            tools = (await c.list_tools()).tools
            print(json.dumps([{"name": t.name, "description": t.description, "input_schema": t.input_schema}
                              for t in tools], indent=1))
            print(f"\nINSTRUCTIONS: {server.instructions}")
            return 0
        name = argv[2]
        args = json.loads(argv[3]) if len(argv) > 3 else {}
        r = await c.call_tool(name, args)
        text = r.content[0].text if r.content else ""
    with open(OUT / f"calls_{task}.jsonl", "a") as f:
        f.write(json.dumps({"tool": name, "args": args, "is_error": r.is_error, "chars": len(text)}) + "\n")
    sf.write_text(json.dumps(state))
    print(("ERROR: " if r.is_error else "") + text)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
