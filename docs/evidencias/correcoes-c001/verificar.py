"""Da raiz: .venv-c001/Scripts/python.exe docs/evidencias/correcoes-c001/verificar.py"""
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'backend'))
from scorm_manifest import validate_manifest

environment = dict(os.environ, PYTHONIOENCODING='utf-8', AUTO_CREATE_SCHEMA='false', DATABASE_URL='sqlite://')
command = [sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v']
run = subprocess.run(command, cwd=ROOT / 'backend', env=environment, capture_output=True, text=True, encoding='utf-8')
header = ('Data: 04/11/2026; America/Sao_Paulo\n'
          f'Ambiente: {platform.platform()}; Python {platform.python_version()}\n'
          f'cwd: {ROOT / "backend"}\nComando: {subprocess.list2cmdline(command)}\n'
          'Tipos: testes unitários; ASGI HTTP in-process + SQLite real/FTP simulado; FTP loopback real + SQLite real.\n'
          'Somente dados sintéticos/temporários. Sem homologação ou produção.\n\n')
(OUT / 'TESTES.txt').write_text(header + run.stdout + run.stderr + f'\nexit={run.returncode}\n', encoding='utf-8')
print(run.stdout + run.stderr)
check = subprocess.run([sys.executable, '-m', 'pip', 'check'], capture_output=True, text=True, encoding='utf-8')
versions = subprocess.run([sys.executable, '-m', 'pip', 'list', '--format=json'], capture_output=True, text=True, encoding='utf-8')
(OUT / 'AMBIENTE.txt').write_text(f'Venv isolado: {sys.prefix}\nPython: {platform.python_version()}\npip check (exit={check.returncode}):\n{check.stdout}{check.stderr}\nPacotes instalados:\n{versions.stdout}', encoding='utf-8')

compatibility = []
counts = Counter()
for manifest in sorted((ROOT / 'public/scorm').rglob('imsmanifest.xml')):
    before = hashlib.sha256(manifest.read_bytes()).hexdigest()
    item = {'arquivo': manifest.relative_to(ROOT).as_posix(), 'sha256': before}
    try:
        info = validate_manifest(manifest.parent)
        item.update(resultado='aceito', versao=info.version, launcher=info.launcher)
        counts[info.version] += 1
    except Exception as error:
        item.update(resultado='rejeitado', motivo=str(error))
        counts['rejeitados'] += 1
    assert hashlib.sha256(manifest.read_bytes()).hexdigest() == before
    compatibility.append(item)
(OUT / 'COMPATIBILIDADE_MANIFESTOS.json').write_text(json.dumps({'resumo': dict(counts), 'escopo': 'Leitura estática de manifesto/referências; não é execução no player nem reimportação ZIP.', 'arquivos': compatibility}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print('Compatibilidade:', dict(counts))
old = json.loads((ROOT / 'docs/evidencias/auditoria-v3/FONTES_SHA256.json').read_text(encoding='utf-8'))
preserved = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == old[name]
             for name in ['backend/routes/sessions.py', 'backend/schemas.py', 'src/App.jsx', 'src/main.jsx', 'public/.htaccess']}
assert all(preserved.values())
(OUT / 'PRESERVACAO.json').write_text(json.dumps(preserved, indent=2) + '\n', encoding='utf-8')
raise SystemExit(run.returncode or check.returncode)
