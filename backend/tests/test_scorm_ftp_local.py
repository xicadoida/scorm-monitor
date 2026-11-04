from contextlib import contextmanager
import ftplib
import logging
from pathlib import Path
import subprocess
import sys
import threading
import unittest

from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import FTPHandler
from pyftpdlib.servers import FTPServer

from models import Course
from publication_fixtures import PublicationFixture
from scorm_publication import Remote, PublicationError, publish_course, recover_publication


class LocalFtpTests(PublicationFixture, unittest.TestCase):
    """Integração: sockets loopback, arquivos temporários e SQLite reais."""
    def setUp(self):
        self.setup_publication()
        self.ftp_root = self.root / 'ftp'
        (self.ftp_root / 'scorm').mkdir(parents=True)
        authorizer = DummyAuthorizer()
        authorizer.add_user('synthetic', 'synthetic-only', str(self.ftp_root), perm='elradfmwMT')

        class Handler(FTPHandler):
            pass

        Handler.authorizer = authorizer
        # Logs de protocolo não devem misturar parâmetros de login à evidência.
        logger = logging.getLogger('pyftpdlib')
        previous = logger.disabled
        logger.disabled = True
        self.addCleanup(setattr, logger, 'disabled', previous)
        self.server = FTPServer(('127.0.0.1', 0), Handler)
        self.port = self.server.socket.getsockname()[1]
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={'timeout': 0.05, 'handle_exit': False}, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop_server)

    def stop_server(self):
        self.server.close_all()
        self.thread.join(timeout=2)

    @contextmanager
    def real_remote(self):
        ftp = ftplib.FTP()
        try:
            ftp.connect('127.0.0.1', self.port, timeout=5)
            ftp.login('synthetic', 'synthetic-only')
            yield Remote(ftp)
        finally:
            ftp.close()

    def test_real_ftp_upload_and_replace(self):
        initial = publish_course(self.package, 'course', {'title': 'Synthetic'}, self.sessions, self.real_remote)
        self.assertFalse(initial['recovery_pending'])
        target = self.ftp_root / 'scorm/course/scormdriver/indexAPI.html'
        self.assertEqual(target.read_bytes(), b'new content')
        (self.package / 'scormdriver/indexAPI.html').write_bytes(b'replacement content')
        result = publish_course(self.package, 'course', None, self.sessions, self.real_remote)
        self.assertEqual(result['id'], initial['id'])
        self.assertFalse(result['recovery_pending'])
        self.assertEqual(target.read_bytes(), b'replacement content')
        self.assertEqual([p.name for p in (self.ftp_root / 'scorm').iterdir()], ['course'])
        with self.sessions() as db:
            self.assertEqual(db.query(Course).count(), 1)

    def test_real_ftp_rollback_after_injected_swap_response_loss(self):
        initial = publish_course(self.package, 'course', {'title': 'Synthetic'}, self.sessions, self.real_remote)
        (self.package / 'scormdriver/indexAPI.html').write_bytes(b'replacement content')
        failed = False

        class ResponseLost(Remote):
            def rename(inner, source, destination):
                nonlocal failed
                super().rename(source, destination)
                if destination == '/scorm/course' and not failed:
                    failed = True
                    inner.ftp.close()
                    raise ConnectionResetError('synthetic response loss after real rename')

        @contextmanager
        def factory():
            with self.real_remote() as remote:
                yield ResponseLost(remote.ftp)

        with self.assertRaises(PublicationError):
            publish_course(self.package, 'course', None, self.sessions, factory)
        self.assertEqual((self.ftp_root / 'scorm/course/scormdriver/indexAPI.html').read_bytes(), b'new content')
        with self.sessions() as db:
            course = db.query(Course).one()
            self.assertEqual((course.id, course.scorm_path), (initial['id'], initial['scorm_path']))

    def test_real_ftp_recovery_after_process_exit(self):
        initial = publish_course(self.package, 'course', {'title': 'Synthetic'}, self.sessions, self.real_remote)
        (self.package / 'scormdriver/indexAPI.html').write_bytes(b'interrupted replacement')
        worker = Path(__file__).with_name('publication_crash_worker.py')
        result = subprocess.run([sys.executable, str(worker), str(self.root / 'test.db'), str(self.package), str(self.port)], capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 73, result.stderr)
        target = self.ftp_root / 'scorm/course/scormdriver/indexAPI.html'
        self.assertEqual(target.read_bytes(), b'interrupted replacement')
        self.assertEqual(recover_publication('course', self.sessions, self.real_remote), 'rolled_back')
        self.assertEqual(target.read_bytes(), b'new content')
        with self.sessions() as db:
            self.assertEqual(db.query(Course).one().scorm_path, initial['scorm_path'])
