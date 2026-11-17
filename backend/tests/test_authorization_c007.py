"""Matriz executavel de autorizacao da tarefa C0-07.

Os cenarios usam SQLite temporario e dados sinteticos. Nenhuma chamada usa o
banco local, FTP, VPS ou outro ambiente externo.
"""
import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import auth_utils
from database import Base
from models import (
    AttendanceModule,
    Course,
    CourseSession,
    Enrollment,
    Event,
    EventEmail,
    EventMembership,
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


class AuthorizationC007Tests(unittest.TestCase):
    """Exercita autorizacao HTTP sem sobrescrever os guards da aplicacao."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        database_path = Path(self.temp.name) / "authorization-c007.db"
        self.engine = create_engine(
            f"sqlite:///{database_path.as_posix()}",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(bind=self.engine)
        self.sessions = sessionmaker(bind=self.engine)
        self.addCleanup(self.engine.dispose)

        environment = {
            "AUTH_SECRET": "c007-auth-secret-with-at-least-thirty-two-characters",
            "AUTH_TOKEN_TTL_SECONDS": "60",
            "AUTH_LOGIN_MAX_ATTEMPTS": "20",
            "AUTH_LOGIN_WINDOW_SECONDS": "60",
            "IP_HASH_SECRET": "c007-ip-secret-with-at-least-thirty-two-characters",
            "TRUST_PROXY_HEADERS": "false",
            "ADMIN_EMAILS": "admin@tests.invalid,reserved-admin@tests.invalid",
            # Impede que importar main toque o banco configurado fora do teste.
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
        with self.sessions() as db:
            event_alpha = Event(name="Evento Alpha", slug="alpha")
            event_beta = Event(name="Evento Beta", slug="beta")
            db.add_all((event_alpha, event_beta))
            db.flush()

            db.add_all((
                EventEmail(event_id=event_alpha.id, email="event-alpha@tests.invalid"),
                EventEmail(event_id=event_beta.id, email="event-beta@tests.invalid"),
            ))
            db.add_all((
                EventMembership(
                    student_code="student-alpha",
                    event_id=event_alpha.id,
                    email="event-alpha@tests.invalid",
                    status="confirmed",
                    confirmed_at=datetime.utcnow(),
                ),
                EventMembership(
                    student_code="student-beta",
                    event_id=event_beta.id,
                    email="event-beta@tests.invalid",
                    status="confirmed",
                    confirmed_at=datetime.utcnow(),
                ),
            ))
            db.add_all((
                Student(
                    student_code="student-standard",
                    name="Student Standard",
                    email="student-standard@tests.invalid",
                    password_hash=hash_password("standard-password"),
                    auth_token_version=0,
                    email_verified_at=datetime.utcnow(),
                ),
                Student(
                    student_code="student-standard-empty",
                    name="Student Standard Empty",
                    email="student-standard-empty@tests.invalid",
                    password_hash=hash_password("empty-password"),
                    auth_token_version=0,
                    email_verified_at=datetime.utcnow(),
                ),
                Student(
                    student_code="student-alpha",
                    name="Student Alpha",
                    email="event-alpha@tests.invalid",
                    password_hash=hash_password("alpha-password"),
                    auth_token_version=0,
                    email_verified_at=datetime.utcnow(),
                ),
                Student(
                    student_code="student-beta",
                    name="Student Beta",
                    email="event-beta@tests.invalid",
                    password_hash=hash_password("beta-password"),
                    auth_token_version=0,
                    email_verified_at=datetime.utcnow(),
                ),
                Student(
                    student_code="admin",
                    name="Admin",
                    email="admin@tests.invalid",
                    password_hash=hash_password("admin-password"),
                    auth_token_version=0,
                    email_verified_at=datetime.utcnow(),
                ),
            ))
            db.add_all((
                Course(
                    title="Public course",
                    course_code="course-public",
                    scorm_path="/scorm/course-public/index.html",
                    active=True,
                ),
                Course(
                    title="Alpha course",
                    course_code="course-alpha",
                    scorm_path="/scorm/course-alpha/index.html",
                    active=True,
                    event_id=event_alpha.id,
                ),
                Course(
                    title="Beta course",
                    course_code="course-beta",
                    scorm_path="/scorm/course-beta/index.html",
                    active=True,
                    event_id=event_beta.id,
                ),
                Course(
                    title="Inactive course",
                    course_code="course-inactive",
                    scorm_path="/scorm/course-inactive/index.html",
                    active=False,
                ),
            ))
            db.add_all((
                Enrollment(student_code="student-standard", course_code="course-public", active=True),
                Enrollment(student_code="student-standard", course_code="course-alpha", active=True),
                Enrollment(student_code="student-alpha", course_code="course-alpha", active=True),
                Enrollment(student_code="student-alpha", course_code="course-public", active=True),
                Enrollment(student_code="student-alpha", course_code="course-beta", active=True),
                Enrollment(student_code="student-beta", course_code="course-beta", active=True),
                Enrollment(student_code="student-standard", course_code="course-inactive", active=True),
            ))
            allowed_session = CourseSession(
                student_id="student-alpha",
                course_id="course-alpha",
                status="incomplete",
                started_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            legacy_cross_event_session = CourseSession(
                student_id="student-alpha",
                course_id="course-beta",
                status="incomplete",
                started_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            other_student_session = CourseSession(
                student_id="student-beta",
                course_id="course-beta",
                status="incomplete",
                started_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            inactive_legacy_session = CourseSession(
                student_id="student-standard",
                course_id="course-inactive",
                status="incomplete",
                started_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.add_all((
                allowed_session,
                legacy_cross_event_session,
                other_student_session,
                inactive_legacy_session,
                AttendanceModule(name="Modulo global", event_id=None, position=1),
                AttendanceModule(name="Modulo Alpha", event_id=event_alpha.id, position=1),
            ))
            db.flush()
            self.allowed_session_id = allowed_session.id
            self.legacy_cross_event_session_id = legacy_cross_event_session.id
            self.other_student_session_id = other_student_session.id
            self.inactive_legacy_session_id = inactive_legacy_session.id
            self.event_alpha_id = event_alpha.id
            db.commit()

    def login(self, email: str, password: str, event_slug: str | None = None) -> str:
        payload = {"email": email, "password": password}
        if event_slug:
            payload["event_slug"] = event_slug
        response = self.client.post("/auth/login", json=payload)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.json()["success"], response.text)
        return response.json()["access_token"]

    @staticmethod
    def bearer(token: str) -> dict:
        return {"Authorization": f"Bearer {token}"}

    def test_protected_domains_reject_anonymous_requests(self):
        protected_reads = (
            "/students",
            "/courses",
            "/sessions",
            "/classes",
            "/events",
            "/attendance/modules",
            "/attendance/reports",
            "/admin/insights/summary",
            "/students/student-alpha/courses",
            "/attendance/students/student-alpha",
            "/progress/student-alpha/course-alpha",
            "/courses/public?email=event-alpha%40tests.invalid",
        )

        for path in protected_reads:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 401)

        response = self.client.post(
            "/enrollments",
            json={"student_code": "student-alpha", "course_code": "course-alpha"},
        )
        self.assertEqual(response.status_code, 401)

    def test_student_can_use_only_own_resources_and_cannot_change_identifiers(self):
        token = self.login("event-alpha@tests.invalid", "alpha-password", "alpha")
        headers = self.bearer(token)

        allowed = self.client.get("/students/student-alpha/courses", headers=headers)
        self.assertEqual(allowed.status_code, 200)

        forbidden_requests = (
            ("get", "/students/student-beta/courses", {}),
            ("get", "/attendance/students/student-beta", {}),
            ("get", "/progress/student-beta/course-beta", {}),
            ("get", "/courses/public?email=event-beta%40tests.invalid", {}),
            ("put", "/students/student-beta", {"json": {"name": "Altered"}}),
            (
                "post",
                "/students/student-beta/delete-account",
                {"json": {"password": "beta-password"}},
            ),
            (
                "post",
                "/students/student-beta/reset-password",
                {"json": {"new_password": "new-password"}},
            ),
            (
                "post",
                "/auth/change-password",
                {
                    "json": {
                        "student_code": "student-beta",
                        "current_password": "beta-password",
                        "new_password": "new-password",
                    }
                },
            ),
            (
                "post",
                "/sessions/start",
                {"json": {"student_id": "student-beta", "course_id": "course-beta"}},
            ),
            (
                "post",
                f"/sessions/{self.other_student_session_id}/update",
                {"json": {"session_time": "00:01"}},
            ),
            ("post", f"/sessions/{self.other_student_session_id}/finish", {}),
        )

        for method, path, kwargs in forbidden_requests:
            with self.subTest(method=method, path=path):
                response = getattr(self.client, method)(path, headers=headers, **kwargs)
                self.assertEqual(response.status_code, 403, response.text)

    def test_student_cannot_execute_administrative_operations(self):
        token = self.login("event-alpha@tests.invalid", "alpha-password", "alpha")
        headers = self.bearer(token)

        admin_reads = (
            "/students",
            "/courses",
            "/sessions",
            "/classes",
            "/events",
            "/attendance/modules",
            "/attendance/reports",
            "/admin/insights/summary",
        )
        for path in admin_reads:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path, headers=headers).status_code, 403)

        admin_writes = (
            (
                "post",
                "/students",
                {
                    "json": {
                        "student_code": "created-by-student",
                        "name": "Created",
                        "email": "created@tests.invalid",
                    }
                },
            ),
            (
                "post",
                "/courses",
                {
                    "json": {
                        "title": "Created",
                        "course_code": "created-course",
                        "scorm_path": "/scorm/created/index.html",
                    }
                },
            ),
            ("delete", "/courses/course-alpha", {}),
            (
                "post",
                "/enrollments",
                {"json": {"student_code": "student-beta", "course_code": "course-beta"}},
            ),
            ("post", "/classes", {"json": {"name": "Created class"}}),
            ("post", "/events", {"json": {"name": "Created event"}}),
            (
                "put",
                "/attendance/students/student-beta/parts/1",
                {"json": {"status": "presente"}},
            ),
        )
        for method, path, kwargs in admin_writes:
            with self.subTest(method=method, path=path):
                response = getattr(self.client, method)(path, headers=headers, **kwargs)
                self.assertEqual(response.status_code, 403, response.text)

        upload = self.client.post(
            "/courses/upload",
            headers=headers,
            data={"title": "Upload", "course_code": "upload-course"},
            files={"file": ("course.zip", b"not-a-zip", "application/zip")},
        )
        replace = self.client.post(
            "/courses/course-alpha/replace-file",
            headers=headers,
            files={"file": ("course.zip", b"not-a-zip", "application/zip")},
        )
        self.assertEqual(upload.status_code, 403, upload.text)
        self.assertEqual(replace.status_code, 403, replace.text)

    def test_admin_can_access_administrative_resources(self):
        token = self.login("admin@tests.invalid", "admin-password")
        headers = self.bearer(token)

        for path in (
            "/students",
            "/courses",
            "/sessions",
            "/classes",
            "/events",
            "/attendance/modules",
            "/attendance/reports",
            "/admin/insights/summary",
            "/students/student-alpha/courses",
        ):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path, headers=headers).status_code, 200)

        created_class = self.client.post(
            "/classes",
            headers=headers,
            json={"name": "Class C0-07"},
        )
        created_enrollment = self.client.post(
            "/enrollments",
            headers=headers,
            json={
                "student_code": "student-standard-empty",
                "course_code": "course-public",
            },
        )
        created_course = self.client.post(
            "/courses",
            headers=headers,
            json={
                "title": "Admin course",
                "course_code": "admin-created-course",
                "scorm_path": "/scorm/admin-created-course/index.html",
            },
        )
        self.assertEqual(created_class.status_code, 200, created_class.text)
        self.assertEqual(created_enrollment.status_code, 200, created_enrollment.text)
        self.assertEqual(created_course.status_code, 200, created_course.text)

    def test_admin_is_authorized_for_scorm_mutations_without_real_ftp(self):
        token = self.login("admin@tests.invalid", "admin-password")
        headers = self.bearer(token)
        publication_result = {"success": True, "recovery_pending": False}
        prepare_package = AsyncMock(return_value="/temporary/scorm-root")
        publish = AsyncMock(return_value=publication_result)

        with patch.object(
            courses_routes,
            "prepare_package",
            new=prepare_package,
        ), patch.object(
            courses_routes,
            "run_in_threadpool",
            new=publish,
        ):
            upload = self.client.post(
                "/courses/upload",
                headers=headers,
                data={"title": "Upload", "course_code": "upload-course"},
                files={"file": ("course.zip", b"synthetic", "application/zip")},
            )
            replace = self.client.post(
                "/courses/course-alpha/replace-file",
                headers=headers,
                files={"file": ("course.zip", b"synthetic", "application/zip")},
            )

        with patch.object(courses_routes.ftplib, "FTP"):
            deleted = self.client.delete("/courses/course-alpha", headers=headers)

        self.assertEqual(upload.status_code, 200, upload.text)
        self.assertTrue(upload.json()["success"])
        self.assertEqual(replace.status_code, 200, replace.text)
        self.assertTrue(replace.json()["success"])
        self.assertEqual(deleted.status_code, 200, deleted.text)
        self.assertTrue(deleted.json()["success"])
        self.assertEqual(prepare_package.await_count, 2)
        self.assertEqual(publish.await_count, 2)

    def test_event_scope_blocks_direct_enrollment_and_legacy_access(self):
        alpha_token = self.login("event-alpha@tests.invalid", "alpha-password", "alpha")
        alpha_headers = self.bearer(alpha_token)
        standard_token = self.login("student-standard@tests.invalid", "standard-password")
        standard_headers = self.bearer(standard_token)

        alpha_courses = self.client.get(
            "/students/student-alpha/courses", headers=alpha_headers
        ).json()
        standard_courses = self.client.get(
            "/students/student-standard/courses", headers=standard_headers
        ).json()
        self.assertEqual({course["course_code"] for course in alpha_courses}, {"course-alpha"})
        self.assertEqual({course["course_code"] for course in standard_courses}, {"course-public"})

        alpha_public = self.client.get(
            "/courses/public?email=event-alpha%40tests.invalid", headers=alpha_headers
        ).json()
        self.assertEqual(
            {course["course_code"] for course in alpha_public["courses"]},
            {"course-alpha"},
        )

        blocked_enrollments = (
            (alpha_headers, "student-alpha", "course-public"),
            (alpha_headers, "student-alpha", "course-beta"),
            (standard_headers, "student-standard", "course-alpha"),
        )
        for headers, student_code, course_code in blocked_enrollments:
            with self.subTest(student=student_code, course=course_code):
                response = self.client.post(
                    f"/students/{student_code}/enroll/{course_code}", headers=headers
                )
                self.assertEqual(response.status_code, 403, response.text)

        allowed_enrollment = self.client.post(
            "/students/student-alpha/enroll/course-alpha", headers=alpha_headers
        )
        self.assertEqual(allowed_enrollment.status_code, 200)
        self.assertTrue(allowed_enrollment.json()["success"])

        for course_code in ("course-public", "course-beta"):
            with self.subTest(course=course_code):
                response = self.client.post(
                    "/sessions/start",
                    headers=alpha_headers,
                    json={"student_id": "student-alpha", "course_id": course_code},
                )
                self.assertEqual(response.status_code, 403, response.text)

        allowed_session = self.client.post(
            "/sessions/start",
            headers=alpha_headers,
            json={"student_id": "student-alpha", "course_id": "course-alpha"},
        )
        self.assertEqual(allowed_session.status_code, 200, allowed_session.text)

        cross_progress = self.client.get(
            "/progress/student-alpha/course-beta", headers=alpha_headers
        )
        cross_update = self.client.post(
            f"/sessions/{self.legacy_cross_event_session_id}/update",
            headers=alpha_headers,
            json={"session_time": "00:01"},
        )
        cross_finish = self.client.post(
            f"/sessions/{self.legacy_cross_event_session_id}/finish",
            headers=alpha_headers,
        )
        self.assertEqual(cross_progress.status_code, 403, cross_progress.text)
        self.assertEqual(cross_update.status_code, 403, cross_update.text)
        self.assertEqual(cross_finish.status_code, 403, cross_finish.text)

    def test_attendance_standard_is_not_available_outside_an_event(self):
        standard = self.login("student-standard@tests.invalid", "standard-password")
        alpha = self.login("event-alpha@tests.invalid", "alpha-password", "alpha")
        admin = self.login("admin@tests.invalid", "admin-password")

        blocked = self.client.get(
            "/attendance/students/student-standard", headers=self.bearer(standard)
        )
        event_student = self.client.get(
            "/attendance/students/student-alpha", headers=self.bearer(alpha)
        )
        admin_audit = self.client.get(
            "/attendance/students/student-standard", headers=self.bearer(admin)
        )
        self.assertEqual(blocked.status_code, 403, blocked.text)
        self.assertEqual(event_student.status_code, 200, event_student.text)
        self.assertEqual(admin_audit.status_code, 200, admin_audit.text)

    def test_legacy_inactive_course_is_not_usable_by_a_student(self):
        token = self.login("student-standard@tests.invalid", "standard-password")
        headers = self.bearer(token)

        requests = (
            (
                "post",
                "/sessions/start",
                {"json": {"student_id": "student-standard", "course_id": "course-inactive"}},
            ),
            ("get", "/progress/student-standard/course-inactive", {}),
            (
                "post",
                f"/sessions/{self.inactive_legacy_session_id}/update",
                {"json": {"session_time": "00:01"}},
            ),
            ("post", f"/sessions/{self.inactive_legacy_session_id}/finish", {}),
        )
        for method, path, kwargs in requests:
            with self.subTest(method=method, path=path):
                response = getattr(self.client, method)(path, headers=headers, **kwargs)
                self.assertEqual(response.status_code, 403, response.text)

    def test_public_registration_cannot_claim_a_reserved_admin_email(self):
        response = self.client.post(
            "/auth/register",
            json={
                "name": "Impostor",
                "email": "reserved-admin@tests.invalid",
                "password": "impostor-password",
                "person_type": "pf",
                "accepted_terms": True,
            },
        )
        self.assertEqual(response.status_code, 200)
        # A resposta publica e generica para nao confirmar se o endereco
        # reservado existe ou e administrativo; a conta continua ausente.
        self.assertTrue(response.json()["success"])
        self.assertNotIn("student", response.json())

        with self.sessions() as db:
            student = db.query(Student).filter(
                Student.email == "reserved-admin@tests.invalid"
            ).first()
        self.assertIsNone(student)

    def test_invalid_expired_and_revoked_tokens_are_rejected(self):
        invalid = self.client.get("/students", headers=self.bearer("not-a-token"))
        self.assertEqual(invalid.status_code, 401)

        with self.sessions() as db:
            student = db.query(Student).filter(Student.student_code == "admin").one()
            with patch.object(auth_utils.time, "time", return_value=1_000):
                expired_token = auth_utils.create_access_token(student)
        with patch.object(auth_utils.time, "time", return_value=1_060):
            expired = self.client.get("/students", headers=self.bearer(expired_token))
        self.assertEqual(expired.status_code, 401)

        valid_token = self.login("admin@tests.invalid", "admin-password")
        with self.sessions() as db:
            student = db.query(Student).filter(Student.student_code == "admin").one()
            student.auth_token_version += 1
            db.commit()
        revoked = self.client.get("/students", headers=self.bearer(valid_token))
        self.assertEqual(revoked.status_code, 401)

    def test_intended_public_routes_remain_available(self):
        self.assertEqual(self.client.get("/").status_code, 200)
        self.assertEqual(self.client.get("/events/slug/alpha").status_code, 200)
        self.assertEqual(self.client.get("/catalog").status_code, 200)
        self.assertEqual(self.client.get("/catalog/last-update").status_code, 200)


if __name__ == "__main__":
    unittest.main()
