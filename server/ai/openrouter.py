import json
import time
from typing import Any, Optional

import httpx

from config import settings


class OpenRouterError(Exception):
    pass


class OpenRouterClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 30.0,
        max_tokens: int = 1024,
    ):
        self._api_key = settings.OPENROUTER_API_KEY if api_key is None else api_key
        self._model = model or settings.OPENROUTER_MODEL
        self._timeout = timeout
        self._max_tokens = max_tokens
        self._base_url = "https://openrouter.ai/api/v1/chat/completions"

    @property
    def available(self) -> bool:
        return bool(self._api_key)

    async def chat(
        self,
        messages: list[dict],
        tools: Optional[list[dict]] = None,
        temperature: float = 0.3,
    ) -> dict:
        if not self.available:
            raise OpenRouterError("OpenRouter API key not configured")

        payload = {
            "model": self._model,
            "messages": messages,
            "max_tokens": self._max_tokens,
            "temperature": temperature,
        }
        if tools:
            payload["tools"] = tools

        t0 = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    self._base_url,
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                resp.raise_for_status()
                body = resp.json()
        except httpx.TimeoutException:
            raise OpenRouterError("OpenRouter request timed out")
        except httpx.HTTPStatusError as e:
            raise OpenRouterError(f"OpenRouter returned {e.response.status_code}")
        except Exception as e:
            raise OpenRouterError(f"OpenRouter request failed: {e}")

        elapsed = time.monotonic() - t0
        choice = body.get("choices", [{}])[0]
        usage = body.get("usage", {})

        return {
            "message": choice.get("message", {}),
            "finish_reason": choice.get("finish_reason", ""),
            "usage": {
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
            },
            "model": body.get("model", self._model),
            "latency_ms": round(elapsed * 1000),
        }

    def count_tokens(self, text: str) -> int:
        try:
            import tiktoken
            enc = tiktoken.get_encoding("cl100k_base")
            return len(enc.encode(text))
        except ImportError:
            return len(text) // 4


_openrouter_client: Optional[OpenRouterClient] = None


def get_openrouter_client() -> OpenRouterClient:
    global _openrouter_client
    if _openrouter_client is None:
        _openrouter_client = OpenRouterClient()
    return _openrouter_client
