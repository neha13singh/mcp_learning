"""A small agent that talks to the MCP server in mcp.py over stdio.

Two modes:
  * Default: a built-in rule-based router (no API key needed).
  * LLM mode: set OPENAI_API_KEY (in the environment or in a .env file) to let
    an OpenAI model choose and call the MCP tools for you. Optionally set
    OPENAI_MODEL (default: gpt-4o-mini).

Run with:  python agent.py
Every step is recorded in flow.log next to this file.
"""

from __future__ import annotations

import asyncio
import json
import logging
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

# Both agent.py and mcp.py append to this same file, giving one combined flow.
LOG_FILE = Path(__file__).with_name("flow.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(filename)s:%(lineno)d %(funcName)s() | %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8")],
)
log = logging.getLogger("agent")
log.info("FLOW: === agent.py started ===")


def load_dotenv(path: Path) -> None:
    """Load KEY=VALUE lines from a .env file into os.environ (no dependency)."""
    log.info("FLOW: load_dotenv() checking %s", path)
    if not path.exists():
        log.info("FLOW: no .env file found - skipping")
        return
    log.info("FLOW: .env file found - reading lines")
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)
            log.info("FLOW: environment variable '%s' loaded (value hidden)", key)


load_dotenv(Path(__file__).with_name(".env"))
log.info("FLOW: setup done - API key present: %s", bool(os.environ.get("OPENAI_API_KEY")))


# --------------------------------------------------------------------------
# MCP helpers
# --------------------------------------------------------------------------
def result_text(result: Any) -> str:
    """Pull readable text out of an MCP tool result."""
    log.info("FLOW: result_text() extracting content from MCP result")
    chunks = [
        getattr(part, "text", None) or str(part)
        for part in getattr(result, "content", [])
    ]
    text = "\n".join(chunks).strip() or "(no output)"
    is_error = getattr(result, "is_error", False)
    log.info("FLOW: result_text() is_error=%s text=%r", is_error, text[:200])
    if is_error:
        return f"Tool error: {text}"
    return text


async def call_tool(session: ClientSession, name: str, arguments: dict[str, Any]) -> str:
    log.info("FLOW: call_tool() requesting %s with %r", name, arguments)
    result = await session.call_tool(name, arguments)
    log.info("FLOW: call_tool() response received from %s", name)
    return result_text(result)


# --------------------------------------------------------------------------
# Mode 1: rule-based router (works with no API key)
# --------------------------------------------------------------------------
NUMBER_RE = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)")



def parse_request(text: str, tool_names: set[str]) -> tuple[str, dict[str, Any]] | None:
    """Turn a simple English request into an MCP tool call."""
    log.info("FLOW: parse_request() input=%r", text)
    lower = text.lower()

    if "average" in lower or "mean" in lower:
        values = [float(n) for n in NUMBER_RE.findall(text)]
        log.info("FLOW: matched 'average' -> values=%r", values)
        return "average", {"values": values}

    if "time" in lower or "date" in lower:
        log.info("FLOW: matched 'time' -> get_time")
        return "get_time", {}

    if "greet" in lower or lower.startswith("hello") or lower.startswith("hi "):
        name_match = re.search(r"(?:greet|hello|hi)\s+([A-Za-z][\w\s]*)", text, re.I)
        name = name_match.group(1).strip().rstrip(".!?") if name_match else "there"
        log.info("FLOW: matched greeting -> name=%r", name)
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

    log.info("FLOW: keyword scan -> operation=%s numbers=%r", operation, numbers)
    if operation and len(numbers) >= 2:
        log.info("FLOW: parse_request() succeeded -> %s", operation)
        return operation, {"a": numbers[0], "b": numbers[1]}

    if operation and operation in tool_names:
        log.info("FLOW: operation known but numbers missing - cannot call")
        return None  # recognized but missing numbers
    log.info("FLOW: parse_request() could not understand the input")
    return None


async def rule_based_loop(session: ClientSession, tools: list[Any]) -> None:
    tool_names = {t.name for t in tools}
    log.info("FLOW: rule_based_loop() started; tools=%r", sorted(tool_names))
    print("\nMode: rule-based (no API key).")
    print("Try: 'add 5 and 3', 'divide 10 by 2', 'average 1 2 3', 'greet Sam', 'time'.")
    print("Type 'quit' to exit.\n")

    while True:
        try:
            user_input = input("You> ").strip()
        except (EOFError, KeyboardInterrupt):
            log.info("FLOW: input closed (EOF/Ctrl+C) - leaving loop")
            print()
            break

        if not user_input:
            log.info("FLOW: empty input - ignoring")
            continue
        log.info("FLOW: user said %r", user_input)
        if user_input.lower() in EXIT_WORDS:
            log.info("FLOW: exit word detected - leaving loop")
            print("Goodbye!")
            break

        parsed = parse_request(user_input, tool_names)
        if parsed is None:
            log.info("FLOW: no tool selected - showing help")
            print("Agent> Sorry, I didn't understand that. Try one of the examples above.")
            continue

        name, arguments = parsed
        if name not in tool_names:
            log.warning("FLOW: tool %s is not offered by the server - skipping", name)
            print(f"Agent> The server does not expose a '{name}' tool.")
            continue

        try:
            answer = await call_tool(session, name, arguments)
            log.info("FLOW: final answer via %s -> %r", name, answer)
            print(f"Agent> [via {name}] {answer}")
        except Exception as error:  # noqa: BLE001 - demo agent reports all failures
            log.exception("FLOW: error while calling %s: %s", name, error)
            print(f"Agent> Something went wrong: {error}")

    log.info("FLOW: rule_based_loop() ended")


