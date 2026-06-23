-- Run once as postgres superuser: sudo -u postgres psql -f init-spoton.sql
-- Fixes "permission denied for schema public" on PostgreSQL 15+

CREATE USER spoton WITH PASSWORD 'change-me';
CREATE DATABASE spotoncleaning OWNER spoton;

\c spotoncleaning

ALTER SCHEMA public OWNER TO spoton;
GRANT ALL ON SCHEMA public TO spoton;
GRANT CREATE ON SCHEMA public TO spoton;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO spoton;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO spoton;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO spoton;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO spoton;
