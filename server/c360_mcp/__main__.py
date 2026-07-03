import asyncio
import json
import sys

from mcp.server import Server
from mcp.server.models import InitializationOptions
import mcp.server.stdio
import mcp.types as types

from c360_mcp.handler import (
    handle_list_resources,
    handle_read_resource,
    handle_list_tools,
    handle_call_tool,
    get_pool,
    close_pool,
)
from c360_mcp.auth import (
    store_key_hash,
    generate_api_key,
    ALL_PERMISSIONS,
    get_training_api_key,
)

server = Server("customer360-mcp")


@server.list_resources()
async def list_resources():
    return await handle_list_resources()


@server.read_resource()
async def read_resource(uri: str):
    content = await handle_read_resource(uri)
    return types.TextResourceContents(
        uri=uri,
        mimeType="application/json",
        text=content,
    )


@server.list_tools()
async def list_tools():
    return await handle_list_tools()


@server.call_tool()
async def call_tool(name: str, arguments: dict = None):
    results = await handle_call_tool(name, arguments or {})
    return [r for r in results]


async def main():
    import argparse

    parser = argparse.ArgumentParser(description="Customer360 MCP Server")
    parser.add_argument("--api-key", help="Pre-set API key for authentication")
    parser.add_argument(
        "--generate-key", action="store_true", help="Generate a new API key and exit"
    )
    args = parser.parse_args()

    if args.generate_key:
        key = generate_api_key()
        env_var = "C360_TRAINING_API_KEY"
        print(f"\n{'='*60}")
        print(f"  TRAINING API KEY GENERATED")
        print(f"{'='*60}")
        print(f"  API Key: {key}")
        print(f"  Permissions: {', '.join(sorted(ALL_PERMISSIONS))}")
        print(f"\n  Set this in your .env or environment:")
        print(f"  {env_var}={key}")
        print(f"{'='*60}\n")
        return

    if args.api_key:
        store_key_hash(args.api_key)

    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="customer360-mcp",
                server_version="1.0.0",
                capabilities=server.get_capabilities(
                    notifications=None,
                    experimental_capabilities=None,
                ),
            ),
        )


if __name__ == "__main__":
    asyncio.run(main())
