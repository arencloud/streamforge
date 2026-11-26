-- Optional, server-wide setup for a self-managed PostgreSQL instance (psql).
-- Run as an administrator authorized to ALTER SYSTEM, outside a transaction.
-- For operator/managed databases, change the owning platform configuration instead.
-- This file does not create users/passwords, restart PostgreSQL, or change slot limits.
\set ON_ERROR_STOP on
ALTER SYSTEM SET wal_level = 'logical';
\echo 'Saved wal_level=logical. Restart PostgreSQL through its deployment manager.'
\echo 'Then reconnect, verify SHOW wal_level returns logical, and run 01-prepare-postgres.sql.'
