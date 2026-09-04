"""Cria a tabela de tokens seguros de recupera\u00e7\u00e3o de senha."""
from sqlalchemy import text

from database import engine


def main():
    with engine.begin() as connection:
        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS password_reset_tokens (
                id INTEGER PRIMARY KEY,
                student_code VARCHAR(100) NOT NULL,
                token_hash VARCHAR(64) NOT NULL UNIQUE,
                expires_at DATETIME NOT NULL,
                used_at DATETIME,
                created_at DATETIME NOT NULL
            )
        """))
        for name, column in [
            ("ix_password_reset_tokens_student_code", "student_code"),
            ("ix_password_reset_tokens_expires_at", "expires_at"),
            ("ix_password_reset_tokens_used_at", "used_at"),
            ("ix_password_reset_tokens_created_at", "created_at"),
        ]:
            connection.execute(text(
                f"CREATE INDEX IF NOT EXISTS {name} ON password_reset_tokens ({column})"
            ))
    print("Tabela password_reset_tokens pronta.")


if __name__ == "__main__":
    main()
