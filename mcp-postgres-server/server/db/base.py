from datetime import date, datetime
from typing import Any, Protocol

from pydantic import BaseModel


class Customer(BaseModel):
    id: str
    name: str
    plan: str
    signup_date: date


class Order(BaseModel):
    id: str
    customer_id: str
    amount_cents: int
    status: str
    created_at: datetime


class CustomerSummary(BaseModel):
    customer: Customer
    total_orders: int
    paid_orders: int
    total_paid_cents: int


class DatabaseClient(Protocol):
    async def start(self) -> None: ...

    async def stop(self) -> None: ...

    async def get_customer(self, customer_id: str) -> Customer | None: ...

    async def get_customer_orders(
        self, customer_id: str, limit: int
    ) -> list[Order]: ...

    async def get_customer_summary(
        self, customer_id: str
    ) -> CustomerSummary | None: ...

    async def run_select(
        self, query: str, max_rows: int, timeout_ms: int
    ) -> list[dict[str, Any]]: ...
