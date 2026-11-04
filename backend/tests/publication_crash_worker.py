"""Worker exclusivo do teste loopback: encerra o processo após rename real."""
from contextlib import contextmanager
import ftplib
import os
from pathlib import Path
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scorm_publication import Remote, publish_course

if __name__ == '__main__':
    database, package, port = sys.argv[1:]
    # Nunca recebe host arbitrário; somente servidor loopback do teste.
    engine = create_engine('sqlite:///' + Path(database).as_posix())

    class CrashAfterSwap(Remote):
        def rename(self, source, destination):
            super().rename(source, destination)
            if destination == '/scorm/course':
                os._exit(73)

    @contextmanager
    def factory():
        ftp = ftplib.FTP()
        try:
            ftp.connect('127.0.0.1', int(port), timeout=5)
            ftp.login('synthetic', 'synthetic-only')
            yield CrashAfterSwap(ftp)
        finally:
            ftp.close()

    publish_course(package, 'course', None, sessionmaker(bind=engine), factory)
