"""Adiciona os campos do catálogo público a bancos SQLite existentes.

Execute este arquivo a partir da pasta backend, com a venv ativada.
"""
import sqlite3
from datetime import datetime


DB_PATH = "scorm_monitor.db"


def add_column_if_missing(cursor, table, column, definition):
    columns = {row[1] for row in cursor.execute(f"PRAGMA table_info({table})")}
    if column not in columns:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
        print(f"Coluna {table}.{column} criada.")
        return True
    else:
        print(f"Coluna {table}.{column} já existe.")
        return False


connection = sqlite3.connect(DB_PATH)
cursor = connection.cursor()

add_column_if_missing(cursor, "courses", "tool", "VARCHAR(255)")
add_column_if_missing(cursor, "courses", "duration_hours", "INTEGER")
add_column_if_missing(cursor, "courses", "catalog_url", "VARCHAR(500)")
add_column_if_missing(cursor, "courses", "thumbnail_url", "VARCHAR(500)")
add_column_if_missing(cursor, "courses", "short_description", "VARCHAR(500)")
catalog_status_was_added = add_column_if_missing(
    cursor, "courses", "catalog_status", "VARCHAR(30) DEFAULT 'active'"
)
add_column_if_missing(cursor, "courses", "updated_at", "DATETIME")

if catalog_status_was_added:
    # Preserva a interpretação que o LMS já usava: curso inativo entra no
    # catálogo como concluído; os demais começam como ativos.
    cursor.execute(
        "UPDATE courses SET catalog_status = "
        "CASE WHEN active = 0 THEN 'completed' ELSE 'active' END"
    )
else:
    cursor.execute("UPDATE courses SET catalog_status = 'active' WHERE catalog_status IS NULL")
cursor.execute("UPDATE courses SET updated_at = created_at WHERE updated_at IS NULL")
cursor.execute(
    "CREATE TABLE IF NOT EXISTS catalog_state (id INTEGER PRIMARY KEY, updated_at DATETIME NOT NULL)"
)
cursor.execute(
    "INSERT OR IGNORE INTO catalog_state (id, updated_at) VALUES (1, ?)",
    (datetime.utcnow().isoformat(),),
)

connection.commit()
connection.close()
print("Migração do catálogo concluída.")
