"""Adiciona estados de arquivamento para preservar o histórico do LMS.

Execute explicitamente a partir de ``backend/`` antes de usar a versão que
arquiva contas, eventos e itens de frequência::

    python migrate_add_integrity_states.py

A migração é somente aditiva e idempotente. Registros legados permanecem
ativos; ela não altera matrículas, sessões, frequência nem arquivos SCORM.
"""

from sqlalchemy import inspect, text

from database import engine


ADDITIVE_COLUMNS = {
    "students": (
        ("active", "BOOLEAN NOT NULL DEFAULT 1"),
        ("deactivated_at", "DATETIME"),
    ),
    "courses": (("archived_at", "DATETIME"),),
    "events": (
        ("active", "BOOLEAN NOT NULL DEFAULT 1"),
        ("archived_at", "DATETIME"),
    ),
    "event_emails": (
        ("active", "BOOLEAN NOT NULL DEFAULT 1"),
        ("revoked_at", "DATETIME"),
    ),
    "attendance_modules": (
        ("active", "BOOLEAN NOT NULL DEFAULT 1"),
        ("archived_at", "DATETIME"),
    ),
    "attendance_module_parts": (
        ("active", "BOOLEAN NOT NULL DEFAULT 1"),
        ("archived_at", "DATETIME"),
    ),
}


def upgrade(bind=engine):
    """Aplica o esquema novo sem apagar ou reinterpretar dados legados."""

    inspector = inspect(bind)
    tables = set(inspector.get_table_names())
    missing_tables = set(ADDITIVE_COLUMNS) - tables
    if missing_tables:
        raise RuntimeError(
            "Migration stopped: missing required table(s): "
            + ", ".join(sorted(missing_tables))
        )

    added = []
    with bind.begin() as connection:
        for table, columns in ADDITIVE_COLUMNS.items():
            existing = {
                column["name"]
                for column in inspect(connection).get_columns(table)
            }
            for column, definition in columns:
                if column not in existing:
                    connection.execute(
                        text(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
                    )
                    added.append(f"{table}.{column}")

            # Bases SQLite legadas podem ter recebido NULL por ALTERs antigos.
            # A normalização é apenas para o novo estado técnico e não
            # forja confirmação de e-mail, presença ou conclusão.
            if any(column == "active" for column, _ in columns):
                connection.execute(text(f"UPDATE {table} SET active = 1 WHERE active IS NULL"))

        for table in (
            "students",
            "events",
            "event_emails",
            "attendance_modules",
            "attendance_module_parts",
        ):
            connection.execute(
                text(
                    f"CREATE INDEX IF NOT EXISTS ix_{table}_active_c006 "
                    f"ON {table} (active)"
                )
            )
        connection.execute(
            text("CREATE INDEX IF NOT EXISTS ix_courses_archived_at_c006 ON courses (archived_at)")
        )

    return {"added": added}


def main():
    result = upgrade()
    if result["added"]:
        print("Colunas de integridade criadas: " + ", ".join(result["added"]))
    else:
        print("Estados de integridade já estão disponíveis.")


if __name__ == "__main__":
    main()
