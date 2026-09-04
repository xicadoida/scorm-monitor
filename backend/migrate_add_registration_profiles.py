"""Cria perfis de inscrição PF/PJ e preserva contas existentes sem forjar aceite."""
import sqlite3


connection = sqlite3.connect("scorm_monitor.db")
cursor = connection.cursor()

cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS registration_profiles (
        id INTEGER PRIMARY KEY,
        student_code VARCHAR(100) NOT NULL UNIQUE,
        person_type VARCHAR(20) NOT NULL DEFAULT 'not_informed',
        accepted_terms_at DATETIME,
        accepted_terms_url VARCHAR(500),
        event_id INTEGER,
        created_at DATETIME,
        updated_at DATETIME
    )
    """
)
cursor.execute("CREATE INDEX IF NOT EXISTS ix_registration_profiles_person_type ON registration_profiles (person_type)")
cursor.execute("CREATE INDEX IF NOT EXISTS ix_registration_profiles_event_id ON registration_profiles (event_id)")

# Contas antigas não recebem um aceite fictício: ficam como not_informed e
# accepted_terms_at NULL, preservando a realidade histórica dos dados.
cursor.execute(
    """
    INSERT OR IGNORE INTO registration_profiles
        (student_code, person_type, accepted_terms_at, accepted_terms_url, event_id, created_at, updated_at)
    SELECT student_code, 'not_informed', NULL, NULL, NULL, created_at, created_at
    FROM students
    """
)

connection.commit()
connection.close()
print("Migração de perfis de inscrição concluída.")
