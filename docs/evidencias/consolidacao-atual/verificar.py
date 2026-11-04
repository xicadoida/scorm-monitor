"""Revalida a suíte atual sem reescrever evidências históricas."""
import ast
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
env = dict(os.environ, PYTHONIOENCODING='utf-8', AUTO_CREATE_SCHEMA='false', DATABASE_URL='sqlite://')
command = [sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v']
result = subprocess.run(command, cwd=ROOT/'backend', env=env, capture_output=True, text=True, encoding='utf-8')
header = f'Data: 04/11/2026; America/Sao_Paulo\nAmbiente: {platform.platform()}; Python {platform.python_version()}\nComando: {subprocess.list2cmdline(command)}\ncwd: {ROOT / "backend"}\nTestes locais: ZIP/XML reais; SQLite real; HTTP ASGI com FTP simulado; FTP loopback real. Sem homologação.\n\n'
(OUT/'EV-01-testes.txt').write_text(header+result.stdout+result.stderr+f'\nexit={result.returncode}\n',encoding='utf-8')
counts = {}
for path in sorted((ROOT/'backend/tests').glob('test_*.py')):
    counts[path.name] = sum(isinstance(n,ast.FunctionDef) and n.name.startswith('test_') for n in ast.walk(ast.parse(path.read_text(encoding='utf-8'))))
paths = [ROOT/'backend/scorm_package.py', ROOT/'backend/scorm_manifest.py', ROOT/'backend/scorm_publication.py', ROOT/'backend/routes/courses.py']
hashes = {p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
sys.path.insert(0,str(ROOT/'backend'))
from scorm_manifest import validate_manifest
manifestos = []
for path in sorted((ROOT/'public/scorm').rglob('imsmanifest.xml')):
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    info = validate_manifest(path.parent)
    assert before == hashlib.sha256(path.read_bytes()).hexdigest()
    manifestos.append({'arquivo':path.relative_to(ROOT).as_posix(),'versao':info.version,'sha256':before})
(OUT/'VERIFICACAO.json').write_text(json.dumps({'exit':result.returncode,'metodos_por_modulo':counts,'fontes_sha256':hashes,'manifestos_aceitos':manifestos},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(result.stderr[-600:])
print('Métodos:',sum(counts.values()),'; manifestos:',len(manifestos),'; exit:',result.returncode)
raise SystemExit(result.returncode)
