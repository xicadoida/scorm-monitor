"""Cria a tabela de auditoria anonimizando IPs por HMAC no app."""
import sqlite3


connection = sqlite3.connect("scorm_monitor.db")
cursor = connection.cursor()
cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS access_events (
        id INTEGER PRIMARY KEY,
        event_type VARCHAR(50) NOT NULL,
        success BOOLEAN NOT NULL DEFAULT 1,
        student_code VARCHAR(100),
        event_id INTEGER,
        ip_hash VARCHAR(64),
        user_agent VARCHAR(500),
        route VARCHAR(255),
        created_at DATETIME NOT NULL
    )
    """
)
for name, expression in (
    ("ix_access_events_event_type", "event_type"),
    ("ix_access_events_success", "success"),
    ("ix_access_events_student_code", "student_code"),
    ("ix_access_events_event_id", "event_id"),
    ("ix_access_events_ip_hash", "ip_hash"),
    ("ix_access_events_created_at", "created_at"),
):
    cursor.execute(f"CREATE INDEX IF NOT EXISTS {name} ON access_events ({expression})")

connection.commit()
connection.close()
print("Migração de auditoria de acessos concluída.")
