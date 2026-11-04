# Auditoria técnica do plano v3 — LMS IACLUBE

Data: 04/11/2026, America/Sao_Paulo. Escopo: as 23 tarefas solicitadas, com prioridade de verificação C0-01. Auditoria do checkout local e provas isoladas; não é homologação, inspeção de produção ou aceite pedagógico. O pedido recebido termina no item 4 dos cenários C0-01; todos os quatro cenários recebidos foram examinados, além das afirmações históricas explicitadas.

## Fonte documental e estado inicial

Arquivo exato `iaclube-plano-visual-evidencias-v3-auditoria-preliminar(1).xlsx` não localizado no workspace/Downloads consultados. Foi localizada e lida, somente para referência, a variante `C:\Users\Usuário\Downloads\iaclube-plano-visual-evidencias-v3-auditoria-preliminar.xlsx`. Não se afirma que as duas variantes sejam idênticas. A variante disponível contém exatamente 23 IDs, 22 status Não iniciado e C0-01 Aguardando validação em homologação, na aba Execução técnica, A2:W24. Critérios H2:H24 e status K2:K24. Extrato com coordenadas e hash em `auditoria-v3/PLANILHA_REFERENCIA.json`. SHA-256 antes/depois da leitura idêntico: bfaf78171a7edb31b3ef229d673b075484ec7d5cd55b0e343cc1e38ed8e31e6f. Nenhuma planilha foi modificada.

Pasta confirmada: `C:\Users\Usuário\Documents\scorm-monitor`. Branch `main`; último commit `fa3fbaba77df92a121c42c98da6968bb9d4c9a8d`, assunto `bugfix email_service`. A branch c0-01-scorm-upload-security não aparece em `git branch -a`; isso só descreve referências locais e remotas já armazenadas. Não houve fetch, commit, push ou deploy.

Já havia alterações não versionadas no início: `backend/routes/courses.py` modificado; AGENTS.md, backend/scorm_package.py, backend/tests/ e docs/ não rastreados. Foram preservadas. O código endurecido e os 16 testes são trabalho da execução anterior nesta conversa, NÃO entregas implementadas novamente nesta auditoria, nem conteúdo do HEAD. Relatórios anteriores continuam intactos. As linhas abaixo referem-se ao working tree auditado; os hashes em `auditoria-v3/FONTES_SHA256.json` identificam essa versão.

## Método e alcance das verificações

Lidos README, AGENTS.md, docs C0/C1 existentes, modelos, schemas, routers, configuração de Vite/FastAPI/SQLAlchemy, scripts de migração e suíte. Buscas de símbolos e arquivos verificaram ausência de modelos/importadores C1, backup/restore e changelog de publicação no código inspecionado. Ausência significa não encontrado no checkout consultado, não inexistência em serviços externos, Git remoto não atualizado ou documentos da equipe.

Frontend: React/Vite, `src/App.jsx` coordena autenticação/navegação/player; páginas em src/pages e componentes em src/components. Backend: FastAPI e routers, SQLAlchemy/SessionLocal em `backend/database.py:8`, modelos em `backend/models.py:6`, contratos em schemas.py. SQLite é fallback; DATABASE_URL pode apontar a outro banco, não foi aberta conexão. `backend/main.py:23` monta a API, `:37` define CORS e `:53` condiciona criação de schema. SCORM é publicado via FTP em courses.py e servido sob /scorm; `public/.htaccess:6` exclui esse caminho do fallback React. Nenhum pacote publicado foi modificado.

Configuração inspecionada por nomes, sem valores privados: DATABASE_URL, AUTO_CREATE_SCHEMA, AUTH_SECRET, ADMIN_EMAILS, AUTH_TOKEN_TTL_SECONDS, IP_HASH_SECRET, TRUST_PROXY_HEADERS, ACCESS_LOG_RETENTION_DAYS, FTP_PASSWORD, PUBLIC_APP_URL, EMAIL_PROVIDER/EMAIL_SENDER/EMAIL_SENDER_NAME, GMAIL_CLIENT_ID/GMAIL_CLIENT_SECRET/GMAIL_REFRESH_TOKEN, PASSWORD_RESET_TOKEN_TTL_MINUTES, VITE_API_URL e os cinco limites SCORM. Host/usuário/base FTP e URL SCORM estão fixos em `backend/routes/courses.py:17` e configuração de logos separada em events.py:21; .env isolado sozinho não protege a publicação de teste.

