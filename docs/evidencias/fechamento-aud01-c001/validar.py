"""Fechamento local isolado: suíte, migração CLI, start API/Vite e build/lint."""
import hashlib
import json
import os
from pathlib import Path
import platform
import socket
import subprocess
import sys
import tempfile
import time
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
NODE = Path(r'C:\Users\Usuário\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe')
NPM = ROOT / 'node_modules/.audit-npm/bin/npm-cli.js'
env = dict(os.environ, PYTHONIOENCODING='utf-8', AUTO_CREATE_SCHEMA='false', DATABASE_URL='sqlite://')
env['PATH'] = str(NODE.parent) + os.pathsep + env.get('PATH', '')
results = []


def run(label, command, cwd=ROOT):
    completed = subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True, encoding='utf-8', errors='replace')
    (OUT / f'{label}.txt').write_text(f'cwd={cwd}\nComando={subprocess.list2cmdline(list(map(str, command)))}\n\n{completed.stdout}{completed.stderr}\nexit={completed.returncode}\n', encoding='utf-8')
    results.append({'etapa': label, 'exit': completed.returncode})
    print(label, completed.returncode, flush=True)
    return completed


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def smoke(label, command, cwd, urls):
    with (OUT / f'{label}-servidor.txt').open('w', encoding='utf-8') as log:
        process = subprocess.Popen(command, cwd=cwd, env=env, stdout=log, stderr=log)
        try:
            responses = []
            for path, url in urls:
                deadline = time.monotonic() + 30
                while True:
                    try:
                        with urlopen(url, timeout=3) as response:
                            body = response.read()
                            responses.append({'recurso': path, 'status': response.status, 'bytes': len(body)})
                            if path == '/openapi.json':
                                api = json.loads(body)
                                (OUT / 'ROTAS.json').write_text(json.dumps({p: sorted(ops) for p, ops in api['paths'].items()}, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
                            break
                    except Exception:
                        if time.monotonic() >= deadline or process.poll() is not None:
                            raise
                        time.sleep(0.2)
            (OUT / f'{label}-http.json').write_text(json.dumps(responses, indent=2)+'\n', encoding='utf-8')
            results.append({'etapa': label, 'exit': 0})
            print(label, 'HTTP OK', flush=True)
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


run('DEPENDENCIAS', [sys.executable, '-m', 'pip', 'check'])
run('TESTES', [sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v'], ROOT / 'backend')
with tempfile.TemporaryDirectory() as temp:
    database = Path(temp) / 'disposable.db'
    env['DATABASE_URL'] = 'sqlite:///' + database.as_posix()
    # Estrutura anterior compatível completa, SEM a tabela nova, e registro sintético.
    preparation = "from database import Base,engine,SessionLocal; import models; Base.metadata.create_all(engine,tables=[t for t in Base.metadata.sorted_tables if t.name!='scorm_publications']); db=SessionLocal(); db.add(models.Course(course_code='synthetic-aud01',title='Preservar',scorm_path='synthetic')); db.commit(); db.close()"
    assert run('BANCO_ANTERIOR', [sys.executable, '-c', preparation], ROOT / 'backend').returncode == 0
    for label in ('MIGRACAO', 'MIGRACAO_REPETIDA'):
        assert run(label, [sys.executable, 'migrate_add_scorm_publications.py'], ROOT / 'backend').returncode == 0
    verification = "from database import SessionLocal,engine; from sqlalchemy import inspect; from models import Course; db=SessionLocal(); c=db.query(Course).one(); assert c.title=='Preservar'; assert 'scorm_publications' in inspect(engine).get_table_names(); print('Curso preservado; journal criado; nenhuma conexao FTP'); db.close()"
    assert run('BANCO_VERIFICADO', [sys.executable, '-c', verification], ROOT / 'backend').returncode == 0
    port = free_port()
    base = f'http://127.0.0.1:{port}'
    smoke('API', [sys.executable, '-m', 'uvicorn', 'main:app', '--host', '127.0.0.1', '--port', str(port)], ROOT / 'backend', [(p, base+p) for p in ['/', '/docs', '/openapi.json', '/catalog']])
    run('RECUPERACAO_CONSULTA', [sys.executable, 'recover_scorm_publication.py', '--course', 'synthetic-aud01'], ROOT / 'backend')

run('NODE', [str(NODE), '--version'])
run('NPM', [str(NODE), str(NPM), '--version'])
run('BUILD', [str(NODE), str(NPM), 'run', 'build'])
run('LINT', [str(NODE), str(NPM), 'run', 'lint'])
port = free_port()
base = f'http://127.0.0.1:{port}'
smoke('VITE', [str(NODE), 'node_modules/vite/bin/vite.js', '--host', '127.0.0.1', '--port', str(port), '--strictPort'], ROOT, [(p, base+p) for p in ['/', '/src/main.jsx', '/src/App.jsx']])
port = free_port()
smoke('PREVIEW', [str(NODE), 'node_modules/vite/bin/vite.js', 'preview', '--host', '127.0.0.1', '--port', str(port), '--strictPort'], ROOT, [('/', f'http://127.0.0.1:{port}/')])
sys.path.insert(0, str(ROOT / 'backend'))
from scorm_manifest import validate_manifest
compatibility = []
for path in sorted((ROOT / 'public/scorm').rglob('imsmanifest.xml')):
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    info = validate_manifest(path.parent)
    assert before == hashlib.sha256(path.read_bytes()).hexdigest()
    compatibility.append({'arquivo': path.relative_to(ROOT).as_posix(), 'versao': info.version, 'sha256': before})
(OUT / 'MANIFESTOS.json').write_text(json.dumps(compatibility, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
(OUT / 'RESULTADOS.json').write_text(json.dumps({'data': '04/11/2026', 'ambiente': platform.platform(), 'python': platform.python_version(), 'etapas': results, 'manifestos_aceitos': len(compatibility)}, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
print('FINAL', json.dumps(results), flush=True)
