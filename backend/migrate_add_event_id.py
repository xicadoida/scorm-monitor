"""
Roda isso UMA VEZ no VPS, antes de reiniciar o serviço com o código novo.

Uso:
    cd ~/app/backend
    source ~/app/venv/bin/activate
    python migrate_add_event_id.py
"""

from sqlalchemy import text
from database import engine

with engine.connect() as conn:
    existing_columns = [
        row[1] for row in conn.execute(text("PRAGMA table_info(courses)"))
    ]

    if "event_id" in existing_columns:
        print("Coluna event_id já existe, nada a fazer.")
    else:
        conn.execute(text("ALTER TABLE courses ADD COLUMN event_id INTEGER"))
        conn.commit()
        print("Coluna event_id adicionada com sucesso.")