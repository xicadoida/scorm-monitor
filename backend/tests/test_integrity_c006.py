"""Evidências automatizadas da integridade de registros da C0-06.

Os cenários usam SQLite temporário e a API real. Não acessam FTP, VPS,
banco de desenvolvimento ou dados reais.
"""
import os
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

import auth_utils
import migrate_add_integrity_states
from database import Base
from models import (
    AccessEvent,
    AttendanceModule,
    AttendanceModulePart,
    AttendanceRecord,
    ClassGroup,
    ClassStudent,
    Course,
    CourseSession,
    EmailVerificationToken,
    Enrollment,
    Event,
    EventEmail,
    EventMembership,
    PasswordResetToken,
    RegistrationProfile,
    ScormPublication,
    Student,
)
from routes import attendance as attendance_routes
from routes import auth as auth_routes
from routes import catalog as catalog_routes
from routes import classes as classes_routes
from routes import courses as courses_routes
from routes import enrollments as enrollments_routes
from routes import events as events_routes
from routes import insights as insights_routes
from routes import sessions as sessions_routes
from routes import students as students_routes
from security import hash_password


class IntegrityC006Tests(unittest.TestCase):
    """Exercita arquivamento, validação de vínculos e rollback atômico."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        database_path = Path(self.temp.name) / "integrity-c006.db"
        self.engine = create_engine(
            f"sqlite:///{database_path.as_posix()}",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(bind=self.engine)
        self.sessions = sessionmaker(bind=self.engine)
        self.addCleanup(self.engine.dispose)

        environment = {
            "AUTH_SECRET": "c006-auth-secret-with-at-least-thirty-two-characters",
            "AUTH_TOKEN_TTL_SECONDS": "300",
            "AUTH_LOGIN_MAX_ATTEMPTS": "20",
            "AUTH_LOGIN_WINDOW_SECONDS": "60",
            "IP_HASH_SECRET": "c006-ip-secret-with-at-least-thirty-two-characters",
            "TRUST_PROXY_HEADERS": "false",
            "ADMIN_EMAILS": "admin@tests.invalid",
            "AUTO_CREATE_SCHEMA": "false",
        }
        environment_patch = patch.dict(os.environ, environment, clear=False)
        environment_patch.start()
        self.addCleanup(environment_patch.stop)

        for target in (
            auth_utils,
            auth_routes,
            attendance_routes,
            catalog_routes,
            classes_routes,
            courses_routes,
            enrollments_routes,
            events_routes,
            insights_routes,
            sessions_routes,
            students_routes,
        ):
            database_patch = patch.object(target, "SessionLocal", self.sessions)
            database_patch.start()
            self.addCleanup(database_patch.stop)

        from main import app

        self.app = app
        self.app.dependency_overrides.clear()
        self.addCleanup(self.app.dependency_overrides.clear)
        self.client = TestClient(self.app)
        self.addCleanup(self.client.close)
        self._create_fixture()

    def _create_fixture(self):
        now = datetime.utcnow()
        self.old_event_token = "old-event-membership-token"
        with self.sessions() as db:
            alpha = Event(name="Evento Alpha", slug="alpha")
            beta = Event(name="Evento Beta", slug="beta")
            db.add_all((alpha, beta))
            db.flush()
            self.alpha_id = alpha.id
            self.beta_id = beta.id

            member = Student(
                student_code="member",
                name="Pessoa Membro",
                email="member@tests.invalid",
                password_hash=hash_password("member-password"),
                auth_token_version=0,
                email_verified_at=now,
            )
            admin = Student(
                student_code="admin",
                name="Pessoa Admin",
                email="admin@tests.invalid",
                password_hash=hash_password("admin-password"),
                auth_token_version=0,
                email_verified_at=now,
            )
            beta_member = Student(
                student_code="beta-member",
                name="Pessoa Beta",
                email="beta-member@tests.invalid",
                password_hash=hash_password("beta-password"),
                auth_token_version=0,
                email_verified_at=now,
            )
            db.add_all((member, admin, beta_member))
            db.add_all((
                EventEmail(event_id=alpha.id, email=member.email),
                EventEmail(event_id=beta.id, email=beta_member.email),
                EventMembership(
                    student_code=member.student_code,
                    event_id=alpha.id,
                    email=member.email,
                    status="confirmed",
                    confirmed_at=now,
                ),
                EventMembership(
                    student_code=beta_member.student_code,
                    event_id=beta.id,
                    email=beta_member.email,
                    status="confirmed",
                    confirmed_at=now,
                ),
                RegistrationProfile(
                    student_code=member.student_code,
                    person_type="pf",
                    event_id=alpha.id,
                    created_at=now,
                    updated_at=now,
                ),
                EmailVerificationToken(
                    student_code=member.student_code,
                    email=member.email,
                    event_id=alpha.id,
                    purpose="event_membership",
                    token_hash=auth_routes._verification_token_hash(self.old_event_token),
                    expires_at=now + timedelta(hours=1),
                    created_at=now,
                ),
                PasswordResetToken(
                    student_code=member.student_code,
                    token_hash="b" * 64,
                    expires_at=now + timedelta(hours=1),
                    created_at=now,
                ),
                AccessEvent(
                    event_type="login",
                    success=True,
                    student_code=member.student_code,
                    event_id=alpha.id,
                    created_at=now,
                ),
            ))

            course = Course(
                title="Curso Alpha",
                course_code="course-alpha",
                scorm_path="/scorm/course-alpha/index.html",
                active=True,
                event_id=alpha.id,
            )
            other_course = Course(
                title="Outro curso Alpha",
                course_code="course-other",
                scorm_path="/scorm/course-other/index.html",
                active=True,
                event_id=alpha.id,
            )
            db.add_all((course, other_course))
            db.add_all((
                Enrollment(
                    student_code=member.student_code,
                    course_code=course.course_code,
                    active=True,
                    assigned_at=now,
                ),
                CourseSession(
                    student_id=member.student_code,
                    course_id=course.course_code,
                    status="passed",
                    completed=True,
                    started_at=now,
                    updated_at=now,
                    completed_at=now,
                ),
            ))

            module = AttendanceModule(name="Módulo Alpha", event_id=alpha.id, position=1)
            db.add(module)
            db.flush()
            self.module_id = module.id
            part = AttendanceModulePart(
                module_id=module.id,
                course_code=course.course_code,
                label="Parte 1",
                position=1,
            )
            db.add(part)
            db.flush()
            self.part_id = part.id
            db.add(AttendanceRecord(
                student_code=member.student_code,
                part_id=part.id,
                status="presente",
                updated_at=now,
            ))

            class_group = ClassGroup(name="Turma Alpha", created_at=now)
            db.add(class_group)
            db.flush()
            self.class_id = class_group.id
            db.add(ClassStudent(class_id=class_group.id, student_code=member.student_code))
            db.commit()

    @staticmethod
    def bearer(token):
        return {"Authorization": f"Bearer {token}"}

    def _login(self, email, password, event_slug=None):
        payload = {"email": email, "password": password}
        if event_slug:
            payload["event_slug"] = event_slug
        response = self.client.post("/auth/login", json=payload)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.json()["success"], response.text)
        return response.json()["access_token"]

    def _admin_headers(self):
        return self.bearer(self._login("admin@tests.invalid", "admin-password"))

    def _assert_no_orphans(self):
        with self.sessions() as db:
            student_codes = {item.student_code for item in db.query(Student).all()}
            course_codes = {item.course_code for item in db.query(Course).all()}
            event_ids = {item.id for item in db.query(Event).all()}
            module_ids = {item.id for item in db.query(AttendanceModule).all()}
            part_ids = {item.id for item in db.query(AttendanceModulePart).all()}
            class_ids = {item.id for item in db.query(ClassGroup).all()}

            for enrollment in db.query(Enrollment).all():
                self.assertIn(enrollment.student_code, student_codes)
                self.assertIn(enrollment.course_code, course_codes)
            for session in db.query(CourseSession).all():
                self.assertIn(session.student_id, student_codes)
                self.assertIn(session.course_id, course_codes)
            for relation in db.query(ClassStudent).all():
                self.assertIn(relation.class_id, class_ids)
                self.assertIn(relation.student_code, student_codes)
            for record in db.query(AttendanceRecord).all():
                self.assertIn(record.student_code, student_codes)
                self.assertIn(record.part_id, part_ids)
            for part in db.query(AttendanceModulePart).all():
                self.assertIn(part.module_id, module_ids)
                if part.course_code:
                    self.assertIn(part.course_code, course_codes)
            for course in db.query(Course).all():
                if course.event_id is not None:
                    self.assertIn(course.event_id, event_ids)
            for module in db.query(AttendanceModule).all():
                if module.event_id is not None:
                    self.assertIn(module.event_id, event_ids)
            for profile in db.query(RegistrationProfile).all():
                self.assertIn(profile.student_code, student_codes)
                if profile.event_id is not None:
                    self.assertIn(profile.event_id, event_ids)
            for invitation in db.query(EventEmail).all():
                self.assertIn(invitation.event_id, event_ids)
            for membership in db.query(EventMembership).all():
                self.assertIn(membership.student_code, student_codes)
                self.assertIn(membership.event_id, event_ids)
            for token in db.query(EmailVerificationToken).all():
                self.assertIn(token.student_code, student_codes)
                if token.event_id is not None:
                    self.assertIn(token.event_id, event_ids)
            for token in db.query(PasswordResetToken).all():
                self.assertIn(token.student_code, student_codes)
            for event in db.query(AccessEvent).all():
                # Em falha de autenticação, student_code guarda um HMAC do
                # principal para auditoria, não uma referência ao aluno.
                if event.success and event.student_code is not None:
                    self.assertIn(event.student_code, student_codes)
                if event.event_id is not None:
                    self.assertIn(event.event_id, event_ids)
            # Uma publicação inicial pode existir legitimamente antes do
            # Course ser criado; a relação é reconciliada pelo journal SCORM.
            for publication in db.query(ScormPublication).all():
                self.assertIn(publication.state, {"pending", "committed"})

    def test_student_deactivation_preserves_history_revokes_access_and_reserves_code(self):
        member_token = self._login("member@tests.invalid", "member-password", "alpha")
        deleted = self.client.delete("/students/member", headers=self._admin_headers())
        self.assertEqual(deleted.status_code, 200, deleted.text)
        self.assertTrue(deleted.json()["success"])

        with self.sessions() as db:
            student = db.query(Student).filter(Student.student_code == "member").one()
            self.assertFalse(student.active)
            self.assertIsNotNone(student.deactivated_at)
            self.assertEqual(db.query(RegistrationProfile).count(), 1)
            self.assertEqual(db.query(CourseSession).count(), 1)
            self.assertEqual(db.query(AttendanceRecord).count(), 1)
            self.assertEqual(db.query(AccessEvent).filter(AccessEvent.student_code == "member").count(), 2)
            self.assertFalse(db.query(Enrollment).one().active)
            membership = db.query(EventMembership).filter(
                EventMembership.student_code == "member"
            ).one()
            self.assertEqual(membership.status, "revoked")
            self.assertIsNotNone(membership.revoked_at)
            self.assertIsNotNone(db.query(EmailVerificationToken).one().used_at)
            self.assertIsNotNone(db.query(PasswordResetToken).one().used_at)

        old_token = self.client.get(
            "/courses/public?email=member%40tests.invalid",
            headers=self.bearer(member_token),
        )
        self.assertEqual(old_token.status_code, 401, old_token.text)
        login = self.client.post(
            "/auth/login",
            json={"email": "member@tests.invalid", "password": "member-password", "event_slug": "alpha"},
        )
        self.assertEqual(login.status_code, 401, login.text)
        self.assertFalse(login.json()["success"])
        self._assert_no_orphans()

    def test_course_archive_preserves_progress_attendance_and_never_deletes_ftp(self):
        member_token = self._login("member@tests.invalid", "member-password", "alpha")
        with patch.object(courses_routes.ftplib, "FTP") as ftp:
            deleted = self.client.delete("/courses/course-alpha", headers=self._admin_headers())
        self.assertEqual(deleted.status_code, 200, deleted.text)
        self.assertTrue(deleted.json()["success"])
        ftp.assert_not_called()

        with self.sessions() as db:
            course = db.query(Course).filter(Course.course_code == "course-alpha").one()
            self.assertFalse(course.active)
            self.assertIsNotNone(course.archived_at)
            self.assertEqual(db.query(Enrollment).count(), 1)
            self.assertEqual(db.query(CourseSession).count(), 1)
            self.assertEqual(db.query(AttendanceModulePart).count(), 1)
            self.assertEqual(db.query(AttendanceRecord).count(), 1)

        denied = self.client.post(
            "/sessions/start",
            headers=self.bearer(member_token),
            json={"student_id": "member", "course_id": "course-alpha"},
        )
        self.assertEqual(denied.status_code, 403, denied.text)
        self._assert_no_orphans()

    def test_pending_scorm_publication_blocks_course_archive(self):
        with self.sessions() as db:
            db.add(ScormPublication(
                course_code="course-alpha",
                token="e" * 32,
                state="pending",
                target_key="f" * 64,
            ))
            db.commit()

        blocked = self.client.delete(
            "/courses/course-alpha", headers=self._admin_headers()
        )
        self.assertEqual(blocked.status_code, 409, blocked.text)
        with self.sessions() as db:
            self.assertTrue(db.query(Course).filter(
                Course.course_code == "course-alpha"
            ).one().active)
            self.assertIsNotNone(db.get(ScormPublication, "course-alpha"))
        self._assert_no_orphans()

    def test_event_archive_preserves_context_but_blocks_new_event_access(self):
        member_token = self._login("member@tests.invalid", "member-password", "alpha")
        deleted = self.client.delete(f"/events/{self.alpha_id}", headers=self._admin_headers())
        self.assertEqual(deleted.status_code, 200, deleted.text)

        with self.sessions() as db:
            event = db.get(Event, self.alpha_id)
            self.assertFalse(event.active)
            self.assertIsNotNone(event.archived_at)
            self.assertEqual(db.query(Course).filter(Course.event_id == self.alpha_id).count(), 2)
            self.assertEqual(db.query(AttendanceModule).filter(AttendanceModule.event_id == self.alpha_id).count(), 1)
            self.assertEqual(db.query(RegistrationProfile).filter(RegistrationProfile.event_id == self.alpha_id).count(), 1)
            self.assertEqual(db.query(AccessEvent).filter(AccessEvent.event_id == self.alpha_id).count(), 2)
            self.assertTrue(db.query(EventEmail).filter(
                EventEmail.event_id == self.alpha_id
            ).one().active)
            membership = db.query(EventMembership).filter(
                EventMembership.student_code == "member"
            ).one()
            self.assertEqual(membership.status, "revoked")
            self.assertIsNotNone(membership.revoked_at)

        slug = self.client.get("/events/slug/alpha")
        self.assertTrue(slug.json()["success"] is False)
        old_token = self.client.get(
            "/courses/public?email=member%40tests.invalid",
            headers=self.bearer(member_token),
        )
        self.assertEqual(old_token.status_code, 401, old_token.text)
        denied_login = self.client.post(
            "/auth/login",
            json={"email": "member@tests.invalid", "password": "member-password", "event_slug": "alpha"},
        )
        self.assertEqual(denied_login.status_code, 200, denied_login.text)
        self.assertFalse(denied_login.json()["success"])
        default_login = self.client.post(
            "/auth/login",
            json={"email": "member@tests.invalid", "password": "member-password"},
        )
        self.assertEqual(default_login.status_code, 200, default_login.text)
        self.assertFalse(default_login.json()["success"])
        self._assert_no_orphans()

    def test_pending_scorm_publication_blocks_event_archive(self):
        with self.sessions() as db:
            db.add(ScormPublication(
                course_code="course-alpha",
                token="c" * 32,
                state="pending",
                target_key="d" * 64,
            ))
            db.commit()

        blocked = self.client.delete(
            f"/events/{self.alpha_id}", headers=self._admin_headers()
        )
        self.assertEqual(blocked.status_code, 200, blocked.text)
        self.assertFalse(blocked.json()["success"], blocked.text)
        with self.sessions() as db:
            self.assertTrue(db.get(Event, self.alpha_id).active)
            self.assertIsNotNone(db.get(ScormPublication, "course-alpha"))
        self._assert_no_orphans()

    def test_removed_invite_revokes_case_variant_membership_and_old_token(self):
        with self.sessions() as db:
            membership = db.query(EventMembership).filter(
                EventMembership.student_code == "member",
                EventMembership.event_id == self.alpha_id,
            ).one()
            membership.email = "Member@Tests.Invalid"
            db.commit()

        headers = self._admin_headers()
        removed = self.client.delete(
            f"/events/{self.alpha_id}/emails/member@tests.invalid",
            headers=headers,
        )
        self.assertEqual(removed.status_code, 200, removed.text)
        self.assertTrue(removed.json()["success"])
        restored_invite = self.client.post(
            f"/events/{self.alpha_id}/emails",
            headers=headers,
            json={"emails": ["member@tests.invalid"]},
        )
        self.assertEqual(restored_invite.status_code, 200, restored_invite.text)
        self.assertTrue(restored_invite.json()["success"])

        reused = self.client.post(
            "/auth/verify-email", json={"token": self.old_event_token}
        )
        self.assertEqual(reused.status_code, 200, reused.text)
        self.assertFalse(reused.json()["success"], reused.text)
        with self.sessions() as db:
            membership = db.query(EventMembership).filter(
                EventMembership.student_code == "member",
                EventMembership.event_id == self.alpha_id,
            ).one()
            invitation = db.query(EventEmail).filter(
                EventEmail.event_id == self.alpha_id,
                EventEmail.email == "member@tests.invalid",
            ).one()
            token = db.query(EmailVerificationToken).filter(
                EmailVerificationToken.student_code == "member"
            ).one()
            self.assertEqual(membership.status, "revoked")
            self.assertIsNotNone(membership.revoked_at)
            self.assertTrue(invitation.active)
            self.assertIsNotNone(token.used_at)
        self._assert_no_orphans()

    def test_attendance_archives_history_and_physically_deletes_only_empty_module(self):
        headers = self._admin_headers()
        deleted_part = self.client.delete(f"/attendance/parts/{self.part_id}", headers=headers)
        self.assertEqual(deleted_part.status_code, 200, deleted_part.text)
        self.assertEqual(deleted_part.json()["outcome"], "arquivada")

        with self.sessions() as db:
            part = db.get(AttendanceModulePart, self.part_id)
            self.assertFalse(part.active)
            self.assertEqual(db.query(AttendanceRecord).count(), 1)

        new_record = self.client.put(
            f"/attendance/students/member/parts/{self.part_id}",
            headers=headers,
            json={"status": "presente"},
        )
        self.assertFalse(new_record.json()["success"])

        archived_module = self.client.delete(f"/attendance/modules/{self.module_id}", headers=headers)
        self.assertEqual(archived_module.status_code, 200, archived_module.text)
        self.assertEqual(archived_module.json()["outcome"], "arquivado")

        empty = self.client.post(
            "/attendance/modules",
            headers=headers,
            json={"name": "Vazio", "event_id": self.beta_id},
        )
        self.assertEqual(empty.status_code, 200, empty.text)
        empty_id = empty.json()["id"]
        removed = self.client.delete(f"/attendance/modules/{empty_id}", headers=headers)
        self.assertEqual(removed.status_code, 200, removed.text)
        self.assertEqual(removed.json()["outcome"], "excluído")
        with self.sessions() as db:
            self.assertIsNone(db.get(AttendanceModule, empty_id))
            self.assertEqual(db.query(AttendanceRecord).count(), 1)
        self._assert_no_orphans()

    def test_reference_validation_and_reparenting_prevent_orphans_or_history_rewrite(self):
        headers = self._admin_headers()
        invalid_operations = (
            ("post", "/enrollments", {"student_code": "missing", "course_code": "course-alpha"}),
            ("post", "/enrollments", {"student_code": "member", "course_code": "missing"}),
            ("post", "/classes/999/students", {"student_codes": ["member"]}),
            ("post", f"/classes/{self.class_id}/students", {"student_codes": ["missing"]}),
            ("post", "/classes/999/enroll", {"course_code": "course-alpha"}),
            ("post", f"/classes/{self.class_id}/enroll", {"course_code": "missing"}),
            (
                "post",
                "/courses",
                {"title": "Inválido", "course_code": "bad-event", "scorm_path": "/x", "event_id": 999},
            ),
            ("post", "/attendance/modules", {"name": "Inválido", "event_id": 999}),
            ("post", "/attendance/modules/999/parts", {"label": "Inválida"}),
            ("post", f"/attendance/modules/{self.module_id}/parts", {"course_code": "missing"}),
            ("put", "/attendance/students/missing/parts/999", {"status": "presente"}),
            (
                "put",
                f"/attendance/students/beta-member/parts/{self.part_id}",
                {"status": "presente"},
            ),
        )
        for method, path, payload in invalid_operations:
            with self.subTest(method=method, path=path):
                response = getattr(self.client, method)(path, headers=headers, json=payload)
                self.assertEqual(response.status_code, 200, response.text)
                self.assertFalse(response.json()["success"], response.text)

        invalid_session = self.client.post(
            "/sessions/start",
            headers=headers,
            json={"student_id": "missing", "course_id": "missing"},
        )
        self.assertEqual(invalid_session.status_code, 200, invalid_session.text)
        self.assertEqual(invalid_session.json()["error"], "Student or course not found or inactive")

        moved_course = self.client.put(
            "/courses/course-alpha", headers=headers, json={"event_id": 0}
        )
        self.assertEqual(moved_course.status_code, 409, moved_course.text)
        moved_module = self.client.put(
            f"/attendance/modules/{self.module_id}", headers=headers, json={"event_id": self.beta_id}
        )
        self.assertEqual(moved_module.status_code, 409, moved_module.text)
        moved_part = self.client.put(
            f"/attendance/parts/{self.part_id}", headers=headers, json={"course_code": "course-other"}
        )
        self.assertEqual(moved_part.status_code, 409, moved_part.text)
        moved_date = self.client.put(
            f"/attendance/parts/{self.part_id}", headers=headers, json={"date": "2026-11-18"}
        )
        self.assertEqual(moved_date.status_code, 409, moved_date.text)

        with self.sessions() as db:
            self.assertEqual(db.query(Enrollment).count(), 1)
            self.assertEqual(db.query(CourseSession).count(), 1)
            self.assertEqual(db.query(AttendanceRecord).count(), 1)
            self.assertEqual(db.get(Course, 1).event_id, self.alpha_id)
            self.assertEqual(db.get(AttendanceModule, self.module_id).event_id, self.alpha_id)
            self.assertEqual(db.get(AttendanceModulePart, self.part_id).course_code, "course-alpha")
        self._assert_no_orphans()

    def test_failed_event_archive_rolls_back_all_changes(self):
        # A falha ocorre no único commit da operação. O rollback deve deixar
        # evento, convite, membership e tokens exatamente ativos/pendentes.
        with patch.object(Session, "commit", side_effect=OSError("commit sintético")):
            with self.assertRaises(OSError):
                events_routes.delete_event(self.alpha_id, object())

        with self.sessions() as db:
            self.assertTrue(db.get(Event, self.alpha_id).active)
            self.assertTrue(db.query(EventEmail).filter(
                EventEmail.event_id == self.alpha_id
            ).one().active)
            membership = db.query(EventMembership).filter(
                EventMembership.student_code == "member"
            ).one()
            self.assertEqual(membership.status, "confirmed")
            self.assertIsNone(membership.revoked_at)
            self.assertIsNone(db.query(EmailVerificationToken).one().used_at)
            self.assertIsNone(db.query(PasswordResetToken).one().used_at)
        self._assert_no_orphans()

    def test_integrity_migration_is_additive_and_idempotent_for_legacy_schema(self):
        legacy_path = Path(self.temp.name) / "legacy-integrity.db"
        legacy_engine = create_engine(f"sqlite:///{legacy_path.as_posix()}")
        self.addCleanup(legacy_engine.dispose)
        with legacy_engine.begin() as connection:
            for table in (
                "students",
                "courses",
                "events",
                "event_emails",
                "attendance_modules",
                "attendance_module_parts",
            ):
                connection.execute(text(f"CREATE TABLE {table} (id INTEGER PRIMARY KEY)"))
            connection.execute(text("INSERT INTO students (id) VALUES (1)"))
            connection.execute(text("INSERT INTO courses (id) VALUES (1)"))

        first = migrate_add_integrity_states.upgrade(bind=legacy_engine)
        second = migrate_add_integrity_states.upgrade(bind=legacy_engine)
        columns = {
            table: {column["name"] for column in inspect(legacy_engine).get_columns(table)}
            for table in migrate_add_integrity_states.ADDITIVE_COLUMNS
        }
        with legacy_engine.connect() as connection:
            student_active = connection.execute(text("SELECT active FROM students WHERE id = 1")).scalar_one()
            course_archived_at = connection.execute(text("SELECT archived_at FROM courses WHERE id = 1")).scalar_one()

        self.assertTrue(first["added"])
        self.assertEqual(second, {"added": []})
        self.assertIn("active", columns["students"])
        self.assertIn("deactivated_at", columns["students"])
        self.assertIn("archived_at", columns["courses"])
        self.assertIn("active", columns["events"])
        self.assertIn("revoked_at", columns["event_emails"])
        self.assertIn("archived_at", columns["attendance_modules"])
        self.assertIn("active", columns["attendance_module_parts"])
        self.assertEqual(student_active, 1)
        self.assertIsNone(course_archived_at)


if __name__ == "__main__":
    unittest.main()
