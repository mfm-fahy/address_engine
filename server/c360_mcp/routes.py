import asyncio
import json

from fastapi import APIRouter, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from c360_mcp.auth import validate_api_key
from c360_mcp.handler import (
    handle_list_resources,
    handle_read_resource,
    handle_list_tools,
    handle_call_tool,
    get_pool,
    close_pool,
)

router = APIRouter(prefix="/mcp", tags=["mcp"])


def _verify_auth(request: Request):
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Missing or invalid Authorization header")
    result = validate_api_key(auth.removeprefix("Bearer "))
    if not result:
        raise HTTPException(403, "Invalid API key")
    return result


@router.get("/v1/sse")
async def sse_endpoint(request: Request):
    _verify_auth(request)

    async def event_generator():
        endpoint_data = json.dumps({"endpoint": "/mcp/v1/message"})
        yield {"event": "endpoint", "data": endpoint_data}
        try:
            while True:
                if await request.is_disconnected():
                    break
                await asyncio.sleep(15)
                yield {"event": "ping", "data": ""}
        except asyncio.CancelledError:
            pass

    return EventSourceResponse(event_generator())


@router.post("/v1/message")
async def message_endpoint(request: Request):
    _verify_auth(request)
    body = await request.json()
    req_id = body.get("id", 1)
    method = body.get("method", "")
    params = body.get("params", {})

    if method == "resources/list":
        resources = await handle_list_resources()
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"resources": [r.model_dump() for r in resources]},
        }

    if method == "resources/read":
        uri = params.get("uri", "")
        if not uri:
            raise HTTPException(400, "uri is required")
        content = await handle_read_resource(uri)
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "contents": [
                    {"uri": uri, "mimeType": "application/json", "text": content}
                ]
            },
        }

    if method == "tools/list":
        tools = await handle_list_tools()
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"tools": [t.model_dump() for t in tools]},
        }

    if method == "tools/call":
        name = params.get("name", "")
        arguments = params.get("arguments", {})
        results = await handle_call_tool(name, arguments)
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"content": [{"type": "text", "text": r.text} for r in results]},
        }

    raise HTTPException(400, f"Unknown method: {method}")


@router.get("/v1/health")
async def mcp_health():
    return {"status": "ok", "service": "customer360-mcp"}


@router.get("/v1/key-info")
async def key_info(request: Request):
    auth_info = _verify_auth(request)
    return {"scope": auth_info["scope"], "permissions": auth_info["permissions"]}
