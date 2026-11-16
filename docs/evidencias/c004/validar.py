"""Prova de executabilidade do guia C0-04 com fixtures; não aceite C0-05."""
import hashlib
from contextlib import closing
import json
import os
from pathlib import Path
import platform
import sqlite3
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
ENV = dict(os.environ, PYTHONIOENCODING='utf-8', DATABASE_URL='sqlite://', AUTO_CREATE_SCHEMA='false')
events = []


def run(label, arguments, cwd=ROOT, success=True):
    command = [sys.executable, *map(str, arguments)]
    process = subprocess.run(command, cwd=cwd, env=ENV, capture_output=True, text=True, encoding='utf-8')
    (OUT / f'{label}.txt').write_text(f'Data: 14/11/2026 America/Sao_Paulo\nPython {platform.python_version()}; {platform.platform()}\ncwd={cwd}\nComando: {subprocess.list2cmdline(command)}\n\n{process.stdout}{process.stderr}\nexit={process.returncode}\n', encoding='utf-8')
    assert (process.returncode == 0) == success, label
    events.append({'etapa': label, 'exit': process.returncode, 'esperado': 0 if success else 'não zero'})
    print(label, process.returncode, flush=True)
    return process


if '--only-operations' not in sys.argv:
    run('AMBIENTE', ['-c', "import sys,hashlib,fastapi,sqlalchemy,defusedxml,httpx,pyftpdlib; assert sys.version_info>=(3,11); assert hasattr(hashlib,'file_digest'); print(sys.version); print('FastAPI',fastapi.__version__,'SQLAlchemy',sqlalchemy.__version__,'defusedxml',defusedxml.__version__)"])
    run('DEPENDENCIAS', ['-m', 'pip', 'check'])
    run('SCORM', ['-m', 'unittest', 'discover', '-s', 'tests', '-p', 'test_scorm_*.py', '-v'], ROOT/'backend')
    run('AUTENTICACAO', ['-m', 'unittest', 'discover', '-s', 'tests', '-p', 'test_auth_security.py', '-v'], ROOT/'backend')

with tempfile.TemporaryDirectory() as directory:
    temp = Path(directory)
    database = temp/'fixture.sqlite'
    with closing(sqlite3.connect(database)) as db:
        db.execute('CREATE TABLE courses (id INTEGER PRIMARY KEY, course_code TEXT)')
        db.execute("INSERT INTO courses VALUES (1,'synthetic')")
        db.execute('CREATE TABLE scorm_publications (course_code TEXT PRIMARY KEY, state TEXT)')
        db.commit()
    scorm = temp/'mirror'
    (scorm/'synthetic/scormdriver').mkdir(parents=True)
    (scorm/'synthetic/scormdriver/indexAPI.html').write_text('synthetic only', encoding='utf-8')
    # Preservar dotfiles/artefatos operacionais também no espelho.
    (scorm/'.backup-synthetic-id').mkdir()
    (scorm/'.backup-synthetic-id/.iaclube-publication').write_text('synthetic-marker', encoding='utf-8')
    logos = temp/'logos'
    logos.mkdir()
    (logos/'synthetic.txt').write_text('synthetic logo fixture', encoding='utf-8')
    snapshot, restored = temp/'snapshot', temp/'restored'
    helper = ROOT/'tools/lms_snapshot.py'
    before = hashlib.sha256(database.read_bytes()).hexdigest()
    run('BACKUP', [helper,'backup','--database',database,'--scorm',scorm,'--logos',logos,'--output',snapshot,'--revision','fixture-c004','--writers-stopped'])
    run('VERIFICAR', [helper,'verify','--source',snapshot])
    run('RESTAURAR_FIXTURE', [helper,'restore','--source',snapshot,'--destination',restored])
    assert (restored/'scorm/.backup-synthetic-id/.iaclube-publication').read_text() == 'synthetic-marker'
    with closing(sqlite3.connect(restored/'database.sqlite')) as db:
        assert db.execute('SELECT course_code FROM courses').fetchall() == [('synthetic',)]
    run('RECUSAR_SOBRESCRITA', [helper,'restore','--source',snapshot,'--destination',restored], success=False)
    (snapshot/'scorm/synthetic/scormdriver/indexAPI.html').write_text('corrupted fixture', encoding='utf-8')
    run('DETECTAR_CORRUPCAO', [helper,'verify','--source',snapshot], success=False)
    run('RECUSAR_RESTORE_CORROMPIDO', [helper,'restore','--source',snapshot,'--destination',temp/'should-not-exist'], success=False)
    assert not (temp/'should-not-exist').exists()
    assert hashlib.sha256(database.read_bytes()).hexdigest() == before

sources = subprocess.check_output(['git','ls-files','backend','src','public/scorm','public/.htaccess'], cwd=ROOT, text=True, encoding='utf-8').splitlines()
hashes = {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in sources}
(OUT/'FONTES_SHA256.json').write_text(json.dumps(hashes, ensure_ascii=False, indent=2)+'\n',encoding='utf-8')
result_name = 'RESULTADOS-OPERACAO.json' if '--only-operations' in sys.argv else 'RESULTADOS.json'
(OUT/result_name).write_text(json.dumps({'data':'14/11/2026','escopo':'verificação do guia com fixture sintética; não é aceite C0-05/produção','etapas':events,'origem_sqlite_preservada':True,'utilitario_sha256':hashlib.sha256((ROOT/'tools/lms_snapshot.py').read_bytes()).hexdigest()},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
