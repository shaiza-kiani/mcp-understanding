"""Verify the weather MCP server works as a real stdio server.

Spawns `python mcp_server.py` as a subprocess and speaks the MCP protocol to it
over stdin/stdout pipes, which is how an MCP client (Claude Desktop, opencode,
etc.) actually connects. This is deliberately separate from the in-memory tests,
which bypass the transport entirely.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

PROJECT_DIR = Path(__file__).parent
PYTHON = PROJECT_DIR / ".venv" / "Scripts" / "python.exe"


async def main() -> int:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    env = dict(os.environ)
    # Ensure the server starts in a directory where .env resolves, and that a key
    # is present even if the caller's shell lacks it.
    if not env.get("WEATHER_API_KEY") and (PROJECT_DIR / ".env").exists():
        for line in (PROJECT_DIR / ".env").read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                key, _, value = line.partition("=")
                env[key.strip()] = value.strip().strip('"').strip("'")

    server = StdioServerParameters(
        command=str(PYTHON),
        args=["mcp_server.py"],
        cwd=str(PROJECT_DIR),
        env=env,
    )

    if os.environ.get("TEST_AWAY_FROM_PROJECT_DIR") == "1":
        # Simulate a host that launches the server from an unrelated directory
        # and passes no key, to prove .env is found without help.
        server = StdioServerParameters(
            command=str(PYTHON),
            args=[str(PROJECT_DIR / "mcp_server.py")],
            cwd=tempfile.gettempdir(),
            env={k: v for k, v in env.items() if k != "WEATHER_API_KEY"},
        )
        print("(launched from an unrelated cwd with no WEATHER_API_KEY in env)\n")

    print("Spawning server over stdio...\n")
    async with stdio_client(server) as (read, write):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            print(f"protocol version : {init.protocol_version}")
            print(f"server name      : {init.server_info.name} {init.server_info.version}")
            print(f"server caps      : tools={init.capabilities.tools is not None}\n")

            tools = await session.list_tools()
            print(f"tools ({len(tools.tools)}):")
            for tool in tools.tools:
                print(f"  - {tool.name}: {(tool.description or '').splitlines()[0]}")
                schema = tool.input_schema.get("properties", {})
                for prop, spec in schema.items():
                    print(f"      {prop}: {spec.get('type')} - {spec.get('description', '')}")
            print()

            print("calling get_weather('Islamabad') ...")
            result = await session.call_tool("get_weather", {"city": "Islamabad"})
            print(f"  isError : {result.is_error}")
            payload = result.structured_content
            if payload is None and result.content:
                text = result.content[0].text
                try:
                    payload = json.loads(text)
                except json.JSONDecodeError:
                    payload = {"raw": text}
            print(f"  result  : {json.dumps(payload, indent=2)}")
            print()

            print("calling get_weather('Atlantisxyz999') for the error path ...")
            bad = await session.call_tool("get_weather", {"city": "Atlantisxyz999"})
            print(f"  isError : {bad.is_error}")
            if bad.content:
                print(f"  detail  : {bad.content[0].text[:120]}")
            print()

            return 0 if not result.is_error else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
