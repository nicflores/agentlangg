"""CLI: send a prompt to the agent, print the full trace.

Usage:
    uv run python -m agent.main "Summarize cus_001's order activity."
    uv run python -m agent.main      # uses the default demo prompt

What it prints:
    [user]        the prompt you sent
    [tool_call]   every tool the model decided to call
    [tool_result] the MCP server's response (truncated)
    [ai]          the model's final text answer
"""

import asyncio
import json
import sys
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from agent.builder import build_agent

DEFAULT_PROMPT = (
    "Summarize Acme Corp's order activity. Their customer id is cus_001."
)


def _format_tool_args(args: dict[str, Any]) -> str:
    return json.dumps(args, separators=(", ", "="), default=str)


def _print_message(message) -> None:
    if isinstance(message, HumanMessage):
        print(f"[user] {message.content}\n")
        return

    if isinstance(message, AIMessage):
        for call in message.tool_calls or []:
            print(f"[tool_call] {call['name']}({_format_tool_args(call['args'])})")
        if message.content:
            print(f"[ai] {message.content}")
        print()
        return

    if isinstance(message, ToolMessage):
        body = str(message.content)
        preview = body if len(body) <= 400 else body[:400] + "…"
        print(f"[tool_result] {message.name}: {preview}\n")
        return


async def run(prompt: str) -> None:
    agent = await build_agent()

    result = await agent.ainvoke(
        {"messages": [HumanMessage(content=prompt)]},
    )

    for message in result["messages"]:
        _print_message(message)


def main() -> None:
    prompt = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else DEFAULT_PROMPT
    asyncio.run(run(prompt))


if __name__ == "__main__":
    main()
