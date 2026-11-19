"""A small agent that talks to the MCP server in mcp.py over stdio.

Two modes:
  * Default: a built-in rule-based router (no API key needed).
  * LLM mode: set OPENAI_API_KEY (in the environment or in a .env file) to let
    an OpenAI model choose and call the MCP tools for you. Optionally set
    OPENAI_MODEL (default: gpt-4o-mini).

Run with:  python agent.py
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

# mcp.py lives beside this file and would shadow the installed `mcp` package.
# Drop this directory from sys.path so `import mcp` finds the real SDK.
_here = Path(__file__).resolve().parent
sys.path[:] = [p for p in sys.path if p and Path(p).resolve() != _here]

from mcp import ClientSession, StdioServerParameters, stdio_client  # noqa: E402

SERVER_PATH = Path(__file__).with_name("mcp.py")
EXIT_WORDS = {"quit", "exit", "q", "bye"}


def load_dotenv(path: Path) -> None:
    """Load KEY=VALUE lines from a .env file into os.environ (no dependency)."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


load_dotenv(Path(__file__).with_name(".env"))


# --------------------------------------------------------------------------
# MCP helpers
# --------------------------------------------------------------------------
def result_text(result: Any) -> str:
    """Pull readable text out of an MCP tool result."""
    chunks = [
        getattr(part, "text", None) or str(part)
        for part in getattr(result, "content", [])
    ]
    text = "\n".join(chunks).strip() or "(no output)"
    if getattr(result, "is_error", False):
        return f"Tool error: {text}"
    return text


async def call_tool(session: ClientSession, name: str, arguments: dict[str, Any]) -> str:
    result = await session.call_tool(name, arguments)
    return result_text(result)


# --------------------------------------------------------------------------
# Mode 1: rule-based router (works with no API key)
# --------------------------------------------------------------------------
NUMBER_RE = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)")


def parse_request(text: str, tool_names: set[str]) -> tuple[str, dict[str, Any]] | None:
    """Turn a simple English request into an MCP tool call."""
    lower = text.lower()

    if "average" in lower or "mean" in lower:
        values = [float(n) for n in NUMBER_RE.findall(text)]
        return "average", {"values": values}

    if "time" in lower or "date" in lower:
        return "get_time", {}

    if "greet" in lower or lower.startswith("hello") or lower.startswith("hi "):
        name_match = re.search(r"(?:greet|hello|hi)\s+([A-Za-z][\w\s]*)", text, re.I)
        name = name_match.group(1).strip().rstrip(".!?") if name_match else "there"
        return "greet", {"name": name}

    numbers = [float(n) for n in NUMBER_RE.findall(text)]
    operation: str | None = None
    if any(w in lower for w in ("plus", "add", "sum", "+")):
        operation = "add"
    elif any(w in lower for w in ("minus", "subtract", "difference", "-")):
        operation = "subtract"
    elif any(w in lower for w in ("multiply", "times", "product", "*", "x ")):
        operation = "multiply"
    elif any(w in lower for w in ("divide", "divided", "quotient", "/")):
        operation = "divide"
    elif any(w in lower for w in ("power", "exponent", "**")):
        operation = "power"

    if operation and len(numbers) >= 2:
        return operation, {"a": numbers[0], "b": numbers[1]}

    if operation and operation in tool_names:
        return None  # recognized but missing numbers
    return None


async def rule_based_loop(session: ClientSession, tools: list[Any]) -> None:
    tool_names = {t.name for t in tools}
    print("\nMode: rule-based (no API key).")
    print("Try: 'add 5 and 3', 'divide 10 by 2', 'average 1 2 3', 'greet Sam', 'time'.")
    print("Type 'quit' to exit.\n")

    while True:
        try:
            user_input = input("You> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not user_input:
            continue
        if user_input.lower() in EXIT_WORDS:
            print("Goodbye!")
            break

        parsed = parse_request(user_input, tool_names)
        if parsed is None:
            print("Agent> Sorry, I didn't understand that. Try one of the examples above.")
            continue

        name, arguments = parsed
        if name not in tool_names:
            print(f"Agent> The server does not expose a '{name}' tool.")
            continue

        try:
            answer = await call_tool(session, name, arguments)
            print(f"Agent> [via {name}] {answer}")
        except Exception as error:  # noqa: BLE001 - demo agent reports all failures
            print(f"Agent> Something went wrong: {error}")


# --------------------------------------------------------------------------
# Mode 2: OpenAI LLM agent (needs OPENAI_API_KEY)
# --------------------------------------------------------------------------
async def llm_loop(session: ClientSession, tools: list[Any]) -> None:
    from openai import OpenAI  # imported lazily so rule-based mode needs no key

    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    client = OpenAI()  # reads OPENAI_API_KEY from the environment
    openai_tools = [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description or "",
                "parameters": tool.input_schema,
            },
        }
        for tool in tools
    ]

    messages: list[dict[str, Any]] = [
        {
            "role": "system",
            "content": (
                "You are a helpful assistant. Use the available MCP tools for "
                "arithmetic and utilities instead of computing answers yourself. "
                "Report the tool's result to the user."
            ),
        }
    ]

    print(f"\nMode: OpenAI LLM ({model}). Type 'quit' to exit.\n")

    while True:
        try:
            user_input = input("You> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not user_input:
            continue
        if user_input.lower() in EXIT_WORDS:
            print("Goodbye!")
            break

        messages.append({"role": "user", "content": user_input})

        try:
            for _ in range(5):  # guard against runaway tool loops
                response = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    tools=openai_tools,
                    tool_choice="auto",
                )
                assistant_message = response.choices[0].message
                messages.append(assistant_message.model_dump(exclude_none=True))

                if not assistant_message.tool_calls:
                    if assistant_message.content:
                        print(f"Agent> {assistant_message.content}")
                    break

                for call in assistant_message.tool_calls:
                    name = call.function.name
                    arguments = json.loads(call.function.arguments or "{}")
                    print(f"Agent> calling {name}({arguments})")
                    answer = await call_tool(session, name, arguments)
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call.id,
                            "content": answer,
                        }
                    )
            else:
                print("Agent> I stopped after too many tool calls.")
        except Exception as error:  # noqa: BLE001 - keep the REPL alive
            print(f"Agent> Something went wrong: {error}")


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------
async def run() -> None:
    server_params = StdioServerParameters(
        command=sys.executable,
        args=[str(SERVER_PATH)],
        cwd=str(_here),
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools_result = await session.list_tools()
            tools = tools_result.tools

            print("Connected to MCP server. Available tools:")
            for tool in tools:
                print(f"  - {tool.name}: {tool.description or ''}")

            if os.environ.get("OPENAI_API_KEY"):
                await llm_loop(session, tools)
            else:
                await rule_based_loop(session, tools)


if __name__ == "__main__":
    asyncio.run(run())
