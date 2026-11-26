-- Run as the database owner in the dedicated showcase database (psql).
-- Supply the existing least-privilege replication role: -v cdc_role=streamforge_cdc
-- Set its password through your provisioning system/Vault, never through this file.
\set ON_ERROR_STOP on
-- wal_level is a server-wide startup setting, not a per-database setting.
-- If needed, an administrator runs 00-enable-logical-wal.sql separately, then
-- restarts PostgreSQL through its deployment manager before running this file.
-- For operator/managed databases, set wal_level in the owning platform config.
DO $preflight$
BEGIN
    IF current_setting('wal_level') <> 'logical' THEN
        RAISE EXCEPTION 'wal_level is %, but Debezium requires logical', current_setting('wal_level')
            USING HINT = 'As a PostgreSQL administrator, run ALTER SYSTEM SET wal_level = ''logical''; or update the owning platform configuration. Restart PostgreSQL, verify SHOW wal_level returns logical, then rerun this script. A reload alone is insufficient.';
    END IF;
END
$preflight$;

BEGIN;
CREATE TABLE IF NOT EXISTS public.orders (
    id bigint PRIMARY KEY,
    customer_name text NOT NULL,
    amount numeric(12,2) NOT NULL,
    status text NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE public.orders REPLICA IDENTITY FULL;
CREATE TABLE IF NOT EXISTS public.streamforge_heartbeat (
    id integer PRIMARY KEY CHECK (id=1), ts timestamptz NOT NULL
);
INSERT INTO public.streamforge_heartbeat VALUES (1, now()) ON CONFLICT (id) DO NOTHING;
GRANT CONNECT ON DATABASE :"DBNAME" TO :"cdc_role";
GRANT USAGE ON SCHEMA public TO :"cdc_role";
GRANT SELECT ON public.orders TO :"cdc_role";
GRANT SELECT, UPDATE ON public.streamforge_heartbeat TO :"cdc_role";
-- This is intentionally explicit. Do not publish ALL TABLES.
-- Preserve an existing publication when rerunning after WAL configuration.
DO $publication$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_publication WHERE pubname = 'streamforge_orders') THEN
        CREATE PUBLICATION streamforge_orders
            FOR TABLE public.orders, public.streamforge_heartbeat;
    END IF;
END
$publication$;
COMMIT;
-- DBA prerequisites: wal_level=logical; role LOGIN REPLICATION; available
-- max_replication_slots/max_wal_senders; a bounded max_slot_wal_keep_size.
-- The connector creates its durable pgoutput slot on first start.
