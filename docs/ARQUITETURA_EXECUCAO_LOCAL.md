# AUD-01 — arquitetura e execução reproduzível

Fechamento local de 04/11/2026, main/fa3fbab com alterações locais preservadas. Critério original: “README de arquitetura com comandos reproduzíveis e mapa das rotas” (Execução técnica!H2, extrato em evidencias/auditoria-v3/PLANILHA_REFERENCIA.json). Este documento consolida o estado atual; os relatórios anteriores preservam o histórico.

## Componentes, dados e fluxos

| Área | Arquivos e responsabilidade |
|---|---|
| UI | src/main.jsx inicia React e acrescenta Bearer às requisições da API; src/App.jsx coordena login, navegação, sessão, runtime SCORM 1.2/2004 e iframe. src/scorm.js é adaptador auxiliar; o runtime integrado está em App.jsx. |
| Telas/componentes | src/pages: Login, Register, Dashboard, Admin, Report e CoursePlayer; src/components: navegação, rodapé e cartões; CSS e styles cuidam da apresentação. |
| API | backend/main.py inclui routers e CORS; routes contém endpoints; schemas.py define contratos Pydantic. |
| Identidade | auth_utils.py implementa Bearer HMAC, expiração, versão de token e guardas admin/titular; security.py trata senhas; email_service.py integra Gmail opcional; privacy.py registra acessos com hash IP. |
| Persistência | database.py configura engine, Base e SessionLocal; models.py define entidades; catalog_utils.py altera versão do catálogo na transação. |
| Publicação | scorm_package.py valida ZIP; scorm_manifest.py confere XML/referências; scorm_publication.py gerencia staging/backup/journal; recover_scorm_publication.py reconcilia com escritores parados. |
| Arquivos | public/scorm contém pacotes; public/.htaccess desvia /scorm do fallback React. Vite gera dist, sem publicar servidor. |

Fluxo de acesso: login → token → chamadas autenticadas → matrícula → sessão → iframe/runtime → progresso/nota → BD/relatórios. Catálogo: consulta pública → Course/Event/CatalogState → JSON e last-update. Publicação: admin → ZIP/manifesto → intenção pending → staging/hash/rename/backup → commit Course+catálogo+committed → limpeza. Garantias e janelas FTP/BD no [procedimento C0-01](SCORM_PUBLICACAO_RECUPERACAO.md).

SQLAlchemy usa SQLite como fallback, configurável por DATABASE_URL. Course representa curso/código/URL/nota/metadados; Student é a conta; Enrollment liga aluno e curso por código; CourseSession registra tentativa/status/nota/bookmark/tempos. Event/EventEmail delimitam eventos; ClassGroup/ClassStudent agrupam alunos; AttendanceModule/Part/Record registram frequência. RegistrationProfile armazena PF/PJ/termos, não perfil pedagógico. AccessEvent registra auditoria; PasswordResetToken guarda hash de recuperação; CatalogState versiona catálogo; ScormPublication guarda intenção/decisão da publicação. Vínculos não implicam FKs/cascatas abrangentes: parte da integridade é manual na aplicação.

## Mapa de API

| Router | Operações principais |
|---|---|
| raiz | GET /, /docs e /openapi.json |
| auth | POST /auth/login, register, forgot-password, reset-password, change-password |
| courses | POST /courses/upload; POST /courses/{course_code}/replace-file; GET/POST /courses; GET /courses/public; PUT/DELETE /courses/{course_code} |
| sessions | POST /sessions/start; POST /sessions/{session_id}/update e finish; GET /sessions; GET /progress/{student_id}/{course_id} |
| students | GET/POST /students; PUT/DELETE /students/{student_code}; POST reset-password e delete-account |
| enrollments | POST /enrollments; POST /students/{student_code}/enroll/{course_code}; GET /students/{student_code}/courses |
| classes | GET/POST /classes; GET/POST /classes/{class_id}/students; GET student-codes; POST enroll |
| events | GET/POST /events; GET /events/slug/{slug}; PUT/DELETE /events/{event_id}; POST logo; GET/POST/DELETE emails |
| attendance | CRUD /attendance/modules e parts; GET/PUT /attendance/students/{student_code}; GET event-progress e reports |
| catalog | GET/OPTIONS /catalog e /catalog/last-update |
| insights | GET /admin/insights/summary, profile-stats, access-log, ip-activity |

Contratos completos são expostos em OpenAPI. [ROTAS.json](evidencias/fechamento-aud01-c001/ROTAS.json) contém o mapa exato obtido da API em execução. Consultas HTTP loopback confirmaram /, /docs, /openapi.json e /catalog; isso não equivale a testar cada rota.

## Instalação e execução isolada (PowerShell)

Ambiente verificado: Python 3.12.14, Node 24.22.1 e npm 11.6.2. requirements fixa FastAPI/SQLAlchemy e inclui defusedxml em runtime; requirements-test acrescenta httpx e pyftpdlib. package-lock fixa a resolução React/Vite/scorm-again/ESLint. Na raiz:

```powershell
python -m venv .venv-c001
& ./.venv-c001/Scripts/python.exe -m pip install -r backend/requirements-test.txt
& ./.venv-c001/Scripts/python.exe -m pip check
npm ci
```

