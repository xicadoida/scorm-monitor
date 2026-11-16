# C0-04 — instalação, operação, backup e restauração do LMS

Guia de 14/11/2026, coerente com `d066988` e C0-01/C0-03. Público: desenvolvedor ou operador autorizado. Nenhum endereço, serviço, credencial, rotina de backup ou acesso externo é presumido. Os comandos locais foram ensaiados com fixtures; ensaio operacional de recuperação/aceite é C0-05, ainda separado.

## 1. Ambientes e informações do operador

Fluxo conhecido: navegador → frontend React/Vite → API FastAPI → SQLAlchemy/banco; administrador → API → FTP/FTPS → conteúdo SCORM público. Gmail OAuth é opcional. `public/.htaccess` exclui `/scorm` do fallback React. O conteúdo SCORM e o banco podem residir em hosts distintos. Mapa e dados: [arquitetura AUD-01](ARQUITETURA_EXECUCAO_LOCAL.md).

| Ambiente | Configuração e regra |
|---|---|
| Desenvolvimento | Banco/arquivos fictícios, API loopback, Vite local. A suíte cria SQLite/FTP descartáveis próprios. |
| Homologação C0-09 | Serviço, banco, raiz/URL SCORM e credenciais próprios; administradores/segredos distintos; e-mail desligado ou caixa de teste. Existência externa não comprovada. |
| Produção | Valores privados definidos pelo operador; migrações explícitas, backup pareado e publicação controlada. Não se executaram ações neste ambiente. |

Antes de operação real, preencher em registro **privado**:

| Informação necessária | Responsável/ação |
|---|---|
| Host/OS, pasta da release, Python/Node, usuário do serviço | Operador de infraestrutura identifica caminhos absolutos, permissões e a revisão instalada. |
| Serviço/supervisor da API, proxy/TLS, pasta web/frontend | Operador fornece comandos reais de parar/iniciar/status/logs. Se usar systemd, verificar a unidade existente; este repositório não fornece seu nome. |
| Engine/versão do banco, arquivo SQLite ou nome do schema MySQL | Operador confirma DATABASE_URL sem copiá-la para logs; usa caminho absoluto e diretório de trabalho backend. |
| Host/porta/raiz/URL e usuário FTP, destino de logos/exclusão | Operador confere todos os destinos; uploads novos configuráveis não alteram automaticamente os legados. |
| Backup: local privado, proprietário, cifragem, cópia externa, agenda/retenção | Administrador define frequência, prazo de retenção, RPO (perda máxima tolerável) e RTO (tempo de recuperação), verifica acesso e monitora sucesso. Nenhuma agenda já implantada é presumida. |
| Aprovação, janela de manutenção, executor e aceite | Responsável do LMS autoriza; operador executa; desenvolvedor valida API; equipe de conteúdo confere cursos. Registrar data/revisão/resultado sem alunos ou segredos. |

Campos de destino/comando são parâmetros obrigatórios de uma execução externa, não lacunas de lógica do guia. Se desconhecidos, **não executar em produção**; obter os valores com o operador. O roteiro local permanece executável sem eles.

## 2. Dependências e configuração privada

Python **3.11+** (a publicação usa hashlib.file_digest); verificado Python 3.12.14. Frontend já verificado com Node 24.22.1/npm 11.6.2; usar versões compatíveis com package-lock. Runtime: `backend/requirements.txt`, incluindo defusedxml. Testes: `backend/requirements-test.txt` (httpx/pyftpdlib). O utilitário de snapshot usa somente a biblioteca padrão Python.

