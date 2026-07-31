"""Adiciona a cor principal por curso em bancos SQLite já existentes."""

from sqlalchemy import text

from database import engine


with engine.connect() as conn:
    columns = [row[1] for row in conn.execute(text("PRAGMA table_info(courses)"))]

    if "color_primary" in columns:
        print("Coluna color_primary já existe, nada a fazer.")
    else:
        conn.execute(text("ALTER TABLE courses ADD COLUMN color_primary VARCHAR(20)"))
        conn.commit()
        print("Coluna color_primary adicionada com sucesso.")
