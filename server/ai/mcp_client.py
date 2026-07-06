import asyncio
import json
import time
from typing import Any, Optional

from c360_mcp.handler import (
    get_pool,
    handle_list_tools,
    handle_call_tool,
    handle_read_resource,
)


class MCPClientError(Exception):
    pass


class MCPTool:
    def __init__(self, name: str, description: str, inputSchema: dict):
        self.name = name
        self.description = description
        self.input_schema = inputSchema

    def to_openai_function(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_schema,
            },
        }


class MCPClient:
    def __init__(self, retry_count: int = 2, timeout: float = 15.0):
        self._retry_count = retry_count
        self._timeout = timeout
        self._tools_initialized = False
        self._tools: list[MCPTool] = []
        self._pool_initialized = False

    async def _ensure_pool(self) -> None:
        if not self._pool_initialized:
            try:
                await get_pool()
                self._pool_initialized = True
            except Exception as e:
                raise MCPClientError(f"Failed to initialize MCP pool: {e}")

    async def discover_tools(self) -> list[MCPTool]:
        if self._tools_initialized:
            return self._tools

        await self._ensure_pool()
        for attempt in range(self._retry_count + 1):
            try:
                raw_tools = await asyncio.wait_for(
                    handle_list_tools(), timeout=self._timeout
                )
                self._tools = [
                    MCPTool(
                        name=t.name,
                        description=t.description,
                        inputSchema=t.inputSchema,
                    )
                    for t in raw_tools
                ]
                self._tools_initialized = True
                return self._tools
            except asyncio.TimeoutError:
                if attempt < self._retry_count:
                    await asyncio.sleep(0.5 * (attempt + 1))
                    continue
                raise MCPClientError("Tool discovery timed out")
            except Exception as e:
                if attempt < self._retry_count:
                    await asyncio.sleep(0.5 * (attempt + 1))
                    continue
                raise MCPClientError(f"Tool discovery failed: {e}")

    async def execute_tool(self, name: str, arguments: dict) -> dict:
        await self._ensure_pool()
        for attempt in range(self._retry_count + 1):
            try:
                results = await asyncio.wait_for(
                    handle_call_tool(name, arguments), timeout=self._timeout
                )
                texts = []
                for r in results:
                    try:
                        texts.append(json.loads(r.text))
                    except (json.JSONDecodeError, TypeError):
                        texts.append(r.text)
                return {
                    "tool": name,
                    "arguments": arguments,
                    "results": texts[0] if len(texts) == 1 else texts,
                    "success": True,
                }
            except asyncio.TimeoutError:
                if attempt < self._retry_count:
                    await asyncio.sleep(0.5 * (attempt + 1))
                    continue
                return self._error_result(name, arguments, "Tool execution timed out")
            except Exception as e:
                if attempt < self._retry_count:
                    await asyncio.sleep(0.5 * (attempt + 1))
                    continue
                return self._error_result(name, arguments, str(e))

    async def read_resource(self, uri: str) -> dict:
        await self._ensure_pool()
        for attempt in range(self._retry_count + 1):
            try:
                content = await asyncio.wait_for(
                    handle_read_resource(uri), timeout=self._timeout
                )
                try:
                    parsed = json.loads(content)
                except (json.JSONDecodeError, TypeError):
                    parsed = {"data": content}
                return {"uri": uri, "data": parsed, "success": True}
            except asyncio.TimeoutError:
                if attempt < self._retry_count:
                    await asyncio.sleep(0.5 * (attempt + 1))
                    continue
                return {"uri": uri, "error": "Resource read timed out", "success": False}
            except Exception as e:
                if attempt < self._retry_count:
                    await asyncio.sleep(0.5 * (attempt + 1))
                    continue
                return {"uri": uri, "error": str(e), "success": False}

    def _error_result(self, name: str, arguments: dict, error: str) -> dict:
        return {
            "tool": name,
            "arguments": arguments,
            "error": error,
            "success": False,
        }

    def get_openai_tools(self) -> list[dict]:
        if not self._tools_initialized:
            return []
        return [t.to_openai_function() for t in self._tools]


_mcp_client: Optional[MCPClient] = None


def get_mcp_client() -> MCPClient:
    global _mcp_client
    if _mcp_client is None:
        _mcp_client = MCPClient()
    return _mcp_client