Migrações: dez scripts backend/migrate_*.py, inspecionados sem execução. Parte abre diretamente `scorm_monitor.db` (por exemplo migrate_add_catalog_fields.py:9 e :23); parte usa engine, mas depende de PRAGMA SQLite (migrate_add_event_id.py:14). DATABASE_URL não redireciona todos os scripts. Não há plano C1 de upgrade/downgrade ou prova de restauração. Não executar todos os scripts cegamente contra outra base.

Comandos previstos na raiz: `npm ci`, `npm run dev`, `npm run lint`, `npm run build`, `npm run preview`. Em backend/: venv, `python -m pip install -r requirements.txt`, configuração privada de banco descartável, `python -m uvicorn main:app --reload`, `python -m unittest discover -s tests -v`. Guia existente: `docs/ARQUITETURA_EXECUCAO_LOCAL.md:44`. Comandos de instalação/start não foram executados nesta auditoria. Python/node/npm não estão no PATH; foi usado Python 3.12.14 do runtime. Import de FastAPI falhou por módulo ausente. UI/API HTTP, migrações e FTP real permanecem não exercitados. Sem alterações JSX/JS nesta auditoria; lint/build não executados.

## Resultado das 23 tarefas

Classificação técnica e status oficial são colunas distintas. Status é recomendação para revisão da equipe, não alteração do Excel. Cada conclusão confronta o critério H da variante disponível. Trabalhos de base preexistentes não foram confundidos com entrega C1 pronta.

