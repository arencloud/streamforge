-- Run as database owner with psql -v app_role=YOUR_EXISTING_APP_ROLE.
-- Creates no roles or credentials. Use only the dedicated synthetic showcase DB.
\set ON_ERROR_STOP on
BEGIN;
GRANT CONNECT ON DATABASE :"DBNAME" TO :"app_role";
GRANT USAGE ON SCHEMA public TO :"app_role";
GRANT SELECT, INSERT, UPDATE ON public.orders TO :"app_role";
COMMIT;
-- No DELETE, REPLICATION, sequence, DDL, or heartbeat privileges are required.
