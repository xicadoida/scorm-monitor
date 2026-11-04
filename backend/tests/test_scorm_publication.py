import unittest
from concurrent.futures import ThreadPoolExecutor
import threading
from unittest.mock import patch

from sqlalchemy.orm import Session, sessionmaker

from models import Course, CourseSession, Enrollment, ScormPublication
from publication_fixtures import PublicationFixture
from scorm_publication import PublicationBusy, PublicationError, RecoveryRequired, publish_course, recover_publication


class PublicationTests(PublicationFixture, unittest.TestCase):
    def setUp(self):
        self.setup_publication()

    def publish(self, metadata=None, sessions=None):
        return publish_course(self.package, 'course', metadata, sessions or self.sessions, self.remote_factory)

    def recover(self):
        return recover_publication('course', self.sessions, self.remote_factory)

    def assert_old(self):
        self.assertEqual(self.remote.nodes['/scorm/course/old.txt'], b'old content')
        with self.sessions() as db:
            course = db.query(Course).one()
            self.assertEqual((course.id, course.title, course.scorm_path), (self.course_id, 'Original', 'old-url'))
            self.assertIsNone(db.get(ScormPublication, 'course'))

    def test_complete_upload(self):
        result = self.publish({'title': 'Synthetic', 'passing_score': 80})
        self.assertFalse(result['recovery_pending'])
        self.assertEqual(self.remote.nodes['/scorm/course/scormdriver/indexAPI.html'], b'new content')
        with self.sessions() as db:
            self.assertEqual(db.query(Course).count(), 1)
            self.assertIsNone(db.get(ScormPublication, 'course'))

    def test_replace_preserves_persisted_links(self):
        self.previous()
        with self.sessions() as db:
            db.add(Enrollment(student_code='synthetic', course_code='course'))
            db.add(CourseSession(student_id='synthetic', course_id='course', status='passed', completed=True))
            db.commit()
        result = self.publish()
        self.assertEqual(result['id'], self.course_id)
        self.assertNotIn('/scorm/course/old.txt', self.remote.nodes)
        with self.sessions() as db:
            self.assertEqual(db.query(Enrollment).count(), 1)
            session = db.query(CourseSession).one()
            self.assertEqual((session.status, session.completed), ('passed', True))
            self.assertNotEqual(db.query(Course).one().scorm_path, 'old-url')

    def test_failure_during_temporary_upload(self):
        self.previous()
        self.once(lambda action, source, dest: action == 'store' and source.endswith('indexAPI.html'))
        with self.assertRaises(PublicationError):
            self.publish()
        self.assert_old()

    def test_rename_unsupported_does_not_touch_previous(self):
        self.previous()
        self.once(lambda action, source, dest: action == 'rename' and '/.probe-' in dest)
        with self.assertRaises(PublicationError):
            self.publish()
        self.assert_old()

    def test_failure_during_swap(self):
        self.previous()
        self.once(lambda action, source, dest: action == 'rename' and dest == '/scorm/course')
        with self.assertRaises(PublicationError):
            self.publish()
        self.assert_old()

    def test_ambiguous_swap_applied_then_connection_lost(self):
        self.previous()
        self.once(lambda action, source, dest: action == 'rename' and dest == '/scorm/course', after=True)
        with self.assertRaises(PublicationError):
            self.publish()
        self.assert_old()

    def test_failure_during_restore_preserves_journal_and_backup(self):
        self.previous()

        def fail(action, source, destination, after):
            if action == 'rename' and destination == '/scorm/course' and not after:
                raise OSError('synthetic swap/restore failure')

        self.remote.hook = fail
        with self.assertRaises(RecoveryRequired):
            self.publish()
        with self.sessions() as db:
            self.assertEqual(db.get(ScormPublication, 'course').state, 'pending')
            self.assertEqual(db.query(Course).one().scorm_path, 'old-url')
        self.assertTrue(any('/.backup-' in path and path.endswith('old.txt') for path in self.remote.nodes))
        self.remote.hook = lambda *args: None
        self.assertEqual(self.recover(), 'rolled_back')
        self.assert_old()
        self.assertEqual(self.recover(), 'nothing_pending')

    def test_restart_after_interrupted_publication(self):
        self.previous()
        self.once(lambda action, source, dest: action == 'rename' and dest == '/scorm/course', after=True, exception=SystemExit)
        with self.assertRaises(SystemExit):
            self.publish()
        # Nova sessão SQL e nova instância de Remote, sem estado em memória da operação.
        self.assertEqual(self.recover(), 'rolled_back')
        self.assert_old()

    def test_restart_with_probe_interrupted(self):
        self.previous()
        self.once(lambda action, source, dest: action == 'rename' and '/.probe-' in dest, after=True, exception=SystemExit)
        with self.assertRaises(SystemExit):
            self.publish()
        self.recover()
        self.assert_old()

    def test_missing_previous_folder(self):
        self.previous(files=False)
        result = self.publish()
        self.assertEqual(result['id'], self.course_id)
        self.assertIn('/scorm/course/scormdriver/indexAPI.html', self.remote.nodes)

    def test_upload_conflict_does_not_overwrite_folder(self):
        self.remote.nodes.update({'/scorm/course': None, '/scorm/course/unknown.txt': b'preserve'})
        with self.assertRaises(PublicationError):
            self.publish({'title': 'Synthetic'})
        self.assertEqual(self.remote.nodes['/scorm/course/unknown.txt'], b'preserve')

    def test_duplicate_course_rejected_before_ftp(self):
        self.previous()
        with self.assertRaises(PublicationError):
            self.publish({'title': 'Duplicate'})
        self.assertEqual(self.remote.events, [])
        self.assert_old()

    def test_database_failure_rolls_back_remote(self):
        self.previous()

        class FailCommit(Session):
            def commit(self):
                operation = self.get(ScormPublication, 'course')
                if operation is not None and operation.state == 'committed':
                    raise OSError('synthetic commit failure before write')
                super().commit()

        with self.assertRaises(PublicationError):
            self.publish(sessions=sessionmaker(bind=self.engine, class_=FailCommit))
        self.assert_old()

    def test_ambiguous_database_commit_keeps_committed_version(self):
        self.previous()
        failed = False

        class AmbiguousCommit(Session):
            def commit(inner):
                nonlocal failed
                operation = inner.get(ScormPublication, 'course')
                committed = operation is not None and operation.state == 'committed'
                super().commit()
                if committed and not failed:
                    failed = True
                    raise OSError('synthetic driver response lost after commit')

        result = self.publish(sessions=sessionmaker(bind=self.engine, class_=AmbiguousCommit))
        self.assertFalse(result['recovery_pending'])
        with self.sessions() as db:
            self.assertIn('indexAPI.html', db.query(Course).one().scorm_path)
        self.assertNotIn('/scorm/course/old.txt', self.remote.nodes)

    def test_cleanup_failure_preserves_committed_state(self):
        self.previous()
        self.once(lambda action, source, dest: action == 'delete' and '/.backup-' in source)
        self.assertTrue(self.publish()['recovery_pending'])
        with self.sessions() as db:
            self.assertEqual(db.get(ScormPublication, 'course').state, 'committed')
        self.assertEqual(self.recover(), 'finalized')
        self.assertIn('/scorm/course/scormdriver/indexAPI.html', self.remote.nodes)

    def test_pending_operation_blocks_another_publication(self):
        self.previous()
        self.once(lambda action, source, dest: action == 'store', exception=SystemExit)
        with self.assertRaises(SystemExit):
            self.publish()
        with self.assertRaises(PublicationBusy):
            self.publish()

    def test_permission_failure_not_mistaken_for_absence(self):
        self.previous()
        self.remote.hook = lambda *args: (_ for _ in ()).throw(PermissionError('synthetic permission denied'))
        with self.assertRaises(RecoveryRequired):
            self.publish()
        self.assertIn('/scorm/course/old.txt', self.remote.nodes)

    def test_staged_integrity_mismatch(self):
        self.previous()

        def corrupt(action, source, destination, after):
            if action == 'store' and source.endswith('indexAPI.html') and after:
                self.remote.nodes[source] = b'corrupt'

        self.remote.hook = corrupt
        with self.assertRaises(PublicationError):
            self.publish()
        self.assert_old()

    def test_restart_after_staging_directory_creation(self):
        self.previous()
        self.once(lambda action, source, dest: action == 'mkdir' and '/.stage-' in source, after=True, exception=SystemExit)
        with self.assertRaises(SystemExit):
            self.publish()
        self.recover()
        self.assert_old()

    def test_recovery_refuses_changed_ftp_target(self):
        self.previous()
        self.once(lambda action, source, dest: action == 'rename' and '/.probe-' in dest, after=True, exception=SystemExit)
        with self.assertRaises(SystemExit):
            self.publish()
        snapshot = dict(self.remote.nodes)
        with patch.dict('os.environ', {'SCORM_FTP_BASE_DIR': '/other'}), self.assertRaises(RecoveryRequired):
            self.recover()
        self.assertEqual(snapshot, self.remote.nodes)
        self.recover()
        self.assert_old()

    def test_simultaneous_publication_same_course_is_excluded(self):
        self.previous()
        entered = threading.Event()
        release = threading.Event()

        def pause(action, source, destination, after):
            if action == 'store' and source.endswith('indexAPI.html') and not after:
                entered.set()
                if not release.wait(10):
                    raise TimeoutError('test synchronization failed')

        self.remote.hook = pause
        with ThreadPoolExecutor(max_workers=2) as executor:
            first = executor.submit(self.publish)
            try:
                self.assertTrue(entered.wait(10))
                snapshot = dict(self.remote.nodes)
                second = executor.submit(self.publish)
                with self.assertRaises(PublicationBusy):
                    second.result(timeout=10)
                self.assertEqual(self.remote.nodes, snapshot)
            finally:
                release.set()
            self.assertFalse(first.result(timeout=10)['recovery_pending'])
        self.assertEqual(self.recover(), 'nothing_pending')

    def test_successive_restore_failures_preserve_previous_and_journal(self):
        self.previous()

        def fail(action, source, destination, after):
            if action == 'rename' and destination == '/scorm/course' and not after:
                raise OSError('successive synthetic restore failures')

        self.remote.hook = fail
        with self.assertRaises(RecoveryRequired):
            self.publish()
        for _ in range(3):
            with self.assertRaises(OSError):
                self.recover()
            self.assertTrue(any('/.backup-' in key and value == b'old content' for key, value in self.remote.nodes.items()))
            with self.sessions() as db:
                self.assertEqual(db.get(ScormPublication, 'course').state, 'pending')
                self.assertEqual(db.query(Course).one().scorm_path, 'old-url')
        self.remote.hook = lambda *args: None
        self.assertEqual(self.recover(), 'rolled_back')
        self.assertEqual(self.recover(), 'nothing_pending')
        self.assert_old()

    def test_successive_cleanup_failures_never_revert_committed_version(self):
        self.previous()

        def fail(action, source, destination, after):
            if action == 'delete' and '/.backup-' in source and not after:
                raise OSError('successive synthetic cleanup failures')

        self.remote.hook = fail
        self.assertTrue(self.publish()['recovery_pending'])
        for _ in range(3):
            with self.assertRaises(OSError):
                self.recover()
            self.assertEqual(self.remote.nodes['/scorm/course/scormdriver/indexAPI.html'], b'new content')
            with self.sessions() as db:
                self.assertEqual(db.get(ScormPublication, 'course').state, 'committed')
                self.assertIn('indexAPI.html', db.query(Course).one().scorm_path)
        self.remote.hook = lambda *args: None
        self.assertEqual(self.recover(), 'finalized')
        self.assertEqual(self.recover(), 'nothing_pending')

    def test_restore_response_lost_is_idempotent_on_retry(self):
        self.previous()
        calls = 0

        def fail(action, source, destination, after):
            nonlocal calls
            if action != 'rename' or destination != '/scorm/course':
                return
            if not after:
                calls += 1
                if calls == 1:
                    raise OSError('swap rejected')
            elif '/.backup-' in source:
                raise ConnectionResetError('restore applied but reply lost')

        self.remote.hook = fail
        with self.assertRaises(RecoveryRequired):
            self.publish()
        self.assertEqual(self.remote.nodes['/scorm/course/old.txt'], b'old content')
        self.remote.hook = lambda *args: None
        self.assertEqual(self.recover(), 'rolled_back')
        self.assertEqual(self.recover(), 'nothing_pending')
        self.assert_old()
