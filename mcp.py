"""A small MCP server exposing calculator and utility tools over stdio.

Run directly with:  python mcp.py
The agent.py script starts this automatically as a subprocess.
"""

from __future__ import annotations

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

server = MCPServer(
    name="utility-calculator",
    description="Calculator and utility tools for the demo agent.",
)


@server.tool()
def add(a: float, b: float) -> float:
    """Add two numbers and return the sum."""
    return a + b


@server.tool()
def subtract(a: float, b: float) -> float:
    """Subtract b from a and return the difference."""
    return a - b


@server.tool()
def multiply(a: float, b: float) -> float:
    """Multiply two numbers and return the product."""
    return a * b


@server.tool()
def divide(a: float, b: float) -> float:
    """Divide a by b and return the quotient. Fails when b is zero."""
    if b == 0:
        raise ToolError("Cannot divide by zero.")
    return a / b


@server.tool()
def power(base: float, exponent: float) -> float:
    """Raise base to the power of exponent."""
    return base ** exponent


@server.tool()
def average(values: list[float]) -> float:
    """Return the arithmetic mean of a list of numbers."""
    if not values:
        raise ToolError("Provide at least one number.")
    return mean(values)


@server.tool()
def greet(name: str) -> str:
    """Return a friendly greeting for the given name."""
    return f"Hello, {name}! Welcome from the MCP server."


@server.tool()
def get_time() -> str:
    """Return the current UTC time as an ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    # stdio reserves stdout for the MCP protocol; never print here.
    server.run("stdio")