Os comandos usam o venv diretamente, sem alterar a política de execução de scripts. Nesta máquina Python/Node não estavam no PATH: foram usados executáveis do runtime e npm oficial local, com caminhos completos nos logs. Em outra máquina, disponibilizar os executáveis no terminal ou usar caminhos absolutos.

Configuração para **banco novo descartável**, na raiz:

```powershell
$localDb = [System.IO.Path]::GetFullPath('.venv-c001/local-dev.db')
$env:DATABASE_URL = 'sqlite:///' + $localDb.Replace('\', '/')
$env:AUTO_CREATE_SCHEMA = 'false'
$env:EMAIL_PROVIDER = ''
$env:AUTH_SECRET = & ./.venv-c001/Scripts/python.exe -c "import secrets; print(secrets.token_urlsafe(48))"
$env:SCORM_FTP_HOST = '127.0.0.1'
$env:SCORM_FTP_PORT = '1'
$env:SCORM_FTP_USER = 'local-only'
$env:SCORM_FTP_BASE_DIR = '/local-only'
$env:SCORM_PUBLIC_BASE_URL = 'http://127.0.0.1:5173/scorm'
Push-Location backend
& ../.venv-c001/Scripts/python.exe -c "from database import Base,engine; import models; Base.metadata.create_all(engine)"
& ../.venv-c001/Scripts/python.exe migrate_add_scorm_publications.py
& ../.venv-c001/Scripts/python.exe -m uvicorn main:app --reload
```

A chave gerada permanece no terminal; não exibi-la em evidências. create_all acima é exclusivamente para banco novo, não migração de produção. A porta FTP local deliberadamente não fornece publicação; a suíte cria seu próprio servidor. Não enviar pacotes ao destino legado para testar a UI. Encerrar com Ctrl+C e executar Pop-Location ao terminar.

Em outro terminal, na raiz: `npm run dev`. VITE_API_URL tem fallback http://127.0.0.1:8000. Acessar frontend por localhost:5173, origem autorizada pelo CORS, e API por 127.0.0.1:8000/docs. Em backend/, executar `../.venv-c001/Scripts/python.exe -m unittest discover -s tests -v`. A suíte usa SQLite/arquivos temporários e sockets loopback; não usa o banco de desenvolvimento.

Build/qualidade na raiz: `npm run lint`, `npm run build`, `npm run preview`. Preview serve dist localmente, sem enviar arquivos à hospedagem. Resultados reais e falhas preexistentes de lint são registrados no fechamento; comando reproduzível não significa aprovação de toda a qualidade do frontend.

## Migração e configuração operacional

AUTO_CREATE_SCHEMA=false é o comportamento normal. Scripts migrate_*.py devem ser revisados individualmente: alguns abrem scorm_monitor.db diretamente ou dependem de PRAGMA SQLite, sem seguir genericamente DATABASE_URL. Para atualização C0-01 de estrutura anterior compatível, executar somente `migrate_add_scorm_publications.py`, com BD/backup revisados e escritores parados: cria a tabela nova via engine, sem modificar Course. Nesta rodada o CLI foi executado duas vezes em BD descartável anterior compatível, com curso preservado. Outro banco/versão exige validação do operador.

Variáveis privadas em backend/.env.example: DATABASE_URL/AUTO_CREATE_SCHEMA; AUTH_SECRET/TTL/ADMIN_EMAILS; IP_HASH_SECRET/TRUST_PROXY_HEADERS/retenção; EMAIL_PROVIDER/SENDER/NAME, GMAIL_CLIENT_ID/SECRET/REFRESH_TOKEN e PUBLIC_APP_URL; PASSWORD_RESET_TOKEN_TTL_MINUTES; FTP_PASSWORD; SCORM_FTP_HOST/PORT/USER/BASE_DIR/TLS e SCORM_PUBLIC_BASE_URL; limites SCORM_MAX_UPLOAD_BYTES/EXTRACTED_BYTES/FILE_BYTES/ENTRIES/EXPANSION_RATIO/MANIFEST_BYTES. Frontend usa VITE_API_URL. CORS é explícito em main.py; Vite não configura proxy.

Upload/replace/recuperação usam SCORM_FTP_*. Exclusão legada e logos ainda têm configuração própria. Banco separado sozinho não isola FTP. Para homologação, configurar todos os destinos e não exercitar essas outras rotas em produção.

Publicação conhecida: build Vite → dist em hospedagem estática/Apache preservando exceção /scorm → FastAPI em serviço separado → migrações explícitas antes do restart da API. Nome do serviço, supervisor, acesso ao host e rotina de backup devem ser informados pelo operador; não foram inventados comandos de deploy. Esses itens operacionais pertencem a C0-04/C0-09. Não impedem o cumprimento do README/mapa reproduzível AUD-01. [Recuperação](SCORM_PUBLICACAO_RECUPERACAO.md) e [checklist C0-09](evidencias/C0-09-CHECKLIST.md).

Instalação, dependências, migração, start Uvicorn/HTTP, build, Vite e preview têm registros em `evidencias/fechamento-aud01-c001/`. Status formal e limitações no [fechamento](evidencias/FECHAMENTO_AUD01_C001.md).
