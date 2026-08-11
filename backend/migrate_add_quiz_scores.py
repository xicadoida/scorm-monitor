import sqlite3


DB_PATH = "scorm_monitor.db"


def add_column_if_missing(cursor, table, column, definition):
    columns = {row[1] for row in cursor.execute(f"PRAGMA table_info({table})")}
    if column not in columns:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
        print(f"Coluna {table}.{column} criada.")
    else:
        print(f"Coluna {table}.{column} já existe.")


connection = sqlite3.connect(DB_PATH)
cursor = connection.cursor()
add_column_if_missing(cursor, "courses", "passing_score", "INTEGER DEFAULT 80")
add_column_if_missing(cursor, "course_sessions", "score_raw", "INTEGER")
connection.commit()
connection.close()
print("Migração de notas concluída.")
