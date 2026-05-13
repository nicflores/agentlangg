"""In-memory implementation of DatabaseClient.

The data here mirrors seed/002_seed.sql so the fake provider behaves the same
as the real one for the curated tools. ``run_select`` doesn't execute SQL —
it's not a real SQL engine — but it returns a deterministic stub payload so
the guard/parse pipeline stays exercised in tests.
"""

from datetime import date, datetime, timezone
from typing import Any

from server.db.base import Customer, CustomerSummary, DatabaseClient, Order


def _utc(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)


_CUSTOMERS: list[Customer] = [
    Customer(id="cus_001", name="Acme Corp",        plan="enterprise", signup_date=date(2024, 1, 15)),
    Customer(id="cus_002", name="Globex",           plan="pro",        signup_date=date(2024, 2, 20)),
    Customer(id="cus_003", name="Initech",          plan="pro",        signup_date=date(2024, 3, 10)),
    Customer(id="cus_004", name="Umbrella",         plan="free",       signup_date=date(2025, 1, 5)),
    Customer(id="cus_005", name="Soylent",          plan="enterprise", signup_date=date(2024, 6, 30)),
    Customer(id="cus_006", name="Hooli",            plan="pro",        signup_date=date(2024, 9, 12)),
    Customer(id="cus_007", name="Pied Piper",       plan="free",       signup_date=date(2025, 2, 1)),
    Customer(id="cus_008", name="Wonka Industries", plan="enterprise", signup_date=date(2024, 4, 22)),
]


_ORDERS: list[Order] = [
    Order(id="ord_001", customer_id="cus_001", amount_cents= 50000, status="paid",     created_at=_utc(2025, 1, 10, 14, 23)),
    Order(id="ord_002", customer_id="cus_001", amount_cents= 75000, status="paid",     created_at=_utc(2025, 2, 15,  9, 12)),
    Order(id="ord_003", customer_id="cus_001", amount_cents=120000, status="paid",     created_at=_utc(2025, 3, 22, 16, 45)),
    Order(id="ord_004", customer_id="cus_001", amount_cents= 30000, status="refunded", created_at=_utc(2025, 4,  1, 11, 30)),
    Order(id="ord_005", customer_id="cus_002", amount_cents= 15000, status="paid",     created_at=_utc(2025, 1, 25,  8,  0)),
    Order(id="ord_006", customer_id="cus_002", amount_cents= 25000, status="pending",  created_at=_utc(2025, 4, 18, 13, 22)),
    Order(id="ord_007", customer_id="cus_003", amount_cents= 40000, status="paid",     created_at=_utc(2025, 2,  5, 10, 15)),
    Order(id="ord_008", customer_id="cus_003", amount_cents= 60000, status="paid",     created_at=_utc(2025, 3, 18, 14,  0)),
    Order(id="ord_009", customer_id="cus_005", amount_cents=200000, status="paid",     created_at=_utc(2025, 1, 30,  9,  0)),
    Order(id="ord_010", customer_id="cus_005", amount_cents=350000, status="paid",     created_at=_utc(2025, 2, 28, 11,  0)),
    Order(id="ord_011", customer_id="cus_005", amount_cents=180000, status="paid",     created_at=_utc(2025, 3, 15, 15, 30)),
    Order(id="ord_012", customer_id="cus_005", amount_cents=220000, status="paid",     created_at=_utc(2025, 4, 22, 10, 45)),
    Order(id="ord_013", customer_id="cus_006", amount_cents= 35000, status="paid",     created_at=_utc(2025, 2, 10, 12,  0)),
    Order(id="ord_014", customer_id="cus_006", amount_cents= 45000, status="refunded", created_at=_utc(2025, 3,  5,  9, 30)),
    Order(id="ord_015", customer_id="cus_008", amount_cents=150000, status="paid",     created_at=_utc(2025, 1, 20, 14,  0)),
    Order(id="ord_016", customer_id="cus_008", amount_cents=175000, status="paid",     created_at=_utc(2025, 2, 25, 11, 15)),
    Order(id="ord_017", customer_id="cus_008", amount_cents=165000, status="pending",  created_at=_utc(2025, 4, 30, 13, 45)),
]


class FakePostgresClient:
    def __init__(self) -> None:
        self._customers = {c.id: c for c in _CUSTOMERS}
        self._orders = list(_ORDERS)

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None

    async def get_customer(self, customer_id: str) -> Customer | None:
        return self._customers.get(customer_id)

    async def get_customer_orders(self, customer_id: str, limit: int) -> list[Order]:
        rows = [o for o in self._orders if o.customer_id == customer_id]
        rows.sort(key=lambda o: o.created_at, reverse=True)
        return rows[:limit]

    async def get_customer_summary(self, customer_id: str) -> CustomerSummary | None:
        customer = await self.get_customer(customer_id)
        if customer is None:
            return None
        orders = [o for o in self._orders if o.customer_id == customer_id]
        paid = [o for o in orders if o.status == "paid"]
        return CustomerSummary(
            customer=customer,
            total_orders=len(orders),
            paid_orders=len(paid),
            total_paid_cents=sum(o.amount_cents for o in paid),
        )

    async def run_select(
        self, query: str, max_rows: int, timeout_ms: int
    ) -> list[dict[str, Any]]:
        # Fake provider doesn't execute SQL; return a deterministic stub so the
        # caller (and tests) can still verify the surrounding guard/parse path.
        return [
            {
                "note": "fake provider does not execute SQL",
                "query_preview": query[:120],
                "max_rows": max_rows,
                "timeout_ms": timeout_ms,
            }
        ]


_FAKE_CUSTOMERS = _CUSTOMERS
_FAKE_ORDERS = _ORDERS
