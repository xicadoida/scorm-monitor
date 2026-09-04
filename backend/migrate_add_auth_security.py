"""Adiciona versão de sessão para invalidar tokens após troca de senha."""
import sqlite3


connection = sqlite3.connect("scorm_monitor.db")
cursor = connection.cursor()
columns = {row[1] for row in cursor.execute("PRAGMA table_info(students)")}

if "auth_token_version" not in columns:
    cursor.execute("ALTER TABLE students ADD COLUMN auth_token_version INTEGER NOT NULL DEFAULT 0")
    print("Coluna students.auth_token_version criada.")
else:
    print("Coluna students.auth_token_version já existe.")

connection.commit()
connection.close()
print("Migração de segurança concluída.")
