from server.tools.customers import get_customer_summary_tool, get_customer_tool
from server.tools.orders import get_customer_orders_tool


async def test_get_customer_returns_record() -> None:
    result = await get_customer_tool("cus_001")
    assert result["id"] == "cus_001"
    assert result["name"] == "Acme Corp"
    assert result["plan"] == "enterprise"


async def test_get_customer_unknown_id_returns_error_payload() -> None:
    result = await get_customer_tool("cus_does_not_exist")
    assert "error" in result
    assert "not found" in result["error"].lower()


async def test_get_customer_orders_returns_ordered_newest_first() -> None:
    result = await get_customer_orders_tool("cus_001")
    assert result["customer_id"] == "cus_001"
    assert result["count"] == len(result["orders"])
    timestamps = [o["created_at"] for o in result["orders"]]
    assert timestamps == sorted(timestamps, reverse=True)


async def test_get_customer_orders_clamps_limit() -> None:
    result = await get_customer_orders_tool("cus_005", limit=2)
    assert result["count"] == 2


async def test_get_customer_orders_lower_bounds_limit() -> None:
    # limit < 1 should clamp to 1, not raise
    result = await get_customer_orders_tool("cus_005", limit=0)
    assert result["count"] == 1


async def test_get_customer_summary_aggregates_paid_orders() -> None:
    result = await get_customer_summary_tool("cus_005")
    # Soylent has 4 paid orders summing to 950000 cents per the seed data.
    assert result["customer"]["id"] == "cus_005"
    assert result["total_orders"] == 4
    assert result["paid_orders"] == 4
    assert result["total_paid_cents"] == 200000 + 350000 + 180000 + 220000


async def test_get_customer_summary_excludes_non_paid_from_total() -> None:
    # cus_001 has 3 paid + 1 refunded; the refunded order should not contribute.
    result = await get_customer_summary_tool("cus_001")
    assert result["total_orders"] == 4
    assert result["paid_orders"] == 3
    assert result["total_paid_cents"] == 50000 + 75000 + 120000


async def test_get_customer_summary_handles_customer_with_no_orders() -> None:
    # cus_004 (Umbrella) has no orders in the seed data.
    result = await get_customer_summary_tool("cus_004")
    assert result["total_orders"] == 0
    assert result["paid_orders"] == 0
    assert result["total_paid_cents"] == 0
