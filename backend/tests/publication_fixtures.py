from contextlib import contextmanager
from pathlib import Path
import posixpath
import tempfile
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base
from models import Course
from scorm_fixtures import SCORM12
from scorm_publication import Remote


class FakeFTP:
    """Protocolo FTP simulado com falhas antes/depois de efeitos remotos."""
    def __init__(self):
        self.nodes = {'/scorm': None}
        self.hook = lambda action, source, destination, after: None
        self.events = []

    def mlsd(self, path):
        self.hook('list', path, '', False)
        if path not in self.nodes or self.nodes[path] is not None:
            raise OSError('synthetic directory inaccessible')
        return [(posixpath.basename(p), {'type': 'dir' if value is None else 'file'})
                for p, value in list(self.nodes.items()) if p != path and posixpath.dirname(p) == path]

    def mkd(self, path):
        self.hook('mkdir', path, '', False)
        if path in self.nodes:
            raise OSError('already exists')
        self.nodes[path] = None
        self.hook('mkdir', path, '', True)

    def storbinary(self, command, data):
        path = command.removeprefix('STOR ')
        self.hook('store', path, '', False)
        self.nodes[path] = data.read()
        self.hook('store', path, '', True)

    def retrbinary(self, command, callback):
        path = command.removeprefix('RETR ')
        self.hook('read', path, '', False)
        callback(self.nodes[path])
        self.hook('read', path, '', True)

    def rename(self, source, destination):
        self.events.append(('rename', source, destination))
        self.hook('rename', source, destination, False)
        if source not in self.nodes or destination in self.nodes:
            raise OSError('invalid rename')
        moved = {destination + key[len(source):]: value for key, value in self.nodes.items()
                 if key == source or key.startswith(source + '/')}
        for key in list(self.nodes):
            if key == source or key.startswith(source + '/'):
                del self.nodes[key]
        self.nodes.update(moved)
        self.hook('rename', source, destination, True)

    def delete(self, path):
        self.hook('delete', path, '', False)
        del self.nodes[path]
        self.hook('delete', path, '', True)

    def rmd(self, path):
        self.hook('rmdir', path, '', False)
        del self.nodes[path]
        self.hook('rmdir', path, '', True)


class PublicationFixture:
    def setup_publication(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.package = self.root / 'package'
        self.package.mkdir()
        (self.package / 'imsmanifest.xml').write_text(SCORM12, encoding='utf-8')
        (self.package / 'scormdriver').mkdir()
        (self.package / 'scormdriver/indexAPI.html').write_bytes(b'new content')
        self.engine = create_engine('sqlite:///' + (self.root / 'test.db').as_posix())
        self.addCleanup(self.engine.dispose)
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine)
        self.remote = FakeFTP()
        environment = patch.dict('os.environ', {'SCORM_FTP_BASE_DIR': '/scorm', 'SCORM_FTP_HOST': 'synthetic', 'SCORM_FTP_USER': 'synthetic', 'SCORM_PUBLIC_BASE_URL': 'https://synthetic.invalid/scorm'})
        environment.start()
        self.addCleanup(environment.stop)

    @contextmanager
    def remote_factory(self):
        yield Remote(self.remote)

    def previous(self, files=True):
        with self.sessions() as db:
            course = Course(course_code='course', title='Original', scorm_path='old-url', active=True)
            db.add(course)
            db.commit()
            self.course_id = course.id
        if files:
            self.remote.nodes.update({'/scorm/course': None, '/scorm/course/old.txt': b'old content'})

    def once(self, predicate, after=False, exception=OSError):
        triggered = False

        def hook(action, source, destination, happened):
            nonlocal triggered
            if not triggered and happened == after and predicate(action, source, destination):
                triggered = True
                raise exception('synthetic injected failure')

        self.remote.hook = hook
