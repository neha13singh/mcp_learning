# Tech Stack — open_code

A reference for all tools, packages, modules, and protocols used in this project,
plus what each one does.

---

## 1. Runtime & environment

| Item | Details |
|------|---------|
| Language | **Python 3.14** (`pythoncore-3.14-64`) |
| Terminal | **Windows PowerShell** |
| Version control | **Git** + **GitHub** |
| Git remote | `origin` → `https://github.com/neha13singh/mcp_learning.git` |
| Branch | `main` |

---

## 2. External packages (pip-installed)

| Package | Version | Use in this project |
|---------|---------|---------------------|
| `mcp` | 2.3.0 | MCP SDK v2. Builds the server (`MCPServer`) and the client (`ClientSession`, `stdio_client`). |
| `openai` | 3.38.0 | LLM mode. Sends chat requests with tool definitions and reads tool calls from the model. |
| `pydantic` | 2.14.1 | Used internally by MCP to turn Python type hints into JSON schemas for tools. |
| `anyio` | 4.15.1 | Async support layer used by the MCP SDK. |
| `httpx` (shown as `httpx2` in logs) | via `openai` | Performs HTTPS calls to `https://api.openai.com/v1/chat/completions`. |

No web framework, database, or container tooling is used.

---

## 3. MCP SDK components

Imported from the `mcp` package:

| Component | File | Purpose |
|-----------|------|---------|
| `MCPServer` | `mcp.py` | Creates the server object; `@server.tool()` registers functions as tools. |
| `ToolError` | `mcp.py` | Raises a clean, protocol-level tool error instead of an ugly traceback. |
| `StdioServerParameters` | `agent.py` | Describes how to launch the server subprocess (command, args, cwd). |
| `stdio_client` | `agent.py` | Starts `python mcp.py` and yields read/write streams for communication. |
| `ClientSession` | `agent.py` | Wraps those streams into an MCP session; handles handshake and tool calls. |

---

## 4. Python standard-library modules

| Module | Files | Purpose |
|--------|-------|---------|
| `__future__` | `mcp.py`, `agent.py` | `annotations` — keeps type hints as text until a library resolves them. |
| `sys` | `mcp.py`, `agent.py` | Removes the script folder from `sys.path` (avoids local `mcp.py` shadowing the SDK); `sys.executable` launches the server with the same Python. |
| `pathlib.Path` | `mcp.py`, `agent.py` | Locates `mcp.py`, `.env`, `flow.log`, and derives each script's folder. |
| `logging` | `mcp.py`, `agent.py` | Writes `flow.log` with time, level, filename, line number, and function name. |
| `asyncio` | `agent.py` | Runs async code: `async def`, `await`, `async with`, `asyncio.run()`. |
| `json` | `agent.py` | `json.loads()` converts OpenAI's tool-argument string into a Python dict. |
| `os` | `agent.py` | Reads environment variables (`OPENAI_API_KEY`, `OPENAI_MODEL`). |
| `re` | `agent.py` | Regex for extracting numbers and greeting names in rule-based mode. |
| `typing.Any` | `agent.py` | Generic type hints where the exact type is not important. |
| `datetime` | `mcp.py` | `datetime.now(timezone.utc)` produces the current UTC time. |
| `statistics` | `mcp.py` | `mean()` computes the average of a list. |

---

## 5. MCP tools exposed by `mcp.py`

| Tool | Parameters | Returns | Description |
|------|-----------|---------|-------------|
| `add` | `a: float`, `b: float` | `float` | Adds two numbers. |
| `subtract` | `a: float`, `b: float` | `float` | Subtracts `b` from `a`. |
| `multiply` | `a: float`, `b: float` | `float` | Multiplies two numbers. |
| `divide` | `a: float`, `b: float` | `float` | Divides `a` by `b`; raises `ToolError` when `b` is 0. |
| `power` | `base: float`, `exponent: float` | `float` | Raises `base` to `exponent`. |
| `average` | `values: list[float]` | `float` | Arithmetic mean; rejects an empty list. |
| `greet` | `name: str` | `str` | Returns a friendly greeting. |
| `get_time` | none | `str` | Current UTC time as an ISO 8601 string. |

The type hints on each tool become the **input schema** the agent/LLM sees; the docstring becomes the tool **description**.

---

## 6. Protocols & patterns

| Concept | Where it appears |
|---------|------------------|
| **MCP (Model Context Protocol)** | Whole project — tools are exposed and discovered through it. |
| **stdio transport** | `server.run("stdio")` and `stdio_client(...)`; messages use stdin/stdout, not a network port. |
| **JSON-RPC** | Underneath MCP; handled by the SDK automatically. |
| **Subprocess** | `agent.py` launches `python mcp.py` as a child process. |
| **OpenAI tool/function calling** | `chat.completions.create(..., tools=..., tool_choice="auto")`. |
| **Environment-based config** | `.env` file plus real environment variables; no config parser library. |
| **Shared file logging** | Both processes append to `flow.log`; `.gitignore` keeps it out of Git. |

---

## 7. File-by-file map

| File | Stack used |
|------|-----------|
| `calculator.py` | Pure Python, no external libraries. Interactive menu. |
| `mcp.py` | `mcp` SDK + `logging`, `pathlib`, `sys`, `datetime`, `statistics`. |
| `agent.py` | `mcp` SDK + `openai` SDK + `asyncio`, `json`, `logging`, `os`, `re`, `sys`, `pathlib`, `typing`. |
| `.env` | Secret config (`OPENAI_API_KEY`, optional `OPENAI_MODEL`). **Never committed.** |
| `flow.log` | Combined runtime log from both processes. **Not committed.** |
| `.gitignore` | Excludes `.env`, `flow.log`, `__pycache__/`, `*.py[cod]`. |
| `TECH_STACK.md` | This document. |

---

## 8. Common commands

```powershell
# Run the agent (it starts the MCP server itself)
python agent.py

# Watch the flow log live
Get-Content flow.log -Wait

# Clear the log
Clear-Content flow.log

# Check Git state
git status --short --branch
git remote -v
```

---


