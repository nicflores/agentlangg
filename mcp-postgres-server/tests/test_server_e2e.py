"""End-to-end checks against the FastMCP server.

These don't spin up the streamable-HTTP transport. Instead they go through
``FastMCP.list_tools()`` / ``call_tool()``, which is the layer the protocol
maps onto — proving the decorators and the lifespan-managed DB are wired up
correctly without paying transport cost.

For real wire-level checks, run the server (``uv run python -m server.main``)
and point the MCP Inspector at it (see README).
"""

from server.main import mcp


async def test_server_registers_all_tools() -> None:
    tools = await mcp.list_tools()
    names = {t.name for t in tools}
    expected = {
        "get_customer",
        "get_customer_orders",
        "get_customer_summary",
        "run_sql",
    }
    assert expected <= names, f"Missing tools: {expected - names}"


async def test_tool_schemas_capture_arguments() -> None:
    tools = await mcp.list_tools()
    by_name = {t.name: t for t in tools}

    customer_schema = by_name["get_customer"].inputSchema
    assert "customer_id" in customer_schema["properties"]
    assert "customer_id" in customer_schema.get("required", [])

    orders_schema = by_name["get_customer_orders"].inputSchema
    assert "customer_id" in orders_schema["properties"]
    assert "limit" in orders_schema["properties"]

    run_sql_schema = by_name["run_sql"].inputSchema
    for arg in ("query", "max_rows", "justification"):
        assert arg in run_sql_schema["properties"]


async def test_run_sql_description_flags_it_as_escape_hatch() -> None:
    tools = await mcp.list_tools()
    by_name = {t.name: t for t in tools}
    assert "escape hatch" in by_name["run_sql"].description.lower()


async def test_call_tool_get_customer_returns_record() -> None:
    # FastMCP.call_tool returns (content_blocks, structured_dict). Use structured.
    _, structured = await mcp.call_tool("get_customer", {"customer_id": "cus_001"})
    assert structured["id"] == "cus_001"
    assert structured["name"] == "Acme Corp"


async def test_call_tool_run_sql_rejects_drop() -> None:
    _, structured = await mcp.call_tool(
        "run_sql",
        {"query": "DROP TABLE customers", "justification": "testing"},
    )
    assert "error" in structured
    assert "not allowed" in structured["error"].lower()
