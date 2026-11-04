"""Publicação recuperável com journal SQL e staging FTP verificado por SHA-256.

Recuperação offline: parar escritores antes de chamar recover_publication.
Não existe transação distribuída ou troca sem janela de indisponibilidade.
"""
from contextlib import contextmanager
from datetime import datetime
import ftplib
import hashlib
import io
import os
from pathlib import Path
import posixpath
import ssl
from uuid import uuid4

from sqlalchemy.exc import IntegrityError

from catalog_utils import touch_catalog
from database import SessionLocal
from models import Course, ScormPublication
from scorm_manifest import validate_manifest
from scorm_package import validate_course_code

MARKER = '.iaclube-publication'


class PublicationError(Exception):
    pass


class RecoveryRequired(PublicationError):
    pass


class PublicationBusy(PublicationError):
    pass


def config():
    base = os.getenv('SCORM_FTP_BASE_DIR', '/public_html/scorm').rstrip('/')
    if not base.startswith('/') or base == '' or any(p in {'.', '..'} for p in base.split('/')) or any(c in base for c in '\r\n\\'):
        raise PublicationError('Raiz FTP inválida.')
    return dict(host=os.getenv('SCORM_FTP_HOST', '147.93.37.72'),
                port=int(os.getenv('SCORM_FTP_PORT', '21')),
                user=os.getenv('SCORM_FTP_USER', 'u124251760.lms.iaclube.help'),
                password=os.getenv('FTP_PASSWORD'), base=base,
                tls=os.getenv('SCORM_FTP_TLS', '').lower() == 'true')


def target_key():
    settings = config()
    return hashlib.sha256(repr(tuple(settings[k] for k in ('host', 'port', 'user', 'base', 'tls'))).encode()).hexdigest()


@contextmanager
def open_ftp():
    settings = config()
    ftp = ftplib.FTP_TLS(context=ssl.create_default_context()) if settings['tls'] else ftplib.FTP()
    try:
        ftp.connect(settings['host'], settings['port'], timeout=30)
        ftp.login(settings['user'], settings['password'])
        if settings['tls']:
            ftp.prot_p()
        yield Remote(ftp)
    finally:
        # A falha de QUIT não desfaz uma operação comprovadamente concluída.
        try:
            ftp.quit()
        except Exception:
            ftp.close()


class Remote:
    def __init__(self, ftp):
        self.ftp = ftp

    def listing(self, path):
        result = {}
        for name, facts in self.ftp.mlsd(path):
            kind = facts.get('type')
            if kind in {'cdir', 'pdir'}:
                continue
            if name in {'.', '..'} or '/' in name or '\\' in name or any(ord(c) < 32 for c in name) or kind not in {'file', 'dir'}:
                raise RecoveryRequired('Listagem FTP incompatível ou insegura.')
            result[name] = kind
        return result

    def exists(self, path):
        return posixpath.basename(path) in self.listing(posixpath.dirname(path))

    def owned(self, path, token):
        if MARKER not in self.listing(path):
            return False
        data = bytearray()

        def receive(chunk):
            if len(data) + len(chunk) > 128:
                raise RecoveryRequired('Identificador de publicação inválido.')
            data.extend(chunk)

        self.ftp.retrbinary(f'RETR {path}/{MARKER}', receive)
        return bytes(data) == token.encode('ascii')

    def mkdir(self, path):
        self.ftp.mkd(path)

    def rename(self, source, destination):
        if self.exists(destination):
            raise RecoveryRequired('Destino de troca FTP já existe.')
        self.ftp.rename(source, destination)
        if self.exists(source) or not self.exists(destination):
            raise RecoveryRequired('Troca FTP não confirmada.')

    def remove(self, path):
        items = self.listing(path)
        # Preserva identidade até o fim para permitir retomar limpeza interrompida.
        for name in sorted(items, key=lambda name: name == MARKER):
            kind = items[name]
            child = f'{path}/{name}'
            if kind == 'dir':
                self.remove(child)
            else:
                self.ftp.delete(child)
        self.ftp.rmd(path)

    def tree(self, path, prefix=''):
        files = set()
        for name, kind in self.listing(path).items():
            relative = f'{prefix}{name}'
            if kind == 'dir':
                files.update(self.tree(f'{path}/{name}', relative + '/'))
            else:
                files.add(relative)
        return files

    def stage(self, root, path, token):
        self.mkdir(path)
        self.ftp.storbinary(f'STOR {path}/{MARKER}', io.BytesIO(token.encode('ascii')))
        expected = {MARKER}
        hashes = {}
        for directory, directories, files in os.walk(root):
            relative = Path(directory).relative_to(root).as_posix()
            remote = path if relative == '.' else f'{path}/{relative}'
            for name in directories:
                self.mkdir(f'{remote}/{name}')
            for name in files:
                local = Path(directory) / name
                relative_file = local.relative_to(root).as_posix()
                expected.add(relative_file)
                with local.open('rb') as data:
                    hashes[relative_file] = hashlib.file_digest(data, 'sha256').hexdigest()
                    data.seek(0)
                    self.ftp.storbinary(f'STOR {path}/{relative_file}', data)
        if self.tree(path) != expected:
            raise PublicationError('Conteúdo de staging incompleto.')
        for name, expected_hash in hashes.items():
            received = hashlib.sha256()
            self.ftp.retrbinary(f'RETR {path}/{name}', received.update)
            if received.hexdigest() != expected_hash:
                raise PublicationError('Integridade de staging não confirmada.')
        if not self.owned(path, token):
            raise RecoveryRequired('Identidade de staging não confirmada.')


