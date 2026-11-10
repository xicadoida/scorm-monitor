"""Testes isolados dos controles de autenticacao da C0-03."""
import os
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from starlette.requests import Request

import auth_utils
from database import Base
from models import AccessEvent, Student
from privacy import trusted_forwarded_ip_hash
from routes import auth as auth_routes
from routes import enrollments as enrollment_routes
from routes import students as students_routes
from security import hash_password


class AuthenticationSecurityTests(unittest.TestCase):
    """Cada teste usa SQLite temporario e nunca toca no banco local."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        database_path = Path(self.temp.name) / "auth-security.db"
        self.engine = create_engine(
            f"sqlite:///{database_path.as_posix()}",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(bind=self.engine)
        self.sessions = sessionmaker(bind=self.engine)
        self.addCleanup(self.engine.dispose)

        self.auth_secret = "test-auth-secret-that-is-long-enough-for-c003"
        self.ip_hash_secret = "test-ip-hash-secret-that-is-long-enough-c003"
        environment = {
            "AUTH_SECRET": self.auth_secret,
            "AUTH_TOKEN_TTL_SECONDS": "60",
            "AUTH_LOGIN_MAX_ATTEMPTS": "3",
            "AUTH_LOGIN_WINDOW_SECONDS": "60",
            "IP_HASH_SECRET": self.ip_hash_secret,
            "TRUST_PROXY_HEADERS": "true",
            "ADMIN_EMAILS": "admin@tests.invalid",
        }
        self.environment_patch = patch.dict(os.environ, environment, clear=False)
        self.environment_patch.start()
        self.addCleanup(self.environment_patch.stop)

        for target in (
            auth_utils,
            auth_routes,
            students_routes,
            enrollment_routes,
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

        self._create_students()

    def _create_students(self):
        with self.sessions() as db:
            db.add_all(
                [
                    Student(
                        student_code="student",
                        name="Student Test",
                        email="student@tests.invalid",
                        password_hash=hash_password("student-password"),
                        auth_token_version=0,
                    ),
                    Student(
                        student_code="other-student",
                        name="Other Student",
                        email="other@tests.invalid",
                        password_hash=hash_password("other-password"),
                        auth_token_version=0,
                    ),
                    Student(
                        student_code="admin",
                        name="Admin Test",
                        email="admin@tests.invalid",
                        password_hash=hash_password("admin-password"),
                        auth_token_version=0,
                    ),
                ]
            )
            db.commit()

    def login(self, email, password):
        return self.client.post(
            "/auth/login",
            json={"email": email, "password": password},
            headers={"X-Forwarded-For": "203.0.113.10"},
        )

    @staticmethod
    def bearer(token):
        return {"Authorization": f"Bearer {token}"}

    def test_valid_login_creates_usable_session(self):
        response = self.login("admin@tests.invalid", "admin-password")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertTrue(data["student"]["is_admin"])
        self.assertNotIn(self.auth_secret, response.text)
        self.assertEqual(
            self.client.get("/students", headers=self.bearer(data["access_token"])).status_code,
            200,
        )

    def test_invalid_or_malformed_credentials_are_rejected_without_enumeration(self):
        unknown = self.login("unknown@tests.invalid", "wrong-password")
        wrong_password = self.login("student@tests.invalid", "wrong-password")

        with self.sessions() as db:
            db.query(Student).filter(Student.student_code == "other-student").update(
                {Student.password_hash: "malformed-password-hash"}
            )
            db.commit()
        malformed_hash = self.login("other@tests.invalid", "other-password")

        for response in (unknown, wrong_password, malformed_hash):
            self.assertEqual(response.status_code, 401)
            self.assertEqual(
                response.json(),
                {"success": False, "message": "Credenciais invalidas."},
            )

    def test_expired_session_is_rejected(self):
        with self.sessions() as db:
            student = db.query(Student).filter(Student.student_code == "student").one()
            with patch.object(auth_utils.time, "time", return_value=1_000):
                token = auth_utils.create_access_token(student)

        with patch.object(auth_utils.time, "time", return_value=1_060):
            response = self.client.get(
                "/students/student/courses", headers=self.bearer(token)
            )

        self.assertEqual(response.status_code, 401)

    def test_logout_revokes_token_and_new_login_works(self):
        token = self.login("student@tests.invalid", "student-password").json()["access_token"]

        logout = self.client.post("/auth/logout", headers=self.bearer(token))
        reused = self.client.get(
            "/students/student/courses", headers=self.bearer(token)
        )
        new_login = self.login("student@tests.invalid", "student-password")

        self.assertEqual(logout.status_code, 200)
        self.assertTrue(logout.json()["success"])
        self.assertEqual(reused.status_code, 401)
        self.assertEqual(new_login.status_code, 200)
        self.assertNotEqual(token, new_login.json()["access_token"])

    def test_rotating_auth_secret_rejects_previously_issued_token(self):
        token = self.login("admin@tests.invalid", "admin-password").json()["access_token"]

        with patch.dict(
            os.environ,
            {"AUTH_SECRET": "rotated-auth-secret-that-is-long-enough-for-c003"},
        ):
            response = self.client.get("/students", headers=self.bearer(token))

        self.assertEqual(response.status_code, 401)

    def test_missing_or_tampered_session_is_rejected(self):
        missing = self.client.get("/students")
        token = self.login("admin@tests.invalid", "admin-password").json()["access_token"]
        tampered = self.client.get("/students", headers=self.bearer(f"{token}x"))
        malformed_parts = self.client.get("/students", headers=self.bearer("a.b.c"))
        with self.assertRaises(HTTPException) as malformed_encoding:
            auth_utils._read_token("\u00e1.b")

        self.assertEqual(missing.status_code, 401)
        self.assertEqual(tampered.status_code, 401)
        self.assertEqual(malformed_parts.status_code, 401)
        self.assertEqual(malformed_encoding.exception.status_code, 401)

    def test_role_and_owner_restrictions_are_enforced(self):
        student_token = self.login("student@tests.invalid", "student-password").json()["access_token"]
        admin_token = self.login("admin@tests.invalid", "admin-password").json()["access_token"]

        admin_only = self.client.get("/students", headers=self.bearer(student_token))
        another_student = self.client.get(
            "/students/other-student/courses", headers=self.bearer(student_token)
        )
        admin = self.client.get("/students", headers=self.bearer(admin_token))

        self.assertEqual(admin_only.status_code, 403)
        self.assertEqual(another_student.status_code, 403)
        self.assertEqual(admin.status_code, 200)

    def test_repeated_login_attempts_are_limited_and_recover_after_window(self):
        for _ in range(3):
            self.assertEqual(
                self.login("student@tests.invalid", "wrong-password").status_code,
                401,
            )

        limited = self.login("student@tests.invalid", "student-password")
        self.assertEqual(limited.status_code, 429)
        self.assertEqual(limited.headers["Retry-After"], "60")

        with self.sessions() as db:
            db.query(AccessEvent).filter(AccessEvent.event_type == "login").update(
                {AccessEvent.created_at: datetime.utcnow() - timedelta(seconds=61)}
            )
            db.commit()

        self.assertEqual(
            self.login("student@tests.invalid", "student-password").status_code,
            200,
        )

    def test_ip_limit_only_uses_explicitly_trusted_forwarded_header(self):
        request = Request(
            {
                "type": "http",
                "method": "POST",
                "scheme": "https",
                "path": "/auth/login",
                "raw_path": b"/auth/login",
                "query_string": b"",
                "headers": [(b"x-forwarded-for", b"203.0.113.10")],
                "client": ("127.0.0.1", 12345),
                "server": ("testserver", 443),
            }
        )

        with patch.dict(os.environ, {"TRUST_PROXY_HEADERS": "false"}):
            self.assertIsNone(trusted_forwarded_ip_hash(request))
        with patch.dict(os.environ, {"TRUST_PROXY_HEADERS": "true"}):
            self.assertIsNotNone(trusted_forwarded_ip_hash(request))

    def test_secret_configuration_fails_closed_without_default_admin(self):
        with patch.dict(os.environ, {"AUTH_SECRET": ""}):
            unavailable = self.login("student@tests.invalid", "student-password")
        with patch.dict(os.environ, {"ADMIN_EMAILS": ""}):
            self.assertFalse(auth_utils.is_admin_email("admin@admin.com"))

        self.assertEqual(unavailable.status_code, 503)
        self.assertNotIn(self.auth_secret, unavailable.text)
        self.assertIn("AUTH_SECRET", unavailable.text)

    def test_example_configuration_contains_no_usable_secrets(self):
        example_path = Path(__file__).resolve().parents[1] / ".env.example"
        values = {}
        for line in example_path.read_text(encoding="utf-8").splitlines():
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                values[key] = value

        self.assertEqual(values["AUTH_SECRET"], "")
        self.assertEqual(values["IP_HASH_SECRET"], "")
        self.assertEqual(values["FTP_PASSWORD"], "")
        self.assertEqual(values["ADMIN_EMAILS"], "")


if __name__ == "__main__":
    unittest.main()
