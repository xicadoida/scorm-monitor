from functools import partial
import io
import os
import unittest
from unittest.mock import patch
import zipfile

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from auth_utils import CurrentUser, require_admin
from migrate_add_scorm_publications import migrate
from models import Course
from publication_fixtures import PublicationFixture
from scorm_fixtures import SCORM12
from scorm_publication import publish_course


class ApiTests(PublicationFixture, unittest.TestCase):
    def setUp(self):
        self.setup_publication()
        with patch.dict(os.environ, {'AUTO_CREATE_SCHEMA': 'false'}):
            from main import app
        self.app = app
        app.dependency_overrides[require_admin] = lambda: CurrentUser('synthetic', 'synthetic@example.invalid', True)
        self.addCleanup(app.dependency_overrides.clear)
        publisher = patch('routes.courses.publish_course', partial(publish_course, session_factory=self.sessions, remote_factory=self.remote_factory))
        publisher.start()
        self.addCleanup(publisher.stop)
        db = patch('routes.courses.SessionLocal', self.sessions)
        db.start()
        self.addCleanup(db.stop)
        self.client = TestClient(app)

    def zip_bytes(self, manifest=SCORM12):
        data = io.BytesIO()
        with zipfile.ZipFile(data, 'w') as package:
            package.writestr('imsmanifest.xml', manifest)
            package.writestr('scormdriver/indexAPI.html', 'new content')
        return data.getvalue()

    def test_upload_http_and_persistence(self):
        response = self.client.post('/courses/upload', data={'title': 'Synthetic', 'course_code': 'course'}, files={'file': ('course.zip', self.zip_bytes(), 'application/zip')})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['course_code'], 'course')
        with self.sessions() as db:
            self.assertEqual(db.query(Course).one().title, 'Synthetic')
        self.assertIn('/scorm/course/scormdriver/indexAPI.html', self.remote.nodes)

    def test_invalid_manifest_http_has_no_ftp_or_db_effect(self):
        for xml in ['', '<manifest', '<other/>']:
            with self.subTest(xml=xml):
                response = self.client.post('/courses/upload', data={'title': 'Synthetic', 'course_code': 'course'}, files={'file': ('course.zip', self.zip_bytes(xml))})
                self.assertEqual(response.status_code, 200)
                self.assertFalse(response.json()['success'])
        self.assertEqual(self.remote.nodes, {'/scorm': None})
        with self.sessions() as db:
            self.assertEqual(db.query(Course).count(), 0)

    def test_replace_http_preserves_course_id(self):
        self.previous()
        response = self.client.post('/courses/course/replace-file', files={'file': ('course.zip', self.zip_bytes())})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        with self.sessions() as db:
            self.assertEqual(db.query(Course).one().id, self.course_id)

    def test_corrupt_zip_http_rejected(self):
        response = self.client.post('/courses/upload', data={'title': 'Synthetic', 'course_code': 'course'}, files={'file': ('course.zip', b'corrupt')})
        self.assertFalse(response.json()['success'])
        self.assertEqual(self.remote.events, [])

    def test_upload_without_authentication(self):
        self.app.dependency_overrides.clear()
        response = self.client.post('/courses/upload', data={'title': 'Synthetic', 'course_code': 'course'}, files={'file': ('course.zip', self.zip_bytes())})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(self.remote.events, [])

    def test_restore_failure_http_returns_sanitized_error(self):
        self.previous()

        def fail(action, source, destination, after):
            if action == 'rename' and destination == '/scorm/course' and not after:
                raise OSError('do-not-expose-synthetic-detail')

        self.remote.hook = fail
        response = self.client.post('/courses/course/replace-file', files={'file': ('course.zip', self.zip_bytes())})
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('do-not-expose', response.text)

    def test_root_api(self):
        self.assertEqual(self.client.get('/').status_code, 200)

    def test_explicit_migration_is_idempotent(self):
        engine = create_engine('sqlite:///' + (self.root / 'migration.db').as_posix())
        try:
            migrate(engine)
            migrate(engine)
            self.assertEqual(inspect(engine).get_table_names(), ['scorm_publications'])
        finally:
            engine.dispose()

    def test_explicit_migration_preserves_existing_course(self):
        engine = create_engine('sqlite:///' + (self.root / 'upgrade.db').as_posix())
        try:
            Course.__table__.create(engine)
            sessions = sessionmaker(bind=engine)
            with sessions() as db:
                db.add(Course(course_code='synthetic', title='Preserved', scorm_path='synthetic-url'))
                db.commit()
            migrate(engine)
            migrate(engine)
            with sessions() as db:
                self.assertEqual(db.query(Course).one().title, 'Preserved')
        finally:
            engine.dispose()