def paths(operation):
    if operation.target_key != target_key():
        raise RecoveryRequired('Configuração FTP difere do destino registrado.')
    base = config()['base']
    code, token = operation.course_code, operation.token
    validate_course_code(code)
    if len(token) != 32 or any(c not in '0123456789abcdef' for c in token):
        raise RecoveryRequired('Identificador persistido inválido.')
    return dict(final=f'{base}/{code}', stage=f'{base}/.stage-{code}-{token}',
                probe=f'{base}/.probe-{code}-{token}', backup=f'{base}/.backup-{code}-{token}',
                failed=f'{base}/.failed-{code}-{token}')


def recover_publication(code, session_factory=SessionLocal, remote_factory=open_ftp):
    """Idempotente, com escritores parados. Não recuperar uma operação ativa."""
    with session_factory() as db:
        operation = db.get(ScormPublication, code)
        if operation is None:
            return 'nothing_pending'
        locations = paths(operation)
        with remote_factory() as remote:
            final, backup = locations['final'], locations['backup']
            if operation.state == 'committed':
                if not remote.exists(final) or not remote.owned(final, operation.token):
                    raise RecoveryRequired('Banco confirmou publicação, mas versão remota não foi identificada.')
                if remote.exists(backup):
                    remote.remove(backup)
            elif operation.state == 'pending':
                if remote.exists(backup):
                    if remote.exists(final):
                        if not remote.owned(final, operation.token):
                            raise RecoveryRequired('Versão final desconhecida; backup preservado.')
                        remote.rename(final, locations['failed'])
                    remote.rename(backup, final)
                elif operation.had_previous is True:
                    if not remote.exists(final) or remote.owned(final, operation.token):
                        raise RecoveryRequired('Versão anterior não localizada; recuperação manual necessária.')
                elif operation.had_previous is False and remote.exists(final):
                    if not remote.owned(final, operation.token):
                        raise RecoveryRequired('Pasta final desconhecida; não foi removida.')
                    remote.rename(final, locations['failed'])
            else:
                raise RecoveryRequired('Estado de publicação desconhecido.')
            for label in ('stage', 'probe', 'failed'):
                path = locations[label]
                if remote.exists(path):
                    if remote.listing(path) and not remote.owned(path, operation.token):
                        raise RecoveryRequired('Staging sem identidade; preservar para inspeção manual.')
                    remote.remove(path)
        state = operation.state
        db.delete(operation)
        db.commit()
        return 'finalized' if state == 'committed' else 'rolled_back'


