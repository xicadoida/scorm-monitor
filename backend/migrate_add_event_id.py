"""
Roda isso UMA VEZ no VPS, antes de reiniciar o serviço com o código novo.

Uso:
    cd ~/app/backend
    source ~/app/venv/bin/activate
    python migrate_add_event_customization.py
"""

from sqlalchemy import text
from database import engine

NEW_COLUMNS = {
    "item_name": "VARCHAR(50)",
    "show_progress": "BOOLEAN DEFAULT 1",
    "show_footer": "BOOLEAN DEFAULT 0"
}

with engine.connect() as conn:
    existing_columns = [
        row[1] for row in conn.execute(text("PRAGMA table_info(events)"))
    ]

    for column, col_type in NEW_COLUMNS.items():
        if column in existing_columns:
            print(f"Coluna {column} já existe, pulando.")
            continue

        conn.execute(text(f"ALTER TABLE events ADD COLUMN {column} {col_type}"))
        conn.commit()
        print(f"Coluna {column} adicionada com sucesso.")