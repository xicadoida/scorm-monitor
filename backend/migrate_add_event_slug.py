"""Adiciona o slug público dos eventos em bancos SQLite existentes."""

from sqlalchemy import text

from database import engine


with engine.connect() as conn:
    columns = [row[1] for row in conn.execute(text("PRAGMA table_info(events)"))]
    if "slug" in columns:
        print("Coluna slug já existe, nada a fazer.")
    else:
        conn.execute(text("ALTER TABLE events ADD COLUMN slug VARCHAR(100)"))
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_events_slug ON events (slug)"))
        conn.commit()
        print("Coluna slug adicionada com sucesso.")
