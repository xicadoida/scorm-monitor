"""EV-03/04 local: HTTP via socket, autenticação, SQLite e FTP reais/descartáveis."""
import io
import json
import logging
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile
import threading
import time
import zipfile

import httpx
from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import FTPHandler
from pyftpdlib.servers import FTPServer

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT/'backend'),str(ROOT/'backend/tests')]


def main():
    with tempfile.TemporaryDirectory() as directory:
        temp = Path(directory)
        (temp/'ftp/scorm').mkdir(parents=True)
        authorizer = DummyAuthorizer()
        ftp_password = secrets.token_urlsafe(24)
        authorizer.add_user('local-only',ftp_password,str(temp/'ftp'),perm='elradfmwMT')

        class Handler(FTPHandler):
            pass

        Handler.authorizer = authorizer
        logging.getLogger('pyftpdlib').disabled = True
        server = FTPServer(('127.0.0.1',0),Handler)
        thread = threading.Thread(target=server.serve_forever,kwargs={'timeout':0.05,'handle_exit':False},daemon=True)
        thread.start()
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0))
            api_port = sock.getsockname()[1]
        environment = dict(os.environ, DATABASE_URL='sqlite:///'+(temp/'isolated.db').as_posix(),AUTO_CREATE_SCHEMA='false',
                           AUTH_SECRET=secrets.token_urlsafe(48),ADMIN_EMAILS='local-only@example.invalid',EMAIL_PROVIDER='',
                           SCORM_FTP_HOST='127.0.0.1',SCORM_FTP_PORT=str(server.socket.getsockname()[1]),SCORM_FTP_USER='local-only',
                           FTP_PASSWORD=ftp_password,SCORM_FTP_BASE_DIR='/scorm',SCORM_FTP_TLS='false',
                           SCORM_PUBLIC_BASE_URL='https://local-only.invalid/scorm',PYTHONIOENCODING='utf-8')
        os.environ.update(environment)
        from database import Base,engine,SessionLocal
        from models import Student,Course,ScormPublication
        from auth_utils import create_access_token
        from scorm_fixtures import SCORM12
        Base.metadata.create_all(engine)
        with SessionLocal() as db:
            student = Student(student_code='local-only',name='Synthetic',email='local-only@example.invalid',auth_token_version=0,password_hash='unused-local-fixture')
            db.add(student)
            db.commit()
            token = create_access_token(student)
        log = (temp/'api.txt').open('w',encoding='utf-8')
        process = subprocess.Popen([sys.executable,'-m','uvicorn','main:app','--host','127.0.0.1','--port',str(api_port)],cwd=ROOT/'backend',env=environment,stdout=log,stderr=log)
        results = []
        try:
            with httpx.Client(base_url=f'http://127.0.0.1:{api_port}',timeout=30,trust_env=False) as client:
                deadline = time.monotonic()+20
                while True:
                    try:
                        if client.get('/').status_code == 200:
                            break
                    except httpx.TransportError:
                        pass
                    if time.monotonic()>deadline or process.poll() is not None:
                        raise RuntimeError('API local não iniciou')
                    time.sleep(0.1)
                headers = {'Authorization':'Bearer '+token}
                invalid = client.post('/courses/upload',headers=headers,data={'title':'Synthetic','course_code':'invalid-local'},files={'file':('broken.zip',b'not a zip','application/zip')})
                assert invalid.status_code==200 and invalid.json()['success'] is False
                with SessionLocal() as db:
                    assert db.query(Course).count()==0 and db.query(ScormPublication).count()==0
                assert list((temp/'ftp/scorm').iterdir()) == []
                results.append({'evidencia':'EV-04','tipo':'HTTP socket + autenticação real + SQLite/FTP locais reais','status_http':invalid.status_code,'resultado':'ZIP inválido rejeitado; zero cursos/journals/arquivos publicados'})
                data = io.BytesIO()
                with zipfile.ZipFile(data,'w') as package:
                    package.writestr('imsmanifest.xml',SCORM12)
                    package.writestr('scormdriver/indexAPI.html','synthetic local content')
                valid = client.post('/courses/upload',headers=headers,data={'title':'Synthetic','course_code':'valid-local'},files={'file':('valid.zip',data.getvalue(),'application/zip')})
                assert valid.status_code==200 and 'id' in valid.json() and valid.json()['recovery_pending'] is False
                target = temp/'ftp/scorm/valid-local/scormdriver/indexAPI.html'
                assert target.read_text()=='synthetic local content'
                with SessionLocal() as db:
                    assert db.query(Course).count()==1 and db.query(ScormPublication).count()==0
                results.append({'evidencia':'EV-03','tipo':'HTTP socket + autenticação real + SQLite/FTP locais reais','status_http':valid.status_code,'resultado':'Curso inserido e conteúdo publicado conferido; journal finalizado','recovery_pending':False})
            (OUT/'EV-03-04-local.json').write_text(json.dumps({'data':'04/11/2026','ambiente':'loopback/temporário; não homologação','segredos':'Nenhum valor de credencial/token ou .env registrado','resultados':results},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            print('EV-03/04: upload válido e rejeição de ZIP inválido confirmados por HTTP/SQLite/FTP reais locais.')
        finally:
            process.terminate()
            process.wait(timeout=5)
            log.close()
            server.close_all()
            thread.join(timeout=2)
            engine.dispose()


if __name__=='__main__':
    main()