| ID | Classificação técnica | Status v3 → recomendado | Evidência, confronto com pronto e pendência |
|---|---|---|---|
| AUD-01 | Parcialmente confirmado | Não iniciado → Em andamento | Routers em backend/main.py:23, persistência em database.py:8, modelos models.py:6 e documentação local docs/ARQUITETURA_EXECUCAO_LOCAL.md:1. Mapa e comandos já existiam no working tree; inicialização API/UI e deploy reproduzível não comprovados. Falta instalação/start isolados; não concluir apenas por mapear arquivos. |
| AUD-02 | Confirmado no código | Não iniciado → Concluído | Upload/replace em backend/routes/courses.py:67 e :141, helper scorm_package.py:26; matriz em docs/PLANO_EXECUCAO_C0_C1.md:23, exemplos em backend/tests/test_scorm_package.py:37. Auditoria reconfirmou fluxo e executou exemplos. Critério é matriz existente/faltante e exemplos, atendido documentalmente e por testes locais; não é aprovação do fluxo FTP. |
| M1-01 | Depende de decisão externa | Não iniciado → Não iniciado | backend/models.py:24 e schemas.py:19 descrevem campos atuais, não dicionário aprovado com Carlo para Curso/Ferramenta/Trilha/Perfil/Área. Nenhum contrato aprovado encontrado. Obter tipos, obrigatoriedade, enums, dono e aprovação externa; não inferir decisão de metadados existentes. |
| C0-01 | Parcialmente confirmado | Aguardando validação em homologação → Em andamento | Helper em backend/scorm_package.py:26 e chamadas courses.py:88/:157 confirmados; 16 testes aprovados. Manifesto malformado aceito, FTP destrutivo e sem recuperação em courses.py:172. Faltam implementação e testes integrados, não apenas homologação; detalhes e provas abaixo. |
| C0-02 | Contradito pelo código | Não iniciado → Em análise | src/App.jsx:692 apresenta iframe sem sandbox; :565 injeta APIs diretamente em contentWindow, presumindo comunicação de mesma origem. src/main.jsx:12 lê token de localStorage. Topologia padrão publica SCORM no mesmo host do LMS (courses.py:21). Código não impõe isolamento de sessão entre pacote e aplicação; cabe testar cabeçalhos/origens reais. Não adicionar sandbox sem desenhar integração compatível. |
| C0-03 | Parcialmente confirmado | Não iniciado → Em análise | backend/auth_utils.py:34/:50/:61/:92 usa segredo por ambiente, HMAC, expiração e versão; troca/reset incrementam versão em routes/auth.py:347/:385. Logout em src/App.jsx:657 apaga token local, não revoga cópia emitida no servidor; não há endpoint logout identificado. Sem prova de segredo efetivo, rotação ou testes de expiração/logout. Não se fez varredura forense de todo histórico Git. |
| C0-04 | Parcialmente confirmado | Não iniciado → Em análise | Documentação arquitetural já presente em docs/ARQUITETURA_EXECUCAO_LOCAL.md:1 cobre stack e comandos, mas não guia operacional completo com responsável, retenção, backup consistente e recuperação. backend/database.py:8 e courses.py:17 mostram dependências separadas BD/FTP. Completar inventário e runbook com operador, sem credenciais. |
| C0-05 | Depende de teste operacional | Não iniciado → Não iniciado | Não encontrado relatório com duração/integridade de restauração BD+arquivos. database.py:8 e migrações não são provas de restore. Requer C0-04, cópia segregada, backup verificável e reconciliação de cursos/matrículas/arquivos; nenhum restore executado. |
| C0-06 | Parcialmente confirmado | Não iniciado → Em análise | models.py:138/:173 guarda vínculos por colunas sem ForeignKey; courses.py:402 remove matrículas/sessões e curso, sem limpar AttendanceModulePart; events.py:197 apaga evento/emails sem tratar cursos/módulos; students.py:127 não limpa RegistrationProfile, PasswordResetToken ou AttendanceRecord. Potenciais órfãos por inspeção, não contagem em BD real. Falta política funcional e testes de integridade/retensão. |
| C0-07 | Parcialmente confirmado | Não iniciado → Em análise | auth_utils.py:44/:107 define admin por e-mail e guarda de rota; attendance.py:448 e insights.py:56 exigem require_admin. Isso não é suíte papel×recurso. Não existem testes de autorização na suíte atual; testar 401/403, titularidade e isolamento por evento com fixtures isoladas. |
| C0-08 | Contradito pelo código | Não iniciado → Em análise | schemas.py:10 aceita status livre, completed e score float sem faixa; sessions.py:74 confia em passed; :89 compara nota fornecida pelo cliente; :104 pode sobrescrever completed. Provas isoladas reproduzem passed sem nota, nota 1000 aprovada e failed/completed=true. Titularidade existe em :68, mas não garante validade da nota. Falta regra pedagógica aprovada, validação de transições e testes HTTP/BD. |
| C0-09 | Depende de teste operacional | Não iniciado → Em análise | courses.py:17/:20 fixa FTP e database.py:8 só permite configuração de BD; .env.example não prova base/arquivos/credenciais segregados. Checklist já existe em docs/evidencias/C0-09-CHECKLIST.md:1. Confirmar com operador ambiente isolado e autorização de falhas; nenhuma conexão remota realizada. |
| C0-10 | Parcialmente confirmado | Não iniciado → Em andamento | backend/tests/test_scorm_package.py:14 possui 16 métodos focados em ZIP; runner tests/run_evidence.py já existe. Sem autenticação, matrícula, autorização, sessão/conclusão ou integração HTTP/BD/FTP. Critério exige regressões dos fluxos críticos, não apenas testes de extração. Manter unittest conforme AGENTS.md; não trocar por pytest por constar em escopo histórico. |
| C1-01 | Não encontrado | Não iniciado → Não iniciado | models.py:24/:96/:138 contém Course, RegistrationProfile PF/PJ e Enrollment por curso. Nenhuma entidade Trilha, Perfil de aprendizagem ou relações curso-ferramenta/trilha identificadas no arquivo completo. Registro PF/PJ não atende perfil pedagógico. Falta diagrama/plano aprovado com rollback; depende de M1-01. |
| C1-02 | Não encontrado | Não iniciado → Não iniciado | migrate_add_catalog_fields.py:26 e migrate_add_registration_profiles.py:10 são migrações de base, não migração C1. Nenhum script para novas tabelas C1 ou teste upgrade/rollback/fresh install localizado entre os dez scripts. Depende de C1-01 e cópia isolada com dados sintéticos. |
| C1-03 | Não encontrado | Não iniciado → Não iniciado | models.py:1 (arquivo completo) sem tabelas-alvo C1; inventário backend/routes e migrate_*.py sem importador/upsert de trilhas/perfis. Falta arquivo final aprovado, regras de validação, vínculos/ordem e prova de segunda execução sem duplicação. Depende C1-02 e trilhas.json final. |
| C1-04 | Depende de teste operacional | Não iniciado → Não iniciado | Course e CRUD existem (models.py:24, courses.py:199), mas não comprovam cargas 29/52. Não se consultou BD/API nem listas editoriais. 29 e 52 são metas documentais; não inventário atual. Falta conferir contagens, vínculos e impedir abertura de planejados, após C1-03 e arquivos aprovados. |
| C1-05 | Parcialmente confirmado | Não iniciado → Não iniciado | routes/catalog.py:46 serializa catálogo e :73/:88 expõe catálogo/last-update; não inclui area/theme/levels/tracks/profiles nem testes de contrato C1/consumidores antigos. Existe base anterior, não extensão C1 concluída. Depende de contrato e C1-04. |
| C1-06 | Não encontrado | Não iniciado → Não iniciado | Enrollment em models.py:138, enrollments.py:38 e progresso sessions.py:155 são por curso; sem matrícula/rota/progresso por trilha encontrados. Faltam regras para planejados, lotes e agregação idempotente. Depende C1-03/C0-10. |
| C1-07 | Não encontrado | Não iniciado → Não iniciado | models.py:24 e catalog.py:46 não contêm entidade/campo Área ou filtro Jurídica/J1–J5. Sem lote editorial aprovado nem proteção completa de planejados. PJ de RegistrationProfile não significa Área Jurídica. Depende C1-04 e revisão editorial. |
| C1-08 | Não encontrado | Não iniciado → Não iniciado | catalog.py:73 fornece uma fonte, não comparador entre LMS/site/dicionário. Nenhum script/relatório de conciliação encontrado no inventário; fontes externas não foram acessadas. Exige IDs/contrato/listas publicados e relatório de divergências, após C1-05. |
| C1-09 | Parcialmente confirmado | Não iniciado → Não iniciado | courses.py:142 preserva código na troca; :355 permite alterar catalog_status; catalog.py:15 aceita coming_soon. Contudo enrollments.py:54/:113 filtra active, não coming_soon; sessions.py:25 verifica matrícula, sem verificar catalog_status. Troca de pacote não altera status automaticamente nem cria histórico de publicação. Falta procedimento e teste fim a fim; depends C1-04 e homologação. |
| C1-10 | Parcialmente confirmado | Não iniciado → Não iniciado | insights.py:50/:105 e attendance.py:443 fornecem estatísticas/relatórios anteriores; perfil medido em insights.py:117 é PF/PJ, não perfil pedagógico. Ausentes métricas por trilha e changelog C1. Critério de export/consulta validada requer fontes autorizadas e proteção de dados; não foram usados alunos reais. Depende C1-06. |

