"""Auditoria reproduzível e local: não importa a API nem conecta a BD/FTP.

Executar da raiz: python docs/evidencias/auditoria-v3/auditar.py
Mantém logs desta auditoria separados das evidências anteriores.
"""
import ast
import asyncio
from collections import Counter
from datetime import datetime
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import MagicMock
import zipfile

ROOT = Path(__file__).resolve().parents[3]
OUTPUT = Path(__file__).resolve().parent
BACKEND = ROOT / 'backend'
sys.path.insert(0, str(BACKEND))
from scorm_package import InvalidPackage, extract_package


def isolated_function(path, name, namespace):
    """Executa corpo original; remove apenas decorators, defaults e anotações.

    Não testa HTTP, dependências FastAPI, Pydantic, SQLAlchemy ou persistência.
    """
    tree = ast.parse(path.read_text(encoding='utf-8'))
    function = next(n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name)
    function.decorator_list = []
    function.returns = None
    function.args.defaults = []
    for arg in function.args.args:
        arg.annotation = None
    module = ast.Module(body=[function], type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), str(path), 'exec'), namespace)
    return namespace[name]


def main():
    records = [
        'AUDITORIA V3 — 04/11/2026 — America/Sao_Paulo',
        f'Ambiente: {platform.platform()}; Python {platform.python_version()}',
        f'Comando completo: & "{sys.executable}" docs/evidencias/auditoria-v3/auditar.py',
        f'Pasta de trabalho requerida: {ROOT}',
        'Sem dados reais, conexão FTP, HTTP ou banco; somente arquivos temporários sintéticos.',
    ]
    for command in [['git', 'branch', '--show-current'], ['git', 'log', '-1', '--format=%H %s'], ['git', 'status', '--short'], ['git', 'branch', '-a']]:
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding='utf-8')
        records.extend(['COMANDO: ' + ' '.join(command), result.stdout.strip(), f'exit={result.returncode}'])

    command = [sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v']
    result = subprocess.run(command, cwd=BACKEND, capture_output=True, text=True, encoding='utf-8')
    records.extend(['\nSUÍTE EXISTENTE (cwd backend):',
                    'COMANDO COMPLETO: ' + subprocess.list2cmdline(command),
                    result.stdout, result.stderr, f'exit={result.returncode}'])

    records.append('\nPROVAS ADICIONAIS: não integram o total da suíte existente.')
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        for label, manifest in [('manifesto_xml_malformado', '<manifest'), ('manifesto_vazio', ''), ('xml_sem_manifesto_scorm', '<other/>')]:
            archive = root / f'{label}.zip'
            with zipfile.ZipFile(archive, 'w') as package:
                package.writestr('imsmanifest.xml', manifest)
                package.writestr('scormdriver/indexAPI.html', '<html/>')
            try:
                extract_package(archive, root / label)
                records.append(f'Arquivo temporário real: {label} -> ACEITO (lacuna: conteúdo XML não validado)')
            except InvalidPackage as error:
                records.append(f'Arquivo temporário real: {label} -> REJEITADO: {error}')

    # Falha após remoção do pacote anterior: executa o corpo original da rota,
    # com FTP e BD simulados. Nenhuma publicação ou exclusão real acontece.
    operations = []
    db = MagicMock()
    course = SimpleNamespace(updated_at=None)
    db.query.return_value.filter.return_value.first.return_value = course
    ftp = MagicMock()
    ftp.connect.side_effect = lambda *args, **kwargs: operations.append('connect')
    ftp.login.side_effect = lambda *args: operations.append('login')
    ftp.quit.side_effect = lambda: operations.append('quit')

    async def prepared(*args):
        return 'synthetic-local-root'

    def remove(*args):
        operations.append('REMOVE_ANTERIOR_SIMULADO')

    def upload(*args):
        operations.append('ENVIO_FALHA_SIMULADA')
        raise OSError('falha sintética de comunicação')

    namespace = dict(SessionLocal=lambda: db, Course=SimpleNamespace(course_code=MagicMock()),
                     tempfile=tempfile, prepare_package=prepared, validate_course_code=lambda code: None,
                     InvalidPackage=InvalidPackage, ftplib=SimpleNamespace(FTP=lambda: ftp),
                     FTP_HOST='synthetic-host', FTP_USER='synthetic-user', FTP_PASS='synthetic-password',
                     FTP_BASE_DIR='/synthetic', remove_dir_ftp=remove, upload_dir_ftp=upload,
                     datetime=datetime, touch_catalog=lambda db: None)
    replace = isolated_function(BACKEND / 'routes/courses.py', 'replace_course_file', namespace)
    response = asyncio.run(replace('synthetic-course', object(), object()))
    records.append('Corpo original replace com FTP/BD mocks: ' + json.dumps(dict(operations=operations, response=response, commits=db.commit.call_count), ensure_ascii=False))

    records.append('\nC0-08: corpo original update_session com BD/modelos simulados; NÃO é teste HTTP ou aprovação pedagógica.')
    namespace = dict(SessionLocal=lambda: db, CourseSession=SimpleNamespace(id=MagicMock()),
                     Course=SimpleNamespace(course_code=MagicMock()), datetime=datetime)
    update = isolated_function(BACKEND / 'routes/sessions.py', 'update_session', namespace)
    for label, changes in [('passed_sem_nota', {'status': 'passed'}),
                           ('failed_com_completed_true', {'status': 'failed', 'completed': True}),
                           ('nota_acima_de_100', {'score_raw': 1000})]:
        session = SimpleNamespace(student_id='synthetic-student', course_id='synthetic-course', status='incomplete', completed=False, completed_at=None)
        db.reset_mock()
        db.query.return_value.filter.return_value.first.side_effect = [session, SimpleNamespace(passing_score=80)]
        data = SimpleNamespace(**dict.fromkeys(['status', 'session_time', 'score_raw', 'completed', 'suspend_data', 'lesson_location']))
        vars(data).update(changes)
        update(1, data, SimpleNamespace(is_admin=False, student_code='synthetic-student'))
        records.append(f'{label}: status={session.status}; completed={session.completed}; commit_simulado={db.commit.call_count}')

    try:
        import fastapi
        records.append(f'FastAPI disponível: {fastapi.__version__}')
    except ImportError as error:
        records.append(f'Inicialização API impedida no runtime consultado: {error}')

    checked = []
    for path in sorted(BACKEND.rglob('*.py')):
        ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
        checked.append(path.relative_to(ROOT).as_posix())
    records.append(f'Sintaxe ast.parse: {len(checked)} arquivos backend aprovados (não é import/runtime).')
    hashes = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in [ROOT/'src/App.jsx', ROOT/'src/main.jsx', ROOT/'package.json', ROOT/'public/.htaccess',
                        *sorted(BACKEND.glob('*.py')), *sorted((BACKEND/'routes').glob('*.py')), *sorted((BACKEND/'tests').glob('*.py'))]}
    (OUTPUT/'FONTES_SHA256.json').write_text(json.dumps(hashes, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    (OUTPUT/'EXECUCAO.txt').write_text('\n'.join(records)+'\n', encoding='utf-8')
    print('\n'.join(records))
    return result.returncode


if __name__ == '__main__':
    raise SystemExit(main())
