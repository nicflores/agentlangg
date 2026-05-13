from typing import Any

from server.db.registry import get_db


async def get_customer_tool(customer_id: str) -> dict[str, Any]:
    customer = await get_db().get_customer(customer_id)
    if customer is None:
        return {"error": f"Customer {customer_id!r} not found."}
    return customer.model_dump(mode="json")


async def get_customer_summary_tool(customer_id: str) -> dict[str, Any]:
    summary = await get_db().get_customer_summary(customer_id)
    if summary is None:
        return {"error": f"Customer {customer_id!r} not found."}
    return summary.model_dump(mode="json")
