"""The ``run_sql`` escape hatch.

Read-only SELECTs only. The guards live here, in the tool layer, so they apply
identically against the fake provider (tests) and the real Postgres connection.

Layered checks, in order:

1. Parse with sqlglot (Postgres dialect). Reject if it doesn't parse cleanly.
2. Require exactly one statement.
3. Reject any node in the tree that's DDL/DML or an unparsed ``Command``
   (GRANT/REVOKE/VACUUM/etc.).
4. Require the top-level expression to be a SELECT or set operation of SELECTs.
5. Require any schema-qualified table reference to be in the allow-list.
6. Inject LIMIT if absent; cap an existing LIMIT at ``max_rows``.
7. Require a non-empty ``justification`` argument (the audit trail).

Only after all of those pass do we hand the rewritten SQL to the db client,
which runs it inside a read-only transaction with ``SET LOCAL statement_timeout``.
"""

from typing import Any

import sqlglot
from sqlglot import exp

from server.config import settings
from server.db.registry import get_db
from server.utils.tracing import trace_event

DENIED_EXPRESSION_TYPES: tuple[type[exp.Expression], ...] = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Merge,
    exp.Create,
    exp.Drop,
    exp.Alter,
    exp.TruncateTable,
    exp.Copy,
    exp.Command,  # catch-all for unparsed statements (GRANT, REVOKE, VACUUM, ...)
)


class RunSqlError(Exception):
    pass


def _validate_select_only(parsed: exp.Expression) -> None:
    for denied in DENIED_EXPRESSION_TYPES:
        node = parsed.find(denied)
        if node is not None:
            raise RunSqlError(
                f"{type(node).__name__.upper()} statements are not allowed; "
                "run_sql is read-only."
            )

    if not isinstance(parsed, (exp.Select, exp.Union, exp.Intersect, exp.Except)):
        raise RunSqlError(
            f"Only SELECT queries are allowed; got {type(parsed).__name__}."
        )


def _validate_schemas(parsed: exp.Expression, allowed: tuple[str, ...]) -> None:
    allowed_lower = {s.lower() for s in allowed}
    for table in parsed.find_all(exp.Table):
        schema = table.args.get("db")
        if schema is None:
            continue  # unqualified — defaults to search_path, which is `public`
        if schema.name.lower() not in allowed_lower:
            raise RunSqlError(
                f"Schema {schema.name!r} is not in the allow-list "
                f"(allowed: {sorted(allowed)})."
            )


def _inject_or_cap_limit(
    parsed: exp.Expression, default_limit: int, max_rows: int
) -> exp.Expression:
    existing = parsed.args.get("limit")
    if existing is None:
        parsed.set("limit", exp.Limit(expression=exp.Literal.number(default_limit)))
        return parsed

    inner = existing.expression
    if isinstance(inner, exp.Literal) and inner.is_int and int(inner.name) > max_rows:
        parsed.set("limit", exp.Limit(expression=exp.Literal.number(max_rows)))
    return parsed


async def run_sql_tool(
    query: str,
    max_rows: int | None = None,
    justification: str = "",
) -> dict[str, Any]:
    if not justification or not justification.strip():
        return {
            "error": (
                "`justification` is required: describe (in one sentence) why a "
                "curated tool isn't sufficient. Audit logs record this."
            )
        }

    if max_rows is None or max_rows < 1 or max_rows > settings.run_sql_max_rows:
        max_rows = settings.run_sql_max_rows

    try:
        statements = sqlglot.parse(query, dialect="postgres")
    except sqlglot.errors.ParseError as exc:
        return {"error": f"Failed to parse SQL: {exc}"}

    statements = [s for s in statements if s is not None]
    if not statements:
        return {"error": "Query is empty."}
    if len(statements) > 1:
        return {"error": "Multi-statement queries are not allowed."}

    parsed = statements[0]

    try:
        _validate_select_only(parsed)
        _validate_schemas(parsed, settings.run_sql_allowed_schemas)
    except RunSqlError as exc:
        trace_event(
            "run_sql_rejected",
            reason=str(exc),
            justification=justification,
            query_preview=query[:200],
        )
        return {"error": str(exc)}

    rewritten = _inject_or_cap_limit(
        parsed,
        default_limit=settings.run_sql_default_limit,
        max_rows=max_rows,
    ).sql(dialect="postgres")

    trace_event(
        "run_sql_executed",
        justification=justification,
        rewritten_preview=rewritten[:200],
        max_rows=max_rows,
    )

    rows = await get_db().run_select(
        rewritten,
        max_rows,
        settings.run_sql_statement_timeout_ms,
    )
    return {
        "rewritten_query": rewritten,
        "row_count": len(rows),
        "rows": rows,
    }
