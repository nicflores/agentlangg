CREATE TABLE customers (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    plan TEXT NOT NULL,
    signup_date DATE NOT NULL
);

CREATE TABLE orders (
    id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL REFERENCES customers(id),
    amount_cents BIGINT NOT NULL,
    status TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX orders_customer_id_idx ON orders(customer_id);
CREATE INDEX orders_created_at_idx ON orders(created_at DESC);

-- Dedicated read-only role used by the run_sql escape hatch.
-- The main MCP service connects as mcp_user (read+write on schema, no DDL on system).
-- For full safety in production you'd swap the application user for this role
-- inside the run_sql code path. Here it's just available if you want to try it.
CREATE ROLE mcp_readonly NOLOGIN;
GRANT USAGE ON SCHEMA public TO mcp_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO mcp_readonly;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO mcp_readonly;
