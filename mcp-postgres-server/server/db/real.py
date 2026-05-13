from typing import Any

import asyncpg

from server.config import settings
from server.db.base import Customer, CustomerSummary, Order
from server.utils.tracing import trace_event


class AsyncpgClient:
    def __init__(self) -> None:
        self._pool: asyncpg.Pool | None = None

    async def start(self) -> None:
        self._pool = await asyncpg.create_pool(
            host=settings.postgres_host,
            port=settings.postgres_port,
            user=settings.postgres_user,
            password=settings.postgres_password,
            database=settings.postgres_db,
            min_size=settings.postgres_pool_min_size,
            max_size=settings.postgres_pool_max_size,
        )
        trace_event(
            "db_pool_started",
            host=settings.postgres_host,
            database=settings.postgres_db,
        )

    async def stop(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None
            trace_event("db_pool_stopped")

    def _require_pool(self) -> asyncpg.Pool:
        if self._pool is None:
            raise RuntimeError(
                "Postgres pool is not initialized. Lifespan didn't start, or start() wasn't awaited."
            )
        return self._pool

    async def get_customer(self, customer_id: str) -> Customer | None:
        pool = self._require_pool()
        row = await pool.fetchrow(
            "SELECT id, name, plan, signup_date FROM customers WHERE id = $1",
            customer_id,
        )
        return Customer(**dict(row)) if row else None

    async def get_customer_orders(self, customer_id: str, limit: int) -> list[Order]:
        pool = self._require_pool()
        rows = await pool.fetch(
            """
            SELECT id, customer_id, amount_cents, status, created_at
            FROM orders
            WHERE customer_id = $1
            ORDER BY created_at DESC
            LIMIT $2
            """,
            customer_id,
            limit,
        )
        return [Order(**dict(r)) for r in rows]

    async def get_customer_summary(self, customer_id: str) -> CustomerSummary | None:
        pool = self._require_pool()
        async with pool.acquire() as conn:
            customer_row = await conn.fetchrow(
                "SELECT id, name, plan, signup_date FROM customers WHERE id = $1",
                customer_id,
            )
            if customer_row is None:
                return None

            summary_row = await conn.fetchrow(
                """
                SELECT
                    COUNT(*)                                        AS total_orders,
                    COUNT(*) FILTER (WHERE status = 'paid')         AS paid_orders,
                    COALESCE(
                        SUM(amount_cents) FILTER (WHERE status = 'paid'),
                        0
                    )                                               AS total_paid_cents
                FROM orders
                WHERE customer_id = $1
                """,
                customer_id,
            )
            return CustomerSummary(
                customer=Customer(**dict(customer_row)),
                total_orders=summary_row["total_orders"],
                paid_orders=summary_row["paid_orders"],
                total_paid_cents=summary_row["total_paid_cents"],
            )

    async def run_select(
        self, query: str, max_rows: int, timeout_ms: int
    ) -> list[dict[str, Any]]:
        pool = self._require_pool()
        async with pool.acquire() as conn:
            # Read-only transaction + per-statement timeout via SET LOCAL.
            async with conn.transaction(readonly=True):
                await conn.execute(f"SET LOCAL statement_timeout = {int(timeout_ms)}")
                rows = await conn.fetch(query)
        # max_rows is enforced via LIMIT injection upstream; capping defensively.
        return [dict(r) for r in rows[:max_rows]]