| Variáveis | Uso/obrigatoriedade |
|---|---|
| DATABASE_URL | Banco explícito em operação real; fallback SQLite `./scorm_monitor.db` depende de cwd backend. Preferir arquivo absoluto. Não registrar URL com senha. |
| AUTH_SECRET | Obrigatória para autenticação, exclusiva por ambiente, aleatória com 32+ caracteres; ausente/inválida gera 503. Rotação exige restart de todos os workers e invalida sessões anteriores. |
| ADMIN_EMAILS | Lista privada explícita para administradores. Vazia não cria administrador implícito. |
| IP_HASH_SECRET | Chave própria para auditoria/limite por IP. Sem configuração adequada, hash não é produzido. Não reutilizar AUTH_SECRET. |
| AUTH_TOKEN_TTL_SECONDS | Padrão 28800; faixa aceita 60–86400 segundos. |
| AUTH_LOGIN_MAX_ATTEMPTS / AUTH_LOGIN_WINDOW_SECONDS | Padrão 5/900; controles persistentes C0-03. |
| TRUST_PROXY_HEADERS | false por padrão; true somente com proxy que remova cabeçalhos externos e forneça X-Forwarded-For confiável. Não expor diretamente a API confiando em cabeçalhos forjáveis. |
| ACCESS_LOG_RETENTION_DAYS | Retenção de auditoria, conforme política. |
| AUTO_CREATE_SCHEMA | Manter false/ausente em operação normal; criação automática não substitui migração. |
| SCORM_FTP_HOST/PORT/USER/BASE_DIR/TLS, FTP_PASSWORD, SCORM_PUBLIC_BASE_URL | Obrigatórias antes de publicar em ambiente real, embora existam defaults legados. FTPS é opt-in e valida certificado; conferir suporte do destino. Nunca ensaiar usando defaults de produção. |
| SCORM_MAX_UPLOAD_BYTES/EXTRACTED_BYTES/FILE_BYTES/ENTRIES/EXPANSION_RATIO/MANIFEST_BYTES | Limites, conforme .env.example e capacidade do servidor/proxy. |
| PUBLIC_APP_URL / VITE_API_URL | URL pública da aplicação e URL da API usada pelo frontend em dev/build. VITE_* é pública no bundle: nunca colocar segredo nela. |
| EMAIL_PROVIDER/SENDER/SENDER_NAME, GMAIL_CLIENT_ID/SECRET/REFRESH_TOKEN | Apenas se enviar e-mails; configurar privadamente. Em ensaios/restauração isolada, EMAIL_PROVIDER vazio para não enviar mensagens reais. |
| PASSWORD_RESET_TOKEN_TTL_MINUTES | Validade da recuperação de senha; padrão documentado no exemplo. |

Copiar `.env.example` para `.env` privado no backend, preencher por canal seguro e restringir leitura ao usuário do serviço/operador. Não incluir .env, credenciais ou dumps em Git/evidências. Gerar chaves com `python -c "import secrets; print(secrets.token_urlsafe(48))"` somente em terminal privado; não registrar a saída. Chaves/OAuth e configurações do proxy/serviço exigem custódia separada em cofre/backup privado; o snapshot abaixo não as coleta.

## 3. Instalar, inicializar e migrar

Na raiz, instalação isolada (PowerShell; usar caminhos absolutos dos executáveis se fora do PATH):

```powershell
python -m venv .venv-c001
& ./.venv-c001/Scripts/python.exe -m pip install -r backend/requirements-test.txt
& ./.venv-c001/Scripts/python.exe -m pip check
npm ci
```

Para servidor sem testes, instalar `backend/requirements.txt`. Não modificar Python global. Fonte canônica e comandos completos de banco novo local: [AUD-01](ARQUITETURA_EXECUCAO_LOCAL.md). **Somente em BD novo descartável**, pode criar o schema via `Base.metadata.create_all(engine)` com DATABASE_URL explicitamente isolada. Não usar esse comando para atualizar banco existente.

Backend, a partir de backend/, após configurar o ambiente privado:

```powershell
& ../.venv-c001/Scripts/python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
```

No desenvolvimento pode acrescentar --reload. Em serviço externo, o operador aplica seu supervisor/process manager existente, cwd backend, venv e configuração privada. Não presumir gunicorn/systemd/porta pública nem reiniciar o VPS inteiro. Verificar status/logs, GET / e /docs/OpenAPI. Não imprimir ambiente completo nos logs.

