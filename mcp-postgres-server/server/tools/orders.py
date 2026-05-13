from typing import Any

from server.db.registry import get_db


async def get_customer_orders_tool(customer_id: str, limit: int = 20) -> dict[str, Any]:
    limit = max(1, min(limit, 200))
    orders = await get_db().get_customer_orders(customer_id, limit)
    return {
        "customer_id": customer_id,
        "count": len(orders),
        "orders": [o.model_dump(mode="json") for o in orders],
    }
