import json
import time
from typing import Any, Optional

from ai.mcp_client import get_mcp_client, MCPClient
from ai.openrouter import get_openrouter_client, OpenRouterClient
from ai.prompts import SYSTEM_PROMPT
from ai.models import ToolCallInfo, ChatResponse


_MAX_TOOL_ROUNDS = 3


class Agent:
    def __init__(self, mcp_client: Optional[MCPClient] = None, openrouter: Optional[OpenRouterClient] = None):
        self._mcp = mcp_client or get_mcp_client()
        self._or = openrouter or get_openrouter_client()

    async def process_message(self, user_message: str) -> ChatResponse:
        if not self._or.available:
            return ChatResponse(
                reply="AI assistant is not available. Please configure the OpenRouter API key.",
                model="",
            )

        tools = await self._mcp.discover_tools()
        openai_tools = self._mcp.get_openai_tools()

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ]

        tool_calls_log: list[ToolCallInfo] = []
        total_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        final_model = ""

        for _round in range(_MAX_TOOL_ROUNDS):
            response = await self._or.chat(
                messages=messages,
                tools=openai_tools if openai_tools else None,
            )

            message = response["message"]
            final_model = response.get("model", final_model)
            usage = response.get("usage", {})
            for k in total_usage:
                total_usage[k] += usage.get(k, 0)

            tool_calls = message.get("tool_calls", [])
            if not tool_calls:
                reply = message.get("content", "") or ""
                return ChatResponse(
                    reply=reply,
                    tool_calls=tool_calls_log,
                    token_usage=total_usage if any(total_usage.values()) else None,
                    model=final_model,
                )

            assistant_msg = {"role": "assistant", "content": message.get("content"), "tool_calls": tool_calls}
            messages.append(assistant_msg)

            for tc in tool_calls:
                func = tc.get("function", {})
                name = func.get("name", "")
                try:
                    args = json.loads(func.get("arguments", "{}"))
                except json.JSONDecodeError:
                    args = {}

                t0 = time.monotonic()
                result = await self._mcp.execute_tool(name, args)
                duration_ms = (time.monotonic() - t0) * 1000

                tool_result_text = self._summarize_tool_result(result)
                tool_calls_log.append(ToolCallInfo(
                    tool=name,
                    arguments=args,
                    result_summary=tool_result_text[:200],
                    duration_ms=round(duration_ms, 1),
                ))

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.get("id", ""),
                    "content": json.dumps(result, default=str),
                })

        final_response = await self._or.chat(messages=messages)
        reply = final_response.get("message", {}).get("content", "") or ""
        return ChatResponse(
            reply=reply,
            tool_calls=tool_calls_log,
            token_usage=total_usage if any(total_usage.values()) else None,
            model=final_model,
        )

    def _summarize_tool_result(self, result: dict) -> str:
        if not result.get("success"):
            return f"Error: {result.get('error', 'unknown')}"
        data = result.get("results", {})
        if isinstance(data, dict):
            total = data.get("total", data.get("count", len(data)))
            return f"Retrieved {total} record(s)" if total else "Data retrieved successfully"
        if isinstance(data, list):
            return f"Retrieved {len(data)} record(s)"
        return "Data retrieved successfully"


_agent: Optional[Agent] = None


def get_agent() -> Agent:
    global _agent
    if _agent is None:
        _agent = Agent()
    return _agent
