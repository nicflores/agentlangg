from server.tools.run_sql import run_sql_tool


async def test_requires_justification() -> None:
    result = await run_sql_tool("SELECT 1")
    assert "error" in result
    assert "justification" in result["error"].lower()


async def test_blank_justification_rejected() -> None:
    result = await run_sql_tool("SELECT 1", justification="   ")
    assert "error" in result
    assert "justification" in result["error"].lower()


async def test_rejects_drop() -> None:
    result = await run_sql_tool("DROP TABLE customers", justification="testing")
    assert "error" in result
    assert "not allowed" in result["error"].lower()


async def test_rejects_insert() -> None:
    result = await run_sql_tool(
        "INSERT INTO customers (id, name, plan, signup_date) "
        "VALUES ('x', 'X', 'free', '2025-01-01')",
        justification="testing",
    )
    assert "error" in result


async def test_rejects_update() -> None:
    result = await run_sql_tool(
        "UPDATE customers SET plan = 'pro' WHERE id = 'cus_001'",
        justification="testing",
    )
    assert "error" in result


async def test_rejects_delete() -> None:
    result = await run_sql_tool(
        "DELETE FROM orders WHERE status = 'pending'",
        justification="testing",
    )
    assert "error" in result


async def test_rejects_multi_statement() -> None:
    result = await run_sql_tool("SELECT 1; SELECT 2;", justification="testing")
    assert "error" in result
    assert "multi-statement" in result["error"].lower()


async def test_rejects_parse_failure() -> None:
    result = await run_sql_tool("SELECT FROM WHERE", justification="testing")
    assert "error" in result


async def test_rejects_unknown_schema() -> None:
    result = await run_sql_tool(
        "SELECT * FROM secret_schema.customers",
        justification="testing",
    )
    assert "error" in result
    assert "schema" in result["error"].lower()


async def test_allows_public_schema_qualified() -> None:
    result = await run_sql_tool(
        "SELECT id FROM public.customers",
        justification="testing",
    )
    assert "error" not in result
    assert result["row_count"] >= 1


async def test_allows_unqualified_table() -> None:
    result = await run_sql_tool("SELECT id FROM customers", justification="testing")
    assert "error" not in result


async def test_injects_default_limit_when_absent() -> None:
    result = await run_sql_tool("SELECT id FROM customers", justification="testing")
    rewritten = result["rewritten_query"].upper()
    assert "LIMIT" in rewritten


async def test_caps_excessive_limit() -> None:
    result = await run_sql_tool(
        "SELECT id FROM customers LIMIT 999999",
        max_rows=100,
        justification="testing",
    )
    rewritten = result["rewritten_query"].upper()
    assert "LIMIT 100" in rewritten
    assert "LIMIT 999999" not in rewritten


async def test_allows_cte_with_select() -> None:
    result = await run_sql_tool(
        "WITH paid AS (SELECT id FROM orders WHERE status = 'paid') "
        "SELECT * FROM paid",
        justification="testing",
    )
    assert "error" not in result


async def test_allows_union_of_selects() -> None:
    result = await run_sql_tool(
        "SELECT id FROM customers UNION SELECT customer_id FROM orders",
        justification="testing",
    )
    assert "error" not in result
