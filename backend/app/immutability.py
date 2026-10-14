"""Database guards preserve append-only financial and decision evidence."""


def install_guards(connection):
    dialect = connection.dialect.name
    for table in ("audit_logs", "ledger_entries"):
        if dialect == "sqlite":
            for operation in ("UPDATE", "DELETE"):
                connection.exec_driver_sql(
                    f"CREATE TRIGGER IF NOT EXISTS {table}_no_{operation.lower()} BEFORE {operation} ON {table} BEGIN SELECT RAISE(ABORT, 'append-only table'); END"
                )
        elif dialect == "postgresql":
            connection.exec_driver_sql(
                "CREATE OR REPLACE FUNCTION aegis_append_only() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'append-only table'; END $$"
            )
            connection.exec_driver_sql(
                f"DROP TRIGGER IF EXISTS {table}_immutable ON {table}"
            )
            connection.exec_driver_sql(
                f"CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION aegis_append_only()"
            )
