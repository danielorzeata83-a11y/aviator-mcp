"""Măsoară tokenii (≈ caractere/4) ai listei de tool-uri, așa cum o vede modelul."""
import asyncio, json, sys
sys.path.insert(0, "src")
from mcp.client.client import Client
from aviator_mcp.client import AviatorClient
from aviator_mcp.server import build_server

async def main():
    async with Client(build_server(AviatorClient(token="x"))) as c:
        tools = (await c.list_tools()).tools
    rows = []
    for t in tools:
        d = {"name": t.name, "description": t.description, "input_schema": t.input_schema}
        rows.append((t.name, len(json.dumps(d)) // 4, len(t.description or "") // 4))
    total = sum(r[1] for r in rows)
    for r in sorted(rows, key=lambda r: -r[1]): print(f"{r[0]:22}{r[1]:6}{r[2]:5}")
    print("TOTAL_TOKENS", total)
asyncio.run(main())
