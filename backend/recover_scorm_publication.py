"""Recuperação explícita. Executar somente com escritores de cursos parados."""
import argparse

from database import SessionLocal
from models import ScormPublication
from scorm_publication import recover_publication


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--course', required=True)
    parser.add_argument('--apply', action='store_true', help='Reconcilia BD/FTP após parar escritores.')
    args = parser.parse_args()
    if args.apply:
        print(recover_publication(args.course))
    else:
        with SessionLocal() as db:
            record = db.get(ScormPublication, args.course)
            print('nothing_pending' if record is None else f'{record.course_code}: {record.state}; ação não executada')