# --------------------------------------------------------------------------
# Mode 2: OpenAI LLM agent (needs OPENAI_API_KEY)
# --------------------------------------------------------------------------
async def llm_loop(session: ClientSession, tools: list[Any]) -> None:
    from openai import OpenAI  # imported lazily so rule-based mode needs no key

    log.info("FLOW: llm_loop() started")
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
    log.info("FLOW: converted %d MCP tools into OpenAI tools; model=%s", len(openai_tools), model)

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
            log.info("FLOW: input closed (EOF/Ctrl+C) - leaving loop")
            print()
            break

        if not user_input:
            log.info("FLOW: empty input - ignoring")
            continue
        log.info("FLOW: user said %r", user_input)
        if user_input.lower() in EXIT_WORDS:
            log.info("FLOW: exit word detected - leaving loop")
            print("Goodbye!")
            break

        messages.append({"role": "user", "content": user_input})

        try:
            for round_number in range(1, 6):  # guard against runaway tool loops
                log.info("FLOW: LLM round %d/5 - sending request", round_number)
                response = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    tools=openai_tools,
                    tool_choice="auto",
                )
                assistant_message = response.choices[0].message
                log.info(
                    "FLOW: LLM round %d returned text=%r tool_calls=%d",
                    round_number,
                    (assistant_message.content or "")[:200],
                    len(assistant_message.tool_calls or []),
                )
                messages.append(assistant_message.model_dump(exclude_none=True))

                if not assistant_message.tool_calls:
                    if assistant_message.content:
                        print(f"Agent> {assistant_message.content}")
                    log.info("FLOW: LLM answered directly - leaving round loop")
                    break

                for call in assistant_message.tool_calls:
                    name = call.function.name
                    arguments = json.loads(call.function.arguments or "{}")
                    log.info("FLOW: LLM requested tool %s with %r", name, arguments)
                    print(f"Agent> calling {name}({arguments})")
                    answer = await call_tool(session, name, arguments)
                    log.info("FLOW: tool %s result fed back to LLM: %r", name, answer)
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call.id,
                            "content": answer,
                        }
                    )
            else:
                log.warning("FLOW: 5 LLM rounds exhausted without final answer")
                print("Agent> I stopped after too many tool calls.")
        except Exception as error:  # noqa: BLE001 - keep the REPL alive
            log.exception("FLOW: error in llm loop: %s", error)
            print(f"Agent> Something went wrong: {error}")

    log.info("FLOW: llm_loop() ended")


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------
async def run() -> None:
    log.info("FLOW: run() started - preparing MCP subprocess")
    server_params = StdioServerParameters(
        command=sys.executable,
        args=[str(SERVER_PATH)],
        cwd=str(_here),
    )
    log.info("FLOW: launching %s with %s", server_params.command, server_params.args)

    async with stdio_client(server_params) as (read, write):
        log.info("FLOW: stdio streams connected to server")
        async with ClientSession(read, write) as session:
            log.info("FLOW: MCP ClientSession opened")
            await session.initialize()
            log.info("FLOW: MCP handshake completed")
            tools_result = await session.list_tools()
            tools = tools_result.tools
            log.info("FLOW: discovered %d tools", len(tools))
            for tool in tools:
                log.info("FLOW:   tool available: %s", tool.name)

            print("Connected to MCP server. Available tools:")
            for tool in tools:
                print(f"  - {tool.name}: {tool.description or ''}")

            if os.environ.get("OPENAI_API_KEY"):
                log.info("FLOW: API key present -> choosing LLM mode")
                await llm_loop(session, tools)
            else:
                log.info("FLOW: no API key -> choosing rule-based mode")
                await rule_based_loop(session, tools)

    log.info("FLOW: run() finished - server connection closed")


if __name__ == "__main__":
    log.info("FLOW: calling asyncio.run(run())")
    try:
        asyncio.run(run())
    finally:
        log.info("FLOW: === agent.py stopped ===")
