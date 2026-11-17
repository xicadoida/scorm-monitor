"""Add the secure email-verification and event-membership data structures.

Run from ``backend/``::

    python migrate_add_email_verification.py

The migration intentionally does not mark existing accounts as verified and
does not create retroactive event memberships. Email ownership must be proved
after this update.
"""

from sqlalchemy import inspect, text

from database import engine
from models import EmailVerificationToken, EventMembership, Student


def _create_indexes(bind, table):
    """Create model indexes, including after a column was added by ALTER."""
    if table.name == "students" and bind.dialect.name == "sqlite":
        # SQLite nao reflete indice por expressao e emite aviso ao inspecionar
        # qualquer indice da tabela. Estes sao os dois unicos indices novos
        # necessarios para um banco legado; os demais ja existiam no modelo.
        with bind.begin() as connection:
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_students_email_verified_at "
                    "ON students (email_verified_at)"
                )
            )
            connection.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS "
                    "uq_students_email_normalized "
                    "ON students (LOWER(TRIM(email)))"
                )
            )
        return
    for index in table.indexes:
        index.create(bind=bind, checkfirst=True)


def _case_insensitive_duplicate_student_email_groups(bind):
    """Count emails that would be ambiguous after login normalization."""
    with bind.connect() as connection:
        return connection.execute(
            text(
                """
                SELECT COUNT(*)
                FROM (
                    SELECT LOWER(TRIM(email)) AS normalized_email
                    FROM students
                    WHERE email IS NOT NULL
                    GROUP BY LOWER(TRIM(email))
                    HAVING COUNT(*) > 1
                ) AS duplicate_emails
                """
            )
        ).scalar_one()


def upgrade(bind=engine):
    """Apply the additive migration idempotently without changing old data."""
    inspector = inspect(bind)
    if "students" not in inspector.get_table_names():
        raise RuntimeError(
            "Table students was not found; run this only against an initialized "
            "LMS database."
        )

    duplicate_email_groups = _case_insensitive_duplicate_student_email_groups(bind)
    if duplicate_email_groups:
        # Verification and login normalize email. Proceeding with two accounts
        # that become equal could associate the wrong person. Failing before
        # any DDL preserves the database for a deliberate manual correction.
        raise RuntimeError(
            "Migration stopped: found "
            f"{duplicate_email_groups} duplicate students.email group(s) when "
            "case and surrounding whitespace are ignored. No changes were "
            "applied; correct the data manually and run the migration again."
        )

    student_columns = {
        column["name"] for column in inspector.get_columns("students")
    }
    added_email_verified_at = "email_verified_at" not in student_columns

    if added_email_verified_at:
        # No DEFAULT: legacy accounts remain pending until they prove email
        # ownership. This additive ALTER does not change passwords or sessions.
        with bind.begin() as connection:
            connection.execute(
                text("ALTER TABLE students ADD COLUMN email_verified_at DATETIME")
            )

    # ``checkfirst`` preserves repeated runs and does not recreate tables.
    EmailVerificationToken.__table__.create(bind=bind, checkfirst=True)
    EventMembership.__table__.create(bind=bind, checkfirst=True)

    # An index on a column created by ALTER is not created automatically.
    _create_indexes(bind, Student.__table__)
    _create_indexes(bind, EmailVerificationToken.__table__)
    _create_indexes(bind, EventMembership.__table__)

    return {"email_verified_at_added": added_email_verified_at}


def main():
    result = upgrade()
    if result["email_verified_at_added"]:
        print("Created students.email_verified_at without verifying old accounts.")
    else:
        print("Column students.email_verified_at already exists.")
    print("Tables email_verification_tokens and event_memberships are ready.")


if __name__ == "__main__":
    main()
