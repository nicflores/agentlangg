# agent-client

A LangGraph ReAct agent that talks to [`../mcp-postgres-server`](../mcp-postgres-server)
through a locally-running Ollama LLM (`qwen2.5:3b` by default). The agent
discovers the MCP tools at startup, binds them to the model, and runs the
standard tool-calling loop until the model produces a final answer.

## Layout

```
agent-client/
├── agent/
│   ├── config.py          # Ollama URL + model, MCP server URL
│   ├── builder.py         # MCP client → tools → ChatOllama → ReAct agent
│   └── main.py            # CLI entrypoint
├── .env.example
└── pyproject.toml
```

Total: ~80 lines of agent code. Everything else is the LangGraph + MCP
adapter doing the work for you.

## Prerequisites

### 1. Ollama with `qwen2.5:3b`

```bash
# In a separate terminal (or as a background service)
ollama serve

# One-time, downloads the model (~2GB)
ollama pull qwen2.5:3b

# Smoke test
curl http://localhost:11434/api/tags | jq '.models[].name'
```

### 2. `mcp-postgres-server` running

```bash
cd ../mcp-postgres-server
uv run python -m server.main
# Should be listening on http://127.0.0.1:8000/mcp
```

Default config works against the fake DB provider. Flip it to real Postgres
later if you want — the agent doesn't care.

## Install and run

```bash
cd agent-client
uv sync
cp .env.example .env       # tweak if your Ollama / MCP host differs

# Default prompt — asks the model to summarize cus_001's orders.
uv run python -m agent.main

# Custom prompt
uv run python -m agent.main "Which paid orders did cus_005 place?"
```

## Example output

```
[user] Summarize Acme Corp's order activity. Their customer id is cus_001.

[tool_call] get_customer_summary({customer_id=cus_001})

[tool_result] get_customer_summary: {"customer": {"id": "cus_001", "name": "Acme Corp", "plan": "enterprise", "signup_date": "2024-01-15"}, "total_orders": 4, "paid_orders": 3, "total_paid_cents": 245000}

[ai] Acme Corp (cus_001) has placed 4 orders total, 3 of which are paid for
a total of $2,450. One order was refunded.
```

## How it works

1. **MCP tool discovery.** `MultiServerMCPClient(...).get_tools()` connects to
   your MCP server, runs `tools/list`, and returns a list of LangChain
   `BaseTool` instances — one per MCP tool, with the JSON schemas you defined
   on the server side mapped to LangChain tool args.
2. **Model binding.** `create_react_agent(model, tools, prompt=...)` builds a
   small LangGraph state machine: model node → tool node → loop until the
   model returns a message with no tool calls.
3. **Tool execution.** When the model emits a tool call, LangGraph routes it
   back through the adapter, which calls `tools/call` on the MCP server. The
   result becomes a `ToolMessage` and gets fed back to the model.
4. **Final answer.** Loop exits when the model is done calling tools.

No code in this project knows what tools exist. Add a new tool to the MCP
server, restart the agent, and the model can use it immediately.

## Caveats with `qwen2.5:3b`

Small models do support tool calling — qwen2.5 instruct variants are tuned
for it — but at 3B parameters expect rough edges:

- **Misses easy tool calls.** The model may try to answer from training
  knowledge instead of calling `get_customer_summary` when it should. Mostly
  fixable with a sharper prompt; sometimes you just need a bigger model.
- **Hallucinated arguments.** Especially for `run_sql`. The guards on the
  server side catch most of this (parse failures, blocked statements), so
  the worst case is a tool error rather than a data leak.
- **Doesn't always stop.** Occasional loops where the model re-calls the same
  tool. LangGraph's `create_react_agent` has built-in step limits; you can
  also pass `recursion_limit` in the runtime config if you hit this.

If quality matters, try `qwen2.5:7b` or `qwen2.5:14b` — same tool-calling
contract, much better at choosing tools. The `.env` swap is the only change.

## Going further

- **Verbose protocol logging.** Set `LANGCHAIN_VERBOSE=true` or call
  `agent.astream(...)` instead of `ainvoke(...)` to watch each step as it
  happens.
- **Multiple MCP servers.** Add more entries to the `MultiServerMCPClient`
  dict in [agent/builder.py](agent/builder.py) — tool names from all servers
  get merged into one flat catalog the model sees.
- **Different model providers.** Swap `ChatOllama` for `ChatAnthropic`,
  `ChatOpenAI`, etc. in `_build_model()` — everything downstream is provider-
  neutral.
