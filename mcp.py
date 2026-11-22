"""A small MCP server exposing calculator and utility tools over stdio.

Run directly with:  python mcp.py
The agent.py script starts this automatically as a subprocess.
Every tool call is recorded in flow.log next to this file.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

# This file is deliberately named mcp.py, which would shadow the installed
# `mcp` package. Remove this script's own directory from sys.path so that
# `import mcp` resolves to the real SDK instead of to this file.
_script_dir = Path(__file__).resolve().parent
sys.path[:] = [p for p in sys.path if p and Path(p).resolve() != _script_dir]

from datetime import datetime, timezone
from statistics import mean

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

# Same log file as agent.py, so both processes write one continuous flow.
LOG_FILE = Path(__file__).with_name("flow.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(filename)s:%(lineno)d %(funcName)s() | %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8")],
)
log = logging.getLogger("mcp_server")
log.info("FLOW: === mcp.py server process started ===")

server = MCPServer(
    name="utility-calculator",
    description="Calculator and utility tools for the demo agent.",
)
log.info("FLOW: MCPServer object created with name=%s", server.name)


@server.tool()
def add(a: float, b: float) -> float:
    """Add two numbers and return the sum."""
    result = a + b
    log.info("FLOW: TOOL add(a=%s, b=%s) -> %s", a, b, result)
    return result


@server.tool()
def subtract(a: float, b: float) -> float:
    """Subtract b from a and return the difference."""
    result = a - b
    log.info("FLOW: TOOL subtract(a=%s, b=%s) -> %s", a, b, result)
    return result


@server.tool()
def multiply(a: float, b: float) -> float:
    """Multiply two numbers and return the product."""
    result = a * b
    log.info("FLOW: TOOL multiply(a=%s, b=%s) -> %s", a, b, result)
    return result


@server.tool()
def divide(a: float, b: float) -> float:
    """Divide a by b and return the quotient. Fails when b is zero."""
    if b == 0:
        log.warning("FLOW: TOOL divide(a=%s, b=%s) rejected: division by zero", a, b)
        raise ToolError("Cannot divide by zero.")
    result = a / b
    log.info("FLOW: TOOL divide(a=%s, b=%s) -> %s", a, b, result)
    return result


@server.tool()
def power(base: float, exponent: float) -> float:
    """Raise base to the power of exponent."""
    result = base ** exponent
    log.info("FLOW: TOOL power(base=%s, exponent=%s) -> %s", base, exponent, result)
    return result


@server.tool()
def average(values: list[float]) -> float:
    """Return the arithmetic mean of a list of numbers."""
    if not values:
        log.warning("FLOW: TOOL average(values=%r) rejected: empty list", values)
        raise ToolError("Provide at least one number.")
    result = mean(values)
    log.info("FLOW: TOOL average(values=%r) -> %s", values, result)
    return result


@server.tool()
def greet(name: str) -> str:
    """Return a friendly greeting for the given name."""
    result = f"Hello, {name}! Welcome from the MCP server."
    log.info("FLOW: TOOL greet(name=%r) -> %r", name, result)
    return result


@server.tool()
def get_time() -> str:
    """Return the current UTC time as an ISO 8601 string."""
    result = datetime.now(timezone.utc).isoformat()
    log.info("FLOW: TOOL get_time() -> %r", result)
    return result


log.info("FLOW: all 8 tools registered; waiting for requests")

if __name__ == "__main__":
    # stdio reserves stdout for the MCP protocol; never print here.
    log.info("FLOW: starting MCP server on stdio")
    server.run("stdio")
