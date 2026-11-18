"""Fluxos de comprovacao de e-mail e vinculo de evento da C0-07.

Cada caso usa um banco SQLite temporario e um outbox em memoria. Assim os
testes exercitam os endpoints reais sem consultar SMTP, Gmail, VPS ou o banco
de desenvolvimento. O token bruto e obtido somente do e-mail falso, como
aconteceria com a pessoa que controla o endereco.
"""
import os
import re
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

import auth_utils
import migrate_add_email_verification
from database import Base
from models import (
    AccessEvent,
    AttendanceRecord,
    Course,
    CourseSession,
    EmailVerificationToken,
    Enrollment,
    Event,
    EventEmail,
    EventMembership,
    PasswordResetToken,
    RegistrationProfile,
    Student,
)
from routes import auth as auth_routes
from routes import courses as courses_routes
from routes import students as students_routes
from security import hash_password


class EmailVerificationC007Tests(unittest.TestCase):
    """Comprova que convite por e-mail nao e, sozinho, uma autorizacao."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        database_path = Path(self.temp.name) / "email-verification-c007.db"
        self.engine = create_engine(
            f"sqlite:///{database_path.as_posix()}",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(bind=self.engine)
        self.sessions = sessionmaker(bind=self.engine)
        self.addCleanup(self.engine.dispose)

        environment = {
            "AUTH_SECRET": "email-verification-c007-secret-with-at-least-32-chars",
            "AUTH_TOKEN_TTL_SECONDS": "300",
            "AUTH_LOGIN_MAX_ATTEMPTS": "20",
            "AUTH_LOGIN_WINDOW_SECONDS": "60",
            "IP_HASH_SECRET": "email-verification-c007-ip-secret-with-at-least-32",
            "TRUST_PROXY_HEADERS": "false",
            "ADMIN_EMAILS": "admin@tests.invalid",
            "EMAIL_VERIFICATION_TOKEN_TTL_MINUTES": "60",
            "EMAIL_VERIFICATION_MAX_REQUESTS": "2",
            "EMAIL_VERIFICATION_REQUEST_WINDOW_SECONDS": "60",
            "EMAIL_VERIFICATION_MAX_ATTEMPTS": "2",
            "EMAIL_VERIFICATION_ATTEMPT_WINDOW_SECONDS": "60",
            # Impede que importar main toque o banco configurado fora do teste.
            "AUTO_CREATE_SCHEMA": "false",
        }
        environment_patch = patch.dict(os.environ, environment, clear=False)
        environment_patch.start()
        self.addCleanup(environment_patch.stop)

        for target in (auth_utils, auth_routes, courses_routes, students_routes):
            database_patch = patch.object(target, "SessionLocal", self.sessions)
            database_patch.start()
            self.addCleanup(database_patch.stop)

        self.outbox = []

        def fake_send_email(to, subject, text, html):
            self.outbox.append(
                {"to": to, "subject": subject, "text": text, "html": html}
            )
            return True, None

        email_patch = patch.object(auth_routes, "send_email", side_effect=fake_send_email)
        email_patch.start()
        self.addCleanup(email_patch.stop)

        from main import app

        self.app = app
        self.app.dependency_overrides.clear()
        self.addCleanup(self.app.dependency_overrides.clear)
        self.client = TestClient(self.app)
        self.addCleanup(self.client.close)
        self._create_fixture()

    def _create_fixture(self):
        now = datetime.utcnow()
        with self.sessions() as db:
            alpha = Event(name="Evento Alpha", slug="alpha")
            beta = Event(name="Evento Beta", slug="beta")
            db.add_all((alpha, beta))
            db.flush()
            self.alpha_id = alpha.id
            self.beta_id = beta.id

            # Convites podem se repetir ou existir em mais de um evento. Eles
            # nao devem gerar memberships sem comprovacao do endereco.
            db.add_all(
                (
                    EventEmail(event_id=alpha.id, email="legit@tests.invalid"),
                    EventEmail(event_id=alpha.id, email="legacy@tests.invalid"),
                    EventEmail(event_id=alpha.id, email="multi@tests.invalid"),
                    EventEmail(event_id=beta.id, email="multi@tests.invalid"),
                    EventEmail(event_id=alpha.id, email="duplicate@tests.invalid"),
                    EventEmail(event_id=alpha.id, email="duplicate@tests.invalid"),
                    EventEmail(event_id=alpha.id, email="member@tests.invalid"),
                    EventEmail(event_id=alpha.id, email="changed@tests.invalid"),
                )
            )
            db.add_all(
                (
                    Course(
                        title="Curso Alpha",
                        course_code="course-alpha",
                        scorm_path="/scorm/course-alpha/index.html",
                        active=True,
                        event_id=alpha.id,
                    ),
                    Course(
                        title="Curso Beta",
                        course_code="course-beta",
                        scorm_path="/scorm/course-beta/index.html",
                        active=True,
                        event_id=beta.id,
                    ),
                    # Conta antiga: nao e considerada confirmada pela migracao.
                    Student(
                        student_code="legacy",
                        name="Conta antiga",
                        email="legacy@tests.invalid",
                        password_hash=hash_password("legacy-old-password"),
                        auth_token_version=0,
                        email_verified_at=None,
                    ),
                    Student(
                        student_code="member",
                        name="Membro confirmado",
                        email="member@tests.invalid",
                        password_hash=hash_password("member-password"),
                        auth_token_version=0,
                        email_verified_at=now,
                    ),
                )
            )
            db.add(
                EventMembership(
                    student_code="member",
                    event_id=alpha.id,
                    email="member@tests.invalid",
                    status="confirmed",
                    confirmed_at=now,
                    created_at=now,
                )
            )
            db.commit()

    @staticmethod
    def bearer(token):
        return {"Authorization": f"Bearer {token}"}

    @staticmethod
    def registration_payload(email, *, event_slug="alpha", password="initial-password"):
        return {
            "name": "Pessoa de teste",
            "email": email,
            "password": password,
            "person_type": "pf",
            "accepted_terms": True,
            "event_slug": event_slug,
        }

    def _last_token(self, expected_recipient=None):
        if expected_recipient is not None:
            messages = [message for message in self.outbox if message["to"] == expected_recipient]
        else:
            messages = self.outbox
        self.assertTrue(messages, "Nenhuma mensagem de confirmacao foi colocada no outbox.")
        message = messages[-1]
        content = message["text"] + message["html"]
        self.assertIn(
            "?confirmacao=1#verify_token=",
            content,
            "O e-mail deve forcar uma navegacao nova sem expor o token na query.",
        )
        self.assertNotRegex(
            content,
            r"[?&]verify_token=",
            "O token de confirmacao nao pode ser enviado na query string.",
        )
        match = re.search(r"\?confirmacao=1#verify_token=([A-Za-z0-9_-]+)", content)
        self.assertIsNotNone(
            match,
            "O e-mail de teste nao contem o token no fragmento apos o marcador de confirmacao.",
        )
        return match.group(1)

    def _login(self, email, password, event_slug=None):
        payload = {"email": email, "password": password}
        if event_slug is not None:
            payload["event_slug"] = event_slug
        return self.client.post("/auth/login", json=payload)

    def _verify(self, token, new_password=None):
        payload = {"token": token}
        if new_password is not None:
            payload["new_password"] = new_password
        return self.client.post("/auth/verify-email", json=payload)

    def _register_and_verify(self, email, event_slug="alpha", password="final-password"):
        response = self.client.post(
            "/auth/register",
            json=self.registration_payload(email, event_slug=event_slug),
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.json()["success"], response.text)
        token = self._last_token(email)
        verified = self._verify(token, password)
        self.assertEqual(verified.status_code, 200, verified.text)
        self.assertTrue(verified.json()["success"], verified.text)
        return token

    def test_registration_stays_pending_until_recipient_proves_possession(self):
        response = self.client.post(
            "/auth/register",
            json=self.registration_payload("legit@tests.invalid", password="attacker-password"),
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        token = self._last_token("legit@tests.invalid")

        with self.sessions() as db:
            pending = db.query(Student).filter(Student.email == "legit@tests.invalid").one()
            self.assertIsNone(pending.email_verified_at)
            self.assertEqual(
                db.query(EventMembership)
                .filter(EventMembership.student_code == pending.student_code)
                .count(),
                0,
            )
            forged_session = auth_utils.create_access_token(pending, self.alpha_id)

        # Saber o convite e escolher uma senha no formulario nao permite usar
        # dados do evento antes que o destinatario receba o link.
        blocked = self.client.get(
            "/courses/public?email=legit%40tests.invalid",
            headers=self.bearer(forged_session),
        )
        self.assertEqual(blocked.status_code, 401, blocked.text)
        attacker_login = self._login("legit@tests.invalid", "attacker-password", "alpha")
        self.assertFalse(attacker_login.json()["success"])

        confirmed = self._verify(token, "recipient-final-password")
        self.assertEqual(confirmed.status_code, 200, confirmed.text)
        self.assertTrue(confirmed.json()["success"], confirmed.text)
        self.assertTrue(confirmed.json()["event_access_granted"])

        attacker_login = self._login("legit@tests.invalid", "attacker-password", "alpha")
        recipient_login = self._login("legit@tests.invalid", "recipient-final-password", "alpha")
        self.assertEqual(attacker_login.status_code, 401)
        self.assertTrue(recipient_login.json()["success"], recipient_login.text)
        listed = self.client.get(
            "/courses/public?email=legit%40tests.invalid",
            headers=self.bearer(recipient_login.json()["access_token"]),
        )
        self.assertEqual(listed.status_code, 200, listed.text)
        self.assertEqual([course["course_code"] for course in listed.json()["courses"]], ["course-alpha"])

    def test_verification_token_is_one_time_expires_and_rate_limits_failed_attempts(self):
        raw_token = self._register_and_verify("duplicate@tests.invalid")
        reused = self._verify(raw_token, "another-password")
        self.assertEqual(reused.status_code, 200)
        self.assertEqual(reused.json(), {"success": False, "message": "Nao foi possivel confirmar este link."})

        self.client.post(
            "/auth/register",
            json=self.registration_payload("legit@tests.invalid"),
        )
        expired_token = self._last_token("legit@tests.invalid")
        with self.sessions() as db:
            token_record = db.query(EmailVerificationToken).filter(
                EmailVerificationToken.token_hash == auth_routes._verification_token_hash(expired_token)
            ).one()
            token_record.expires_at = datetime.utcnow() - timedelta(seconds=1)
            db.commit()
        expired = self._verify(expired_token, "recipient-final-password")
        self.assertEqual(expired.status_code, 200)
        self.assertEqual(expired.json(), {"success": False, "message": "Nao foi possivel confirmar este link."})

        invalid_token = "not-a-valid-verification-token"
        first = self._verify(invalid_token)
        second = self._verify(invalid_token)
        blocked = self._verify(invalid_token)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.json(), second.json())
        self.assertEqual(blocked.status_code, 429)

        # Um token verdadeiro tambem e limitado quando a pessoa ainda nao
        # informou uma senha valida. Isso evita tentativas ilimitadas contra
        # um link capturado, sem tornar a primeira tela de confirmacao invalida.
        resend = self.client.post(
            "/auth/resend-email-verification",
            json={"email": "legit@tests.invalid", "event_slug": "alpha"},
        )
        self.assertEqual(resend.status_code, 200, resend.text)
        valid_token = self._last_token("legit@tests.invalid")
        requires_password_once = self._verify(valid_token)
        requires_password_twice = self._verify(valid_token, "short")
        valid_token_blocked = self._verify(valid_token, "recipient-final-password")
        self.assertTrue(requires_password_once.json()["requires_new_password"])
        self.assertTrue(requires_password_twice.json()["requires_new_password"])
        self.assertEqual(valid_token_blocked.status_code, 429)

    def test_resend_uses_generic_reply_and_never_returns_or_persists_raw_token(self):
        eligible = self.client.post(
            "/auth/register",
            json=self.registration_payload("legit@tests.invalid"),
        )
        ineligible = self.client.post(
            "/auth/register",
            json=self.registration_payload("not-invited@tests.invalid"),
        )
        self.assertEqual(eligible.status_code, 200)
        self.assertEqual(ineligible.status_code, 200)
        self.assertEqual(eligible.json(), ineligible.json())
        raw_token = self._last_token("legit@tests.invalid")
        self.assertNotIn(raw_token, eligible.text)
        self.assertNotIn(raw_token, ineligible.text)

        with self.sessions() as db:
            token = db.query(EmailVerificationToken).one()
            self.assertNotEqual(token.token_hash, raw_token)
            audit_values = [
                " ".join(
                    str(value or "")
                    for value in (event.student_code, event.route, event.user_agent, event.ip_hash)
                )
                for event in db.query(AccessEvent).all()
            ]
        self.assertTrue(all(raw_token not in value for value in audit_values))

        # A terceira solicitacao para a mesma identidade e limitada, inclusive
        # quando uma tentativa anterior nao era elegivel.
        first = self.client.post(
            "/auth/resend-email-verification",
            json={"email": "legit@tests.invalid", "event_slug": "alpha"},
        )
        blocked = self.client.post(
            "/auth/resend-email-verification",
            json={"email": "legit@tests.invalid", "event_slug": "alpha"},
        )
        self.assertEqual(first.status_code, 200)
        self.assertEqual(blocked.status_code, 429)

    def test_each_event_requires_its_own_confirmation_even_for_shared_email(self):
        self._register_and_verify("multi@tests.invalid", "alpha", "multi-final-password")
        alpha_login = self._login("multi@tests.invalid", "multi-final-password", "alpha")
        beta_before = self._login("multi@tests.invalid", "multi-final-password", "beta")
        self.assertTrue(alpha_login.json()["success"], alpha_login.text)
        self.assertFalse(beta_before.json()["success"], beta_before.text)

        with self.sessions() as db:
            multi = db.query(Student).filter(Student.email == "multi@tests.invalid").one()
            memberships = db.query(EventMembership).filter(
                EventMembership.student_code == multi.student_code,
                EventMembership.status == "confirmed",
            ).all()
            self.assertEqual([membership.event_id for membership in memberships], [self.alpha_id])

        request_beta = self.client.post(
            "/auth/resend-email-verification",
            json={"email": "multi@tests.invalid", "event_slug": "beta"},
        )
        self.assertEqual(request_beta.status_code, 200, request_beta.text)
        beta_token = self._last_token("multi@tests.invalid")
        self.assertTrue(self._verify(beta_token).json()["success"])
        beta_login = self._login("multi@tests.invalid", "multi-final-password", "beta")
        self.assertTrue(beta_login.json()["success"], beta_login.text)

        # Dois registros de convite iguais para Alpha ainda produzem um unico
        # vinculo, protegido por chave unica (student_code, event_id).
        self._register_and_verify("duplicate@tests.invalid")
        with self.sessions() as db:
            duplicate = db.query(Student).filter(Student.email == "duplicate@tests.invalid").one()
            self.assertEqual(
                db.query(EventMembership)
                .filter(
                    EventMembership.student_code == duplicate.student_code,
                    EventMembership.event_id == self.alpha_id,
                    EventMembership.status == "confirmed",
                )
                .count(),
                1,
            )

    def test_legacy_account_remains_blocked_until_its_email_is_confirmed(self):
        before = self._login("legacy@tests.invalid", "legacy-old-password", "alpha")
        self.assertEqual(before.status_code, 200)
        self.assertFalse(before.json()["success"])

        resend = self.client.post(
            "/auth/resend-email-verification",
            json={"email": "legacy@tests.invalid", "event_slug": "alpha"},
        )
        self.assertEqual(resend.status_code, 200, resend.text)
        token = self._last_token("legacy@tests.invalid")
        requires_password = self._verify(token)
        self.assertTrue(requires_password.json()["requires_new_password"])
        verified = self._verify(token, "legacy-new-password")
        self.assertTrue(verified.json()["success"], verified.text)

        after = self._login("legacy@tests.invalid", "legacy-new-password", "alpha")
        self.assertTrue(after.json()["success"], after.text)
        with self.sessions() as db:
            legacy = db.query(Student).filter(Student.student_code == "legacy").one()
            self.assertIsNotNone(legacy.email_verified_at)
            self.assertTrue(
                db.query(EventMembership)
                .filter(
                    EventMembership.student_code == "legacy",
                    EventMembership.event_id == self.alpha_id,
                    EventMembership.status == "confirmed",
                )
                .count()
            )

    def test_confirmed_email_change_revokes_event_memberships_until_new_event_proof(self):
        current_login = self._login("member@tests.invalid", "member-password", "alpha")
        self.assertTrue(current_login.json()["success"], current_login.text)
        old_access_token = current_login.json()["access_token"]

        requested = self.client.post(
            "/auth/change-email",
            headers=self.bearer(old_access_token),
            json={"current_password": "member-password", "new_email": "changed@tests.invalid"},
        )
        self.assertEqual(requested.status_code, 200, requested.text)
        self.assertTrue(requested.json()["success"])
        with self.sessions() as db:
            member = db.query(Student).filter(Student.student_code == "member").one()
            self.assertEqual(member.email, "member@tests.invalid")
        change_token = self._last_token("changed@tests.invalid")

        confirmed = self._verify(change_token)
        self.assertTrue(confirmed.json()["success"], confirmed.text)
        with self.sessions() as db:
            member = db.query(Student).filter(Student.student_code == "member").one()
            membership = db.query(EventMembership).filter(
                EventMembership.student_code == "member", EventMembership.event_id == self.alpha_id
            ).one()
            self.assertEqual(member.email, "changed@tests.invalid")
            self.assertEqual(membership.status, "revoked")
            self.assertIsNotNone(membership.revoked_at)

        old_token = self.client.get(
            "/courses/public?email=member%40tests.invalid",
            headers=self.bearer(old_access_token),
        )
        self.assertEqual(old_token.status_code, 401, old_token.text)
        before_reproof = self._login("changed@tests.invalid", "member-password", "alpha")
        self.assertFalse(before_reproof.json()["success"], before_reproof.text)

        resend = self.client.post(
            "/auth/resend-email-verification",
            json={"email": "changed@tests.invalid", "event_slug": "alpha"},
        )
        self.assertEqual(resend.status_code, 200, resend.text)
        membership_token = self._last_token("changed@tests.invalid")
        self.assertTrue(self._verify(membership_token).json()["success"])
        after_reproof = self._login("changed@tests.invalid", "member-password", "alpha")
        self.assertTrue(after_reproof.json()["success"], after_reproof.text)

    def test_account_deactivation_preserves_history_and_blocks_student_code_reuse(self):
        """C0-06 preserva dados sem permitir que outra pessoa os herde."""

        current_login = self._login("member@tests.invalid", "member-password", "alpha")
        self.assertTrue(current_login.json()["success"], current_login.text)
        now = datetime.utcnow()
        with self.sessions() as db:
            db.add_all(
                (
                    RegistrationProfile(
                        student_code="member",
                        person_type="pf",
                        created_at=now,
                        updated_at=now,
                    ),
                    EmailVerificationToken(
                        student_code="member",
                        email="member@tests.invalid",
                        purpose="event_membership",
                        token_hash="a" * 64,
                        expires_at=now + timedelta(hours=1),
                        created_at=now,
                    ),
                    PasswordResetToken(
                        student_code="member",
                        token_hash="b" * 64,
                        expires_at=now + timedelta(hours=1),
                        created_at=now,
                    ),
                    Enrollment(
                        student_code="member",
                        course_code="course-alpha",
                        active=True,
                        assigned_at=now,
                    ),
                    CourseSession(
                        student_id="member",
                        course_id="course-alpha",
                        status="passed",
                        completed=True,
                        started_at=now,
                        updated_at=now,
                        completed_at=now,
                    ),
                    AttendanceRecord(
                        student_code="member",
                        part_id=1,
                        status="presente",
                        updated_at=now,
                    ),
                )
            )
            db.commit()

        deleted = self.client.post(
            "/students/member/delete-account",
            headers=self.bearer(current_login.json()["access_token"]),
            json={"password": "member-password"},
        )
        self.assertEqual(deleted.status_code, 200, deleted.text)
        self.assertTrue(deleted.json()["success"], deleted.text)

        with self.sessions() as db:
            student = db.query(Student).filter(Student.student_code == "member").one()
            self.assertFalse(student.active)
            self.assertIsNotNone(student.deactivated_at)
            self.assertEqual(
                db.query(RegistrationProfile).filter(
                    RegistrationProfile.student_code == "member"
                ).count(),
                1,
            )
            self.assertEqual(
                db.query(CourseSession).filter(CourseSession.student_id == "member").count(),
                1,
            )
            enrollment = db.query(Enrollment).filter(
                Enrollment.student_code == "member"
            ).one()
            self.assertFalse(enrollment.active)
            self.assertEqual(
                db.query(AttendanceRecord).filter(
                    AttendanceRecord.student_code == "member"
                ).count(),
                1,
            )
            membership = db.query(EventMembership).filter(
                EventMembership.student_code == "member"
            ).one()
            self.assertEqual(membership.status, "revoked")
            self.assertIsNotNone(membership.revoked_at)
            for model in (EmailVerificationToken, PasswordResetToken):
                token = db.query(model).filter(model.student_code == "member").one()
                self.assertIsNotNone(token.used_at)

            db.add(
                Student(
                    student_code="member",
                    name="Conta recriada",
                    email="member@tests.invalid",
                    password_hash=hash_password("replacement-password"),
                    auth_token_version=0,
                    email_verified_at=now,
                )
            )
            with self.assertRaises(IntegrityError):
                db.commit()
            db.rollback()

        old_token = self.client.get(
            "/courses/public?email=member%40tests.invalid",
            headers=self.bearer(current_login.json()["access_token"]),
        )
        self.assertEqual(old_token.status_code, 401, old_token.text)
        deactivated_login = self._login("member@tests.invalid", "member-password", "alpha")
        self.assertFalse(deactivated_login.json()["success"], deactivated_login.text)

    def _create_preverification_students_table(self, database_path):
        """Cria somente o formato legado, sem a coluna da nova migracao."""

        engine = create_engine(f"sqlite:///{database_path.as_posix()}")
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    CREATE TABLE students (
                        id INTEGER PRIMARY KEY,
                        student_code VARCHAR(100) UNIQUE,
                        name VARCHAR(255),
                        email VARCHAR(255) UNIQUE,
                        created_at DATETIME,
                        password_hash VARCHAR(255),
                        auth_token_version INTEGER NOT NULL DEFAULT 0
                    )
                    """
                )
            )
        self.addCleanup(engine.dispose)
        return engine

    def test_migration_is_idempotent_and_leaves_legacy_accounts_unverified(self):
        database_path = Path(self.temp.name) / "legacy-schema.db"
        engine = self._create_preverification_students_table(database_path)
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO students (student_code, name, email, password_hash)
                    VALUES ('legacy-migration', 'Conta antiga', 'legacy-migration@tests.invalid', 'hash')
                    """
                )
            )

        first = migrate_add_email_verification.upgrade(bind=engine)
        second = migrate_add_email_verification.upgrade(bind=engine)
        inspector = inspect(engine)
        columns = {column["name"] for column in inspector.get_columns("students")}
        tables = set(inspector.get_table_names())
        with engine.connect() as connection:
            verified_at = connection.execute(
                text(
                    "SELECT email_verified_at FROM students "
                    "WHERE student_code = 'legacy-migration'"
                )
            ).scalar_one()

        self.assertEqual(first, {"email_verified_at_added": True})
        self.assertEqual(second, {"email_verified_at_added": False})
        self.assertIn("email_verified_at", columns)
        self.assertTrue(
            {"email_verification_tokens", "event_memberships"}.issubset(tables)
        )
        self.assertIsNone(verified_at)

    def test_migration_stops_before_ddl_when_legacy_email_normalization_is_ambiguous(self):
        database_path = Path(self.temp.name) / "legacy-duplicate-email.db"
        engine = self._create_preverification_students_table(database_path)
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO students (student_code, name, email, password_hash)
                    VALUES
                        ('legacy-a', 'Conta A', 'Pessoa@tests.invalid', 'hash'),
                        ('legacy-b', 'Conta B', ' pessoa@tests.invalid ', 'hash')
                    """
                )
            )

        with self.assertRaisesRegex(RuntimeError, "duplicate students.email"):
            migrate_add_email_verification.upgrade(bind=engine)

        inspector = inspect(engine)
        self.assertNotIn(
            "email_verified_at",
            {column["name"] for column in inspector.get_columns("students")},
        )
        self.assertNotIn("email_verification_tokens", inspector.get_table_names())
        self.assertNotIn("event_memberships", inspector.get_table_names())


if __name__ == "__main__":
    unittest.main()
