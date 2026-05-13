from contextlib import asynccontextmanager
from typing import Any

from mcp.server.fastmcp import FastMCP

from server.config import settings
from server.db.registry import get_db
from server.tools.customers import get_customer_summary_tool, get_customer_tool
from server.tools.orders import get_customer_orders_tool
from server.tools.run_sql import run_sql_tool
from server.utils.tracing import trace_event


@asynccontextmanager
async def lifespan(_: FastMCP):
    db = get_db()
    await db.start()
    trace_event("server_start", db_provider=settings.db_provider)
    try:
        yield
    finally:
        await db.stop()
        trace_event("server_stop")


mcp = FastMCP(
    "postgres-data",
    instructions=(
        "Read-only access to a Postgres database of customers and orders. "
        "Prefer the curated tools (get_customer, get_customer_orders, "
        "get_customer_summary) for known patterns. Use run_sql only when no "
        "curated tool fits — it's audited, SELECT-only, schema-allowlisted, "
        "and LIMIT-capped."
    ),
    lifespan=lifespan,
    host=settings.mcp_host,
    port=settings.mcp_port,
)


@mcp.tool()
async def get_customer(customer_id: str) -> dict[str, Any]:
    """Return a single customer record by id (e.g. ``cus_001``)."""
    return await get_customer_tool(customer_id)


@mcp.tool()
async def get_customer_orders(customer_id: str, limit: int = 20) -> dict[str, Any]:
    """List the customer's recent orders, newest first (limit 1-200)."""
    return await get_customer_orders_tool(customer_id, limit)


@mcp.tool()
async def get_customer_summary(customer_id: str) -> dict[str, Any]:
    """Customer record plus aggregate stats (total_orders, paid_orders, total_paid_cents)."""
    return await get_customer_summary_tool(customer_id)


@mcp.tool()
async def run_sql(
    query: str,
    max_rows: int = 100,
    justification: str = "",
) -> dict[str, Any]:
    """Run a read-only SELECT against the database (escape hatch).

    SELECT only — DDL/DML are rejected. Multi-statement queries are rejected.
    Schema references must be in the server's allow-list. A LIMIT is auto-
    applied or capped at ``max_rows`` (capped again at the server ceiling).
    Statement timeout is enforced inside a read-only transaction.

    ``justification`` is required and goes into audit logs. Prefer a curated
    tool whenever one fits.
    """
    return await run_sql_tool(query, max_rows=max_rows, justification=justification)


def main() -> None:
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
