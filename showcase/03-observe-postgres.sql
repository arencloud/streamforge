-- Read-only, run by a monitoring/DBA role with visibility into replication slots.
SELECT slot_name, active, restart_lsn, confirmed_flush_lsn,
       pg_size_pretty(pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn)) AS retained_wal,
       wal_status, safe_wal_size
FROM pg_replication_slots WHERE slot_name='streamforge_orders';
SELECT pubname, schemaname, tablename FROM pg_publication_tables
WHERE pubname='streamforge_orders';
