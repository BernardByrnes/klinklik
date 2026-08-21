-- Development-only role setup. The application-role password is supplied by the
-- local POSTGRES_APP_PASSWORD environment variable through 001-init.sh.
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'clinicopus_app') THEN
        CREATE ROLE clinicopus_app LOGIN PASSWORD :'app_password' NOSUPERUSER NOBYPASSRLS;
    END IF;
END
$$;

GRANT CONNECT ON DATABASE clinicopus TO clinicopus_app;
GRANT USAGE ON SCHEMA public TO clinicopus_app;
ALTER DEFAULT PRIVILEGES FOR ROLE clinicopus_owner IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO clinicopus_app;
ALTER DEFAULT PRIVILEGES FOR ROLE clinicopus_owner IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO clinicopus_app;