As classificações Contradito pelo código em C0-02 e C0-08 referem-se ao comportamento/garantia desejados, não à afirmação de que as tarefas já estivessem concluídas na v3. Em C0-02, explorabilidade real depende da origem efetiva e dos cabeçalhos, não inspecionados no servidor.

## C0-01 — verificação individual das afirmações históricas

| Afirmação | Resultado independente atual | Base |
|---|---|---|
| Validador compartilhado | Confirmado no working tree, não no HEAD | import courses.py:11; chamadas :88 e :157; scorm_package.py:26 |
| ZIP Slip/caminhos inseguros | Confirmado para cenários cobertos; não prova absoluta para qualquer ZIP | scorm_package.py:58/:96; test_unsafe_paths:57 e test_symlink:68 aprovados |
| ZIP Bomb/limites configuráveis | Parcialmente confirmado | scorm_package.py:29/:41/:80/:106; limites/expansão testados. Não limita recebimento multipart no proxy nem memória da leitura do diretório central; nenhuma prova de carga/concorrência. |
| Pacotes inválidos/corrompidos | Parcialmente confirmado | BadZipFile/CRC/truncamento rejeitados nos testes; manifesto vazio/malformado e XML de outra raiz aceitos em provas reais locais. |
| Staging, backup e rollback FTP | Contradito pelo código atual | courses.py:172 remove pasta anterior e :173 envia diretamente; nenhuma operação rename/staging/backup/reconciliação encontrada. Prova com mocks reproduziu sequência. |
| Recuperação quando pasta anterior ausente | Não encontrada como mecanismo de recuperação | courses.py:25 ignora error_perm em nlst; :50 tenta mkd. Isso pode tolerar caminho ausente, mas também mascara permissão; não restaura pacote nem reconcilia publicação interrompida. Não foi ensaiado no FTP real. |
| 38 testes aprovados | Contradito como contagem atual; relato histórico não verificável | Descoberta atual: 16 testes, todos aprovados. Sem suíte ou log dos 38 no checkout; nenhum teste foi removido nesta auditoria. |
| docs/PLANO_EXECUCAO_C0_C1.md | Confirmado como arquivo local anterior a esta auditoria, não como documento da branch relatada | Documento :1 reconhece criação na execução anterior desta conversa; não rastreado. Presença não comprova aceite/commit nem implementação FTP. |

