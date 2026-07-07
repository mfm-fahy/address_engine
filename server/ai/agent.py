from typing import Optional

from ai.models import ChatResponse


class Agent:
    def __init__(self):
        pass

    async def process_message(self, user_message: str) -> ChatResponse:
        return ChatResponse(
            reply="AI assistant is not available. No LLM provider is configured.",
            model="",
        )


_agent: Optional[Agent] = None


def get_agent() -> Agent:
    global _agent
    if _agent is None:
        _agent = Agent()
    return _agent