Frontend, outro terminal na raiz: `npm run dev`; acessar **localhost:5173**, autorizado no CORS atual. Para artefato: `npm run lint`, `npm run build`, `npm run preview`. Ajustar VITE_API_URL antes do build; conferir origem de frontend no CORS backend/main.py. Enviar dist e preservar a exceção SCORM no .htaccess somente em uma publicação separadamente autorizada. Preview é servidor local, não deploy.

### Migração de banco existente

1. Identificar versão/engine/schema, guardar backup pareado e parar escritores.
2. Confrontar schema com a release; revisar cada migrate_*.py pertinente. Há scripts que abrem scorm_monitor.db diretamente ou usam PRAGMA SQLite: não executar todos nem pressupor que todos obedecem DATABASE_URL/MySQL.
3. Para baseline anterior compatível da C0-01, executar **em backend/** `python migrate_add_scorm_publications.py` com o Python do venv e DATABASE_URL correta. Cria somente scorm_publications, idempotente; não reescreve Course.
4. C0-03 não acrescentou migração, mas pressupõe schema existente com Student.auth_token_version e AccessEvent. Se faltarem esses recursos, revisar migrate_add_auth_security.py/migrate_add_access_events.py antes de qualquer execução; não improvisar SQL em produção.
5. Conferir tabela/dados, iniciar todos os workers da release e executar checagens. Em erro, manter manutenção e preservar logs. Rollback de código com schema incompatível exige plano de restauração, não downgrade inventado.

## 4. Backup pareado e verificável

**Pré-condição:** parar API/workers, jobs de escrita e administradores/ferramentas FTP externos durante **toda** a coleta de BD + arquivos. Registrar revisão e janela. Parar somente a API sem impedir outro escritor não cria snapshot coerente. Se houver publicação interrompida, preservar journal e todas as pastas relacionadas; não apagar para “limpar” o backup.

Coletar:

- Banco completo, incluindo cursos, alunos, matrículas, tentativas, frequência, perfis, tokens, auditoria, catálogo e scorm_publications.
- Espelho binário completo da raiz SCORM do ambiente, **incluindo ocultos** .stage-*, .probe-*, .backup-*, .failed-* e marcadores .iaclube-publication. O diretório public/scorm local não comprova cópia do FTP real.
- Logos/arquivos adicionais externos referenciados pelo LMS, se usados; código na revisão registrada e configurações de proxy/serviço em custódia separada. Conteúdo remoto HTTP externo ao pacote requer plano próprio do operador.

Se FTP estiver em outro host, com escritores parados, o operador baixa/exporta a raiz com cliente FTPS autorizado em modo binário, com listagem de ocultos, e confere listagem/contagem/tamanhos e relatório de transferência sem falhas. Guardar o espelho local em área privada. O utilitário abaixo valida o espelho fornecido, **não prova que o operador baixou todos os arquivos remotos** nem se conecta ao FTP. Se não houver acesso para coletar uma cópia coerente, manter a manutenção ou reagendar; não chamar um clone do repositório de backup do ambiente.

### SQLite — comandos suportados pelo utilitário local

Executar no host onde o arquivo SQLite é legível e o espelho local de SCORM está disponível, ou sobre uma exportação SQLite consistente produzida pelo operador. Não copiar só o arquivo .db de um banco ativo, ignorando WAL. `tools/lms_snapshot.py` usa a API SQLite de backup e verifica integridade. [Referência oficial Python](https://docs.python.org/3.12/library/sqlite3.html#sqlite3.Connection.backup).

Definir no PowerShell os caminhos absolutos **privados e confirmados** (variáveis sem valores neste exemplo): `$DbFile`, `$ScormMirror`, `$Snapshot`, opcional `$LogosMirror`. `$Snapshot` deve ser novo, fora das origens, em pai existente restrito; nunca dentro do diretório servido pelo site/Git. A partir da raiz da release:

```powershell
python tools/lms_snapshot.py backup --database "$DbFile" --scorm "$ScormMirror" --output "$Snapshot" --revision (git rev-parse HEAD) --writers-stopped
python tools/lms_snapshot.py verify --source "$Snapshot"
```

Se houver logos, acrescentar `--logos "$LogosMirror"` no backup. O flag é confirmação humana de escritores parados, não uma checagem automática. O diretório inclui database.sqlite, scorm/, logos/ opcional e snapshot.json com data UTC, revisão, tamanhos/SHA-256 e contagens não pessoais. Dotfiles são incluídos; links/arquivos especiais e destinos existentes são rejeitados. Diretórios vazios internos não são inventariados; as raízes scorm/logos são mantidas.

Saída exit 0/integrity=ok é condição para guardar como cópia válida. Snapshot sem manifesto final ou com erro é incompleto; não promover nem sobrescrever a origem. Tamanhos e SHA-256 detectam corrupção acidental, não autenticam um backup contra atacante que altere também o manifesto. Manter cópia aprovada imutável/restrita e, se exigido pela política, hash/assinatura externa em custódia independente.

O utilitário não cifra, agenda nem transmite backups. Em POSIX cria raiz 0700; no Windows o operador deve aplicar ACL privada, pois modo POSIX não equivale a ACL. Snapshot contém dados confidenciais: guardar cifrado com ferramenta corporativa aprovada, acesso mínimo e cópia externa independente; verificar essa cópia e monitorar execução/retenção. Não expor backup no webroot nem anexar seu conteúdo às evidências. Registrar somente data/revisão/resultado e contagens necessárias.

### Se o banco real for MySQL

PyMySQL consta nas dependências; nenhum servidor MySQL/configuração real foi identificado. O operador deve confirmar versão, engines, charset/collation e binários compatíveis. O utilitário SQLite **não serve para MySQL**. Roteiro condicional POSIX, não executado nesta rodada:

```sh
mysqldump --defaults-extra-file="$PRIVATE_MYSQL_CONFIG" --single-transaction --quick --routines --triggers --events --hex-blob --result-file="$DUMP_PATH" "$DB_NAME"
```

PRIVATE_MYSQL_CONFIG é arquivo privado com conexão/permissões adequadas, fornecido pelo operador; não usar senha na linha de comando, Git ou logs. DB_NAME e DUMP_PATH são destinos confirmados. Exigir exit 0 e proteger dump/diagnóstico. `--single-transaction` atende tabelas transacionais; tabelas não transacionais e DDL concorrente exigem estratégia de locks/janela do operador. Manter todos os escritores parados também para parear SCORM. Configurações como GTID/tablespaces/privilégios dependem da versão: revisar o comando com DBA, sem ignorar avisos. Guardar dump + espelho SCORM/ocultos + logos + revisão + hashes/custódia como um conjunto da mesma janela. [Manual oficial mysqldump](https://dev.mysql.com/doc/refman/8.4/en/mysqldump.html).

## 5. Restaurar primeiro em destino novo

1. Autorizar a recuperação; identificar a cópia/revisão correta e validar hashes. Preparar ambiente **segregado**, segredos de teste e e-mail desligado. Proteger o original e o estado de erro antes de substituir qualquer serviço.
2. Em SQLite, com `$RestoreWork` sendo diretório novo e privado, executar:

```powershell
python tools/lms_snapshot.py verify --source "$Snapshot"
python tools/lms_snapshot.py restore --source "$Snapshot" --destination "$RestoreWork"
python tools/lms_snapshot.py verify --source "$RestoreWork"
```

O utilitário recusa sobrescrita, verifica antes de copiar e confere novamente hashes/SQLite/contagens no destino. Não altera a configuração da aplicação ou FTP nem reabre usuários. Conservar a cópia original sem modificação. Para usar o banco restaurado, apontar DATABASE_URL ao arquivo absoluto `$RestoreWork/database.sqlite`; não executar create_all ou migrações cegas sobre ele.

3. Enviar o espelho restaurado somente para **nova raiz FTP de teste**, com ocultos preservados, e conferir destino/listagem/tamanhos. Não usar opção de sincronização com exclusão no ambiente original. Definir URL SCORM de teste e todos os destinos legados separadamente; URLs de cursos restaurados podem apontar ao host original, portanto bloquear navegação/publicação externa até revisão. Não executar recuperação automática com configuração ainda de produção.
4. Se houver journal pendente, ler a seção seguinte. Mudar o destino altera target_key e o mecanismo corretamente recusa a reconciliação: não editar token/fingerprint à força. O operador deve preservar a cópia e planejar uma simulação isolada/autorizada; recuperação no destino original exige configuração correspondente e escritores parados.
5. Em MySQL, preparar schema novo, isolado, com charset/collation compatíveis e usuário de teste. Após verificar hashes/dump, em shell POSIX: `mysql --defaults-extra-file="$PRIVATE_RESTORE_CONFIG" --database="$RESTORE_DB" < "$DUMP_PATH"`. Conferir exit/diagnóstico, tabelas/contagens/vínculos; completar SCORM/logos do mesmo conjunto. Ferramentas/servidor não foram ensaiados localmente; não importar dump sobre schema ativo. [Procedimento oficial de recarga SQL](https://dev.mysql.com/doc/refman/8.4/en/reloading-sql-format-dumps.html).
6. Ao restaurar contas de snapshot, rotacionar AUTH_SECRET e reiniciar **todos** os workers: rollback de auth_token_version pode ressuscitar token anteriormente revogado se a chave antiga for mantida. Validar novo login/logout/expiração; manter segredos fora do artefato e políticas de proxy corretas. IP_HASH_SECRET/credenciais externas devem ser recuperados/rotacionados conforme política, em custódia separada.

Troca do ambiente ativo só ocorre após aceite, backup do estado atual e autorização. Em caso de falha, manter manutenção e voltar ao conjunto anterior coerente (código/configuração/BD/arquivos) segundo decisão do operador, não misturar BD antigo com pacote novo sem reconciliação.

## 6. Verificação após recuperação e publicação interrompida

Verificar, na cópia segregada: integrity_check e inventário/hashes; schema compatível; contagens de Course/Enrollment/CourseSession/Student/journal comparadas à cópia; cursos apontando a URLs de teste existentes; matrículas, sessões/conclusões e frequência sem vínculos órfãos; logos/catálogo corretos; /, /docs, /catalog; login/admin/titular e logout; abertura/retomada/conclusão de curso fictício; rejeição de ZIP inválido sem publicação. Testar com dados fictícios e não divulgar registros pessoais em logs.

O utilitário checa integridade física/contagens e arquivos, **não prova integridade relacional/pedagógica nem testa todos os endpoints**. Capturar diferenças/erros para revisão, sem corrigi-los automaticamente. Migrações não são um backup e journal não substitui backup operacional.

Para publicação interrompida, seguir [procedimento C0-01](SCORM_PUBLICACAO_RECUPERACAO.md): parar todos os escritores, preservar journal/staging/backup, confirmar destino/BD e consultar em backend/ `python recover_scorm_publication.py --course CODIGO`. Somente após revisão, executar com `--apply`. Reconsultar, conferir BD/arquivos e só então reabrir escritores. Pending favorece retorno ao estado anterior; committed preserva a versão nova e termina limpeza. Falha desconhecida preserva materiais e exige operador. Nunca apagar journal/backup para desbloquear.

## 7. Rotina, evidências e próximas entregas

Antes de release: código identificado, backup verificado, migrações revisadas, configuração privada aprovada, escritores controlados. Depois: status/logs/HTTP/fluxo fictício e conferência do journal. Monitorar disponibilidade, espaço/quota, falhas FTP/SQL/503 de configuração/recuperação, excesso de 401/429 e sucesso/idade do backup; não registrar headers Authorization ou valores de ambiente. Retenção/alertas/plantão são definidos pelo operador.

Os ensaios deste guia estão em [FECHAMENTO_C004.md](evidencias/FECHAMENTO_C004.md). A C0-05 deve escolher uma cópia efetiva, destino segregado e responsáveis, medir duração/recuperação, conferir integridade funcional/arquivos e obter aceite, com evidências próprias. A C0-09 deve disponibilizar infraestrutura e credenciais segregadas conforme [checklist](evidencias/C0-09-CHECKLIST.md). Nenhuma delas é concluída pela aprovação documental C0-04.