### Fluxo real e consistência

Upload: require_admin → catalog_status → validar course_code → leitura em blocos de 64 KiB limitada → validar todo diretório ZIP → manifesto único por nome + launcher fixo → extrair com limite e CRC → conectar/login FTP → enviar na pasta final → quit → criar Course/touch_catalog/commit. Não há checagem prévia de conflito course_code na rota; unicidade no modelo pode falhar depois de arquivos enviados.

Replace: require_admin → buscar curso → preparar mesmo pacote → FTP → remover pasta final anterior → enviar novo conteúdo → quit → timestamp/catálogo/commit. Curso mantém identidade, mas disponibilidade e consistência de arquivos não são garantidas. Exceção FTP retorna success=false, com texto interno, e não recria arquivos anteriores.

Falhas: upload interrompido pode deixar pasta parcial; replace interrompido pode perder anterior; quit pode falhar depois do envio; commit pode falhar depois da publicação; não há transação BD/FTP nem journal persistente. Rede ambígua, reinício, concorrência, pasta anterior ausente e reconciliação são pendências de desenvolvimento e de teste. A prova com mocks verifica o corpo real da rota, substitui FTP, BD e prepare_package; não testa suas implementações em conjunto.

### Cenários solicitados e matriz atual

| Cenário | Esperado | Teste/prova | Resultado e limite |
|---|---|---|---|
| Upload válido | Aceitar pacote válido e persistir consistentemente | test_valid_package:37, test_nested_package:41, test_upload_limit_and_untrusted_filename:113 | Extração local aprovada; não houve upload HTTP, FTP ou commit real. EV-03 pendente. |
| ZIP corrompido | Rejeitar sem publicar | test_invalid_zip:45, test_truncated_zip:51, test_crc_corruption:100 | Aprovados; ZIPs sintéticos no filesystem temporário real. |
| Manifesto ausente/múltiplo | Rejeitar | test_missing_manifest:79, test_multiple_manifests:83 | Aprovados; só nome/contagem verificados. |
| Manifesto inválido | Rejeitar documento SCORM inválido | auditar.py gera arquivo vazio, XML truncado e XML other | Os três foram ACEITOS pelo validador; lacuna reproduzida. Não se afirmou validação de XSD. |
| Caminhos maliciosos | Rejeitar antes de extrair | test_unsafe_paths:57, test_symlink:68, test_duplicate_case_alias:75, test_course_code:107 | Aprovados para fixtures existentes. |
| Limites/explosão de tamanho | Rejeitar | test_limits:91, test_expansion_ratio:96 e limite de upload:113 | Aprovados; sem benchmark de carga ou proteção comprovada do servidor multipart. |
| Arquivos suspeitos/launcher ausente | Rejeitar | test_suspicious_files:63 e test_missing_launcher:87 | Aprovados. Lista de extensões é defesa parcial, não análise antimalware; conteúdo HTML/JS é aceito. |
| Substituição com falha FTP | Preservar/restaurar versão anterior | Prova auditar.py, mocks | Remoção anterior simulada antes de falha de envio; resposta controlada sem restauração. Nenhuma exclusão remota real. |
| Rename/rollback/reinício/estado ambíguo | Recuperar e reconciliar | Nenhuma implementação/teste integrado localizado | Pendente EV-05, exige código e ambiente segregado. |
| BD falha depois do envio | Preservar consistência | Ausente | Pendente; não inferir pelo commit simulado das provas. |

