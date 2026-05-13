# mcp-postgres-server

A Postgres-backed MCP server. Exposes a small set of **curated tools** for the
common access patterns and a **guarded `run_sql` escape hatch** for the cases
the curated tools don't cover.

Built as a learning-focused first iteration before layering on a gateway and
auth. The MCP backend is deliberately a real service speaking real MCP over
streamable HTTP — only Postgres itself is swappable for an in-memory fake.

## Layout

```
mcp-postgres-server/
├── docker-compose.yml          # local Postgres + seed
├── seed/{001_schema,002_seed}.sql
├── server/
│   ├── main.py                 # FastMCP entrypoint
│   ├── config.py               # pydantic-settings, *_PROVIDER toggle
│   ├── db/{base,fake,real,registry}.py
│   └── tools/{customers,orders,run_sql}.py
└── tests/                      # 28 pytest cases
```

## Running locally

### 1. Install

```bash
uv sync
cp .env.example .env
```

### 2a. Run against the fake provider (no Docker needed)

The fake DB has the same seed data as the SQL seed, so curated tools return
realistic results immediately.

```bash
# Default is already DB_PROVIDER=fake
uv run python -m server.main
```

The server listens on `http://127.0.0.1:8000/mcp` (streamable HTTP).

### 2b. Run against real Postgres

```bash
docker compose up -d              # start Postgres on :5432
# Wait a few seconds for the seed to apply
docker compose logs postgres | tail

# Flip the provider in .env:
#   DB_PROVIDER=real
uv run python -m server.main
```

## Tools exposed

| Tool | Purpose |
|---|---|
| `get_customer(customer_id)` | Curated. One customer row. |
| `get_customer_orders(customer_id, limit=20)` | Curated. Recent orders, newest first. |
| `get_customer_summary(customer_id)` | Curated. Customer + aggregates (total/paid/sum). |
| `run_sql(query, max_rows=100, justification)` | Escape hatch. SELECT only, guarded. |

### `run_sql` guards

In order, in [server/tools/run_sql.py](server/tools/run_sql.py):

1. Parse with `sqlglot` (Postgres dialect). Parse failures rejected.
2. Single statement only — multi-statement queries rejected.
3. DDL/DML/Commands rejected by AST node type (`Insert`, `Update`, `Delete`,
   `Create`, `Drop`, `Alter`, `TruncateTable`, `Merge`, `Copy`, `Command`).
4. Top-level expression must be `Select`, `Union`, `Intersect`, or `Except`.
5. Schema-qualified table references must be in the allow-list
   (default: `public`).
6. `LIMIT` is injected if absent; an existing `LIMIT` is capped at `max_rows`,
   which is itself capped at the server-wide `RUN_SQL_MAX_ROWS`.
7. `justification` argument required and logged — agents have to explain why
   the curated tools weren't enough.

At execution time, the query runs inside a read-only transaction with
`SET LOCAL statement_timeout` set per `RUN_SQL_STATEMENT_TIMEOUT_MS`.

## Inspecting it interactively

The official MCP Inspector is the easiest way to poke this manually:

```bash
# In one terminal:
uv run python -m server.main

# In another:
npx @modelcontextprotocol/inspector
# Then in the UI: Transport=streamable-http, URL=http://127.0.0.1:8000/mcp
```

You'll get tool listing, schema preview, and a click-to-call interface.

## Running tests

```bash
uv run pytest
```

28 tests, all running against the fake provider. Two layers of coverage:

- `tests/test_curated_tools.py` — each curated tool returns the expected shape
  and aggregates correctly.
- `tests/test_run_sql_guards.py` — each guard rejects what it should and
  passes what it should.
- `tests/test_server_e2e.py` — FastMCP registers the tools, exposes correct
  JSON schemas, and `call_tool()` round-trips through the protocol layer.

## What's deliberately *not* here (yet)

- **Auth.** Anyone who can reach the port can call any tool. The next iteration
  adds a gateway in front that does bearer-token auth and per-team policy.
- **Audit log persistence.** `trace_event` writes structured JSON to stderr —
  fine for local dev, not a compliance trail. The gateway is the right place
  to centralize this.
- **Rate limiting / cost ceilings.** Same — gateway concern.
- **Connection-per-caller / row-level security.** Service-account model only.
  See the "service account vs identity federation" discussion in the design
  notes; we'd revisit this when row-level security becomes relevant.

## Adding a new curated tool

1. Add the data-access method to `server/db/base.py:DatabaseClient` (Protocol).
2. Implement it in both `server/db/fake.py:FakePostgresClient` (seeded data)
   and `server/db/real.py:AsyncpgClient` (SQL).
3. Add a thin function in `server/tools/<area>.py` that calls
   `get_db().<method>(...)` and returns a JSON-serializable dict.
4. Decorate it in `server/main.py` with `@mcp.tool()`. The docstring becomes
   the tool description; the type hints become the JSON schema.
5. Write tests in `tests/test_curated_tools.py`.

Five steps and four files — keeping the protocol/transport layer untouched.

## Configuration

All config in [server/config.py](server/config.py), backed by `.env` via
`pydantic-settings`. Key knobs:

| Env var | Default | Purpose |
|---|---|---|
| `DB_PROVIDER` | `fake` | `fake` (in-memory) or `real` (Postgres) |
| `POSTGRES_HOST/PORT/USER/PASSWORD/DB` | localhost/5432/mcp_user/mcp_password/mcp_db | Real provider connection |
| `MCP_HOST` / `MCP_PORT` | `127.0.0.1` / `8000` | Server bind address |
| `RUN_SQL_DEFAULT_LIMIT` | `100` | Auto-injected LIMIT when absent |
| `RUN_SQL_MAX_ROWS` | `1000` | Hard ceiling on `LIMIT` |
| `RUN_SQL_STATEMENT_TIMEOUT_MS` | `5000` | Per-query timeout |