def publish_course(root, code, metadata=None, session_factory=SessionLocal, remote_factory=open_ftp):
    validate_course_code(code)
    manifest = validate_manifest(root)
    operation_token = uuid4().hex
    with session_factory() as db:
        existing = db.query(Course).filter(Course.course_code == code).first()
        if metadata is not None and existing is not None:
            raise PublicationError('Código de curso já cadastrado.')
        if metadata is None and existing is None:
            raise PublicationError('Curso não encontrado.')
        operation = ScormPublication(course_code=code, token=operation_token, state='pending', target_key=target_key())
        db.add(operation)
        try:
            db.commit()  # exclusão persistente por PK antes de qualquer operação remota
        except IntegrityError as error:
            db.rollback()
            raise PublicationBusy('Curso possui publicação pendente; verificar recuperação.') from error
        locations = paths(operation)
    try:
        with remote_factory() as remote:
            had_previous = remote.exists(locations['final'])
            if metadata is not None and had_previous:
                raise PublicationError('Pasta FTP já existe para um novo curso; não será sobrescrita.')
            with session_factory() as db:
                operation = db.get(ScormPublication, code)
                operation.had_previous = had_previous
                db.commit()
            remote.stage(Path(root), locations['stage'], operation_token)
            # Verifica RNFR/RNTO de diretórios deste servidor sem tocar a versão ativa.
            remote.rename(locations['stage'], locations['probe'])
            remote.rename(locations['probe'], locations['stage'])
            if had_previous:
                remote.rename(locations['final'], locations['backup'])
            remote.rename(locations['stage'], locations['final'])
            if not remote.owned(locations['final'], operation_token):
                raise RecoveryRequired('Versão publicada não confirmada.')
        with session_factory() as db:
            operation = db.get(ScormPublication, code)
            if operation is None or operation.token != operation_token or operation.state != 'pending':
                raise RecoveryRequired('Intenção de publicação mudou.')
            course = db.query(Course).filter(Course.course_code == code).first()
            if metadata is not None:
                if course is not None:
                    raise PublicationError('Código cadastrado durante a publicação.')
                course = Course(course_code=code, active=True, created_at=datetime.utcnow(), **metadata)
                db.add(course)
            elif course is None:
                raise PublicationError('Curso removido durante a publicação.')
            base_url = os.getenv('SCORM_PUBLIC_BASE_URL', 'https://lms.iaclube.help/scorm').rstrip('/')
            course.scorm_path = f'{base_url}/{code}/{manifest.launcher}'
            course.updated_at = datetime.utcnow()
            touch_catalog(db)
            operation.state = 'committed'
            db.flush()
            payload = {name: getattr(course, name) for name in ('id', 'title', 'course_code', 'scorm_path', 'event_id', 'color_primary', 'passing_score', 'catalog_status')}
            db.commit()  # Course, catálogo e decisão durável na MESMA transação
    except Exception as error:
        # Reconsulta em conexão nova: commit/rename podem ter ocorrido sem resposta.
        try:
            outcome = recover_publication(code, session_factory, remote_factory)
        except Exception as recovery_error:
            raise RecoveryRequired('Publicação pendente de reconciliação; preserve staging/backup e consulte o journal.') from recovery_error
        if outcome != 'finalized':
            raise PublicationError('Publicação cancelada; estado anterior recuperado.') from error
        # O commit ocorreu apesar da exceção do driver.
        with session_factory() as db:
            course = db.query(Course).filter(Course.course_code == code).one()
            payload = {name: getattr(course, name) for name in ('id', 'title', 'course_code', 'scorm_path', 'event_id', 'color_primary', 'passing_score', 'catalog_status')}
        return dict(payload, recovery_pending=False)
    try:
        recover_publication(code, session_factory, remote_factory)
        return dict(payload, recovery_pending=False)
    except Exception:
        # Versão já confirmada no banco: não reverter por falha ao limpar backup.
        return dict(payload, recovery_pending=True)