Todos os testes de nome nessa matriz estão em `backend/tests/test_scorm_package.py`; os sufixos :n são as linhas nesse arquivo. Testes sintéticos não comprovam compatibilidade dos cursos publicados.

## Execução, resultados e evidências

Da raiz foi executado:

```powershell
& "C:\Users\Usuário\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" docs/evidencias/auditoria-v3/auditar.py
```

O script executou, com cwd backend/, o comando completo:

```powershell
& "C:\Users\Usuário\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m unittest discover -s tests -v
```

Ambiente: Windows 11 10.0.26200, Python 3.12.14. Resultado: **16 executados, 16 aprovados, 0 falhas, 0 erros, 0 ignorados**, exit 0. SubTest agrupa cenários e não aumenta essa contagem. Módulo exercitado pela suíte: backend/scorm_package.py, via backend/tests/test_scorm_package.py. Código das rotas é inspecionado estaticamente e, nas provas adicionais, por corpos de funções com dependências simuladas. As provas não são somadas aos 16 nem descritas como cobertura integrada. Sintaxe de 33 arquivos Python do backend aprovada por ast.parse, não por importação da API. `git diff --check` passou.

| Artefato desta auditoria | Tipo e uso |
|---|---|
| docs/evidencias/auditoria-v3/EXECUCAO.txt | Log real dos comandos Git, comando unittest/saída, provas locais, mocks e impedimento FastAPI |
| docs/evidencias/auditoria-v3/FONTES_SHA256.json | Hashes dos fontes auditados para identificar working tree fora de commit; não inclui .env |
| docs/evidencias/auditoria-v3/PLANILHA_REFERENCIA.json | Extrato de ID/critério/dependência/status com coordenadas e hash do Excel lido |
| docs/evidencias/auditoria-v3/auditar.py | Procedimento reproduzível, sem HTTP/BD/FTP; não é suíte de produção |
| docs/evidencias/auditoria-v3/ler_planilha.py | Procedimento de leitura somente, requer openpyxl disponível no runtime; não altera Excel |
| docs/evidencias/RELATORIO_ATUALIZACAO_PLANO_V3.md | Este relatório com confronto dos 23 IDs e recomendações |

EV-01 atual disponível no log desta auditoria; EV-02 verificável no código e hashes, mas rollback não implementado; EV-06 documentação existente e relatório atual. EV-03/EV-04 de interface/HTTP e EV-05 de homologação permanecem pendentes. Nenhum screenshot criado. Nenhum teste manual de interface, homologação, produção ou restore real realizado. A planilha pode conter relatos históricos, mas os logs atuais não validam retroativamente esses relatos.

## Continuidade da C0 e dependências

