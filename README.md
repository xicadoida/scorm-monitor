# LMS IACLUBE — SCORM Monitor

React/Vite no frontend, FastAPI/SQLAlchemy no backend, SQLite local por padrão e pacotes SCORM publicados via FTP. [Arquitetura e mapa de API](docs/ARQUITETURA_EXECUCAO_LOCAL.md).

## Instalar e executar

Ambiente verificado: Python 3.12.14, Node 24.22.1 e npm 11.6.2. Na raiz:

```powershell
python -m venv .venv-c001
& ./.venv-c001/Scripts/python.exe -m pip install -r backend/requirements-test.txt
npm ci
```

Antes de iniciar a API, siga a [configuração isolada e criação do banco descartável](docs/ARQUITETURA_EXECUCAO_LOCAL.md). Banco separado sozinho não isola FTP. Na pasta backend, com essa configuração:

```powershell
& ../.venv-c001/Scripts/python.exe -m uvicorn main:app --reload
```

Em outro terminal, na raiz: `npm run dev`. Frontend: http://localhost:5173; API: http://127.0.0.1:8000; OpenAPI: http://127.0.0.1:8000/docs.

## Testar e migrar

Em backend/: `../.venv-c001/Scripts/python.exe -m unittest discover -s tests -v`. Na raiz: `npm run lint`, `npm run build`, `npm run preview`. Testes usam dados sintéticos e FTP loopback; requerem requirements-test.txt e sockets locais.

A atualização C0-01 exige a tabela scorm_publications. Após revisar backup/apontamento, executar em backend/: `python migrate_add_scorm_publications.py` com o Python do venv, antes do restart da API. A criação automática de schema é desabilitada por padrão. Não usar create_all como migração nem executar todos os scripts indiscriminadamente.

- [Publicação SCORM e recuperação offline](docs/SCORM_PUBLICACAO_RECUPERACAO.md).
- [Resultados e fechamento AUD-01/C0-01](docs/evidencias/FECHAMENTO_AUD01_C001.md).
- [Requisitos de homologação C0-09](docs/evidencias/C0-09-CHECKLIST.md).

Não versionar .env, credenciais, bancos, venv, node_modules ou dist. Preservar public/scorm e .htaccess: SCORM deve escapar do fallback React. Os comandos de teste não fazem deploy.
