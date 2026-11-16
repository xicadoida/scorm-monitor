"""Backup/verificação/restauração local SQLite + espelho SCORM; sem BD/FTP implícitos.

Não acessa .env, rede ou aplicação. Destinos novos, sem sobrescrita.
Parar todos os escritores durante coleta do banco E do espelho de arquivos.
"""
import argparse
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import sqlite3


def digest(path):
    with path.open('rb') as data:
        return hashlib.file_digest(data, 'sha256').hexdigest()


def files(root):
    if root.is_symlink() or getattr(root, 'is_junction', lambda: False)() or not root.is_dir():
        raise ValueError('Raiz deve ser diretório local real.')
    result = {}
    for path in root.rglob('*'):
        if (path.is_symlink() or getattr(path, 'is_junction', lambda: False)()
                or not path.resolve().is_relative_to(root.resolve())
                or not (path.is_dir() or path.is_file())):
            raise ValueError('Links/arquivos especiais não são aceitos no snapshot.')
        if path.is_file():
            result[path.relative_to(root).as_posix()] = path
    return result


def database_check(path):
    with closing(sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)) as db:
        if db.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
            raise ValueError('SQLite não passou na verificação de integridade.')
        names = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        counts = {name: db.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
                  for name in ('courses', 'students', 'enrollments', 'course_sessions', 'scorm_publications') if name in names}
    return counts


def new_destination(destination, sources):
    destination = destination.absolute()
    if destination.exists() or destination.is_symlink():
        raise ValueError('Destino deve ser novo; não haverá sobrescrita.')
    for source in sources:
        if destination.resolve().is_relative_to(source.resolve()):
            raise ValueError('Destino não pode ficar dentro da origem.')
    if not destination.parent.is_dir():
        raise ValueError('Crie previamente o diretório pai privado do destino.')
    destination.mkdir(mode=0o700)
    return destination


def backup(database, scorm, output, logos=None, revision='not-recorded'):
    if database.is_symlink() or not database.is_file():
        raise ValueError('Arquivo SQLite de origem inexistente ou link.')
    trees = {'scorm': scorm}
    if logos is not None:
        trees['logos'] = logos
    # Lista inclusive dotfiles de staging/backup e valida links antes de iniciar.
    inventories = {label: files(tree) for label, tree in trees.items()}
    output = new_destination(output, [database, *trees.values()])
    snapshot_db = output / 'database.sqlite'
    with closing(sqlite3.connect(database.resolve().as_uri() + '?mode=ro', uri=True)) as source:
        with closing(sqlite3.connect(snapshot_db)) as target:
            source.backup(target)
    database_check(snapshot_db)
    for label, inventory in inventories.items():
        (output / label).mkdir()
        for name, source in inventory.items():
            target = output / label / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
    inventory = {name: {'bytes': path.stat().st_size, 'sha256': digest(path)} for name, path in files(output).items()}
    document = dict(format=1, created_at=datetime.now(timezone.utc).isoformat(), revision=revision,
                    writer_policy='operator-confirmed-stopped', trees=sorted(trees), database_counts=database_check(snapshot_db), files=inventory)
    # O manifesto só aparece ao terminar: diretório sem snapshot.json é incompleto.
    (output / 'snapshot.json').write_text(json.dumps(document, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    return verify(output)


def verify(source):
    present = files(source)
    document = json.loads((source / 'snapshot.json').read_text(encoding='utf-8'))
    if document.get('format') != 1 or not isinstance(document.get('files'), dict):
        raise ValueError('Formato de snapshot não reconhecido.')
    if document.get('trees') not in (['scorm'], ['logos', 'scorm']):
        raise ValueError('Árvores do snapshot não reconhecidas.')
    if any(not (source / label).is_dir() for label in document['trees']):
        raise ValueError('Raiz de arquivos ausente no snapshot.')
    expected = document['files']
    if set(present) != set(expected) | {'snapshot.json'} or 'database.sqlite' not in expected:
        raise ValueError('Inventário difere dos arquivos presentes.')
    for name, metadata in expected.items():
        relative = PurePosixPath(name)
        if relative.is_absolute() or any(part in {'.', '..'} or ':' in part or '\\' in part for part in relative.parts):
            raise ValueError('Caminho inseguro no manifesto de backup.')
        path = present[name]
        if path.stat().st_size != metadata['bytes'] or digest(path) != metadata['sha256']:
            raise ValueError('Tamanho/hash divergente no snapshot.')
    counts = database_check(source / 'database.sqlite')
    if counts != document.get('database_counts'):
        raise ValueError('Contagens SQLite divergentes do snapshot.')
    return {'verified_files': len(expected), 'database_counts': counts, 'integrity': 'ok'}


def restore(source, destination):
    verify(source)
    destination = new_destination(destination, [source])
    document = json.loads((source / 'snapshot.json').read_text(encoding='utf-8'))
    for label in document['trees']:
        (destination / label).mkdir()
    for name, path in files(source).items():
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
    return verify(destination)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    create = commands.add_parser('backup')
    create.add_argument('--database', type=Path, required=True)
    create.add_argument('--scorm', type=Path, required=True)
    create.add_argument('--logos', type=Path)
    create.add_argument('--output', type=Path, required=True)
    create.add_argument('--revision', default='not-recorded')
    create.add_argument('--writers-stopped', action='store_true', required=True)
    check = commands.add_parser('verify')
    check.add_argument('--source', type=Path, required=True)
    recover = commands.add_parser('restore')
    recover.add_argument('--source', type=Path, required=True)
    recover.add_argument('--destination', type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == 'backup':
            result = backup(args.database, args.scorm, args.output, args.logos, args.revision)
        elif args.command == 'verify':
            result = verify(args.source)
        else:
            result = restore(args.source, args.destination)
    except (ValueError, OSError, sqlite3.Error, KeyError, TypeError) as error:
        parser.exit(1, f'Falha: {error}\nNão remover nem sobrescrever fontes; revisar snapshot/destino.\n')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