1. C0-01: recuperar patch/branch anterior se existir, confrontar com este working tree e concluir validação de manifesto, publicação recuperável e consistência BD/FTP, com regressões isoladas. Não publicar este estado como C0-01 pronta para homologação.
2. C0-04/C0-09: inventário com responsável, backup consistente e destino exclusivo de teste; host/base/URL/credenciais FTP e banco segregados. Checklist preexistente em docs/evidencias/C0-09-CHECKLIST.md. C0-05 somente depois, com restore separado e medição.
3. C0-02/C0-03: tratar relação mesma origem/localStorage e política de tokens; decidir integração segura do runtime antes de mudar iframe. Testar sem aluno real.
4. C0-08, apoiada por C0-10: aprovar regra pedagógica de nota/conclusão e eliminar estados contraditórios; acrescentar contratos, autorização e persistência isolada. C0-06/C0-07 completam integridade e matriz de acesso.
5. M1-01 deve obter definições externas enquanto C0 avança; C1 continua sem execução automática. Não inventar inventário 29/52 ou aprovações do dicionário.

Nesta rodada não se alteraram fontes da aplicação, migrações ou suíte preexistente: foram criados relatório, scripts e evidências de auditoria. As falhas foram reproduzidas e priorizadas; a etapa seguinte é implementá-las e validá-las dentro das prioridades descritas. Sem acesso operacional segregado não é possível concluir a auditoria de runtime nem substituir homologação por relatório.

## Síntese para professores

O sistema já possui cadastro, acompanhamento e catálogo. O envio de cursos ganhou verificações locais, e as dezesseis verificações existentes passaram. Porém um arquivo pode ter o nome de manifesto sem ser um manifesto válido, e uma falha no envio da substituição ainda pode retirar a versão anterior. Também foram encontrados estados contraditórios no registro de aprovação em simulações. Os registros entregues mostram exatamente o que foi testado; não há demonstração no servidor de testes. Trilhas, perfis pedagógicos e os lotes 29/52 ainda não estão comprovados. O próximo passo é terminar a proteção do envio e preparar um ambiente separado antes de testar com a equipe de conteúdo.

## RESUMO PARA ATUALIZAÇÃO DA PLANILHA

Auditoria local de 04/11/2026, main/fa3fbab, considerando alterações não versionadas preexistentes. A variante v3 sem `(1)` foi lida e preservada: 23 tarefas, 22 Não iniciado e C0-01 Aguardando validação em homologação. A identidade com a variante `(1)` não foi presumida. Relatório: docs/evidencias/RELATORIO_ATUALIZACAO_PLANO_V3.md. Evidência atual: docs/evidencias/auditoria-v3/EXECUCAO.txt; critérios da fonte: docs/evidencias/auditoria-v3/PLANILHA_REFERENCIA.json.

Recomendar AUD-01 Em andamento; AUD-02 Concluído exclusivamente pelo critério de matriz e exemplos; M1-01 Não iniciado; C0-01 Em andamento; C0-02/C0-03/C0-04/C0-06/C0-07/C0-08/C0-09 Em análise; C0-05 Não iniciado; C0-10 Em andamento; todas C1-01 a C1-10 Não iniciado. Estes são status oficiais, distintos das classificações técnicas na matriz.

C0-01: validador compartilhado e limites presentes no working tree, 16 testes aprovados, 0 falhas/erros/ignorados. Não encontrados 38 testes nem publicação staging/backup/rollback. Provas locais aceitam manifesto vazio/XML inválido; prova com mocks confirma remoção anterior ao envio. Não é uma tarefa que aguarda apenas homologação. C0-08 aceita passed sem nota, nota 1000 e failed com completed=true nas provas isoladas; falta contrato e validação integrada. Não usar esses mocks como prova de produção.

EV-01, código parcial EV-02 e documentação EV-06 disponíveis; EV-03/04 HTTP/UI e EV-05 homologação pendentes. FastAPI ausente no runtime impediu start da API; UI, FTP, migrações e restore não executados. Sem deploy, commit, push, edição do Excel ou dados reais. Próxima etapa: implementar lacunas C0-01 com testes e resolver C0-04/C0-09; tratar isolamento e conclusão com regras aprovadas, antes de expansão C1.
