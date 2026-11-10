# Fechamento C0-03 — autenticação e sessões

Data: 10/11/2026. Escopo limitado à C0-03. Não houve deploy, commit, push, migração em banco real, edição de planilha, dado real ou implementação C1.

## Verificação inicial de sincronização

O checkout iniciou limpo em `064b415` (`main`, após `4b9a1c4`). Foram confirmados como rastreados os mecanismos recuperáveis da C0-01: `scorm_package.py`, `scorm_manifest.py`, `scorm_publication.py`, a migração e o recuperador, modelo `ScormPublication`, integração de upload/substituição em `routes/courses.py`, os cinco arquivos de testes SCORM e este plano/documentação. A contagem histórica de 66 testes C0-01 é coerente com esses arquivos. A observação de “sem commit/push” em `FECHAMENTO_AUD01_C001.md` descreve a rodada histórica; não representa ausência dos artefatos no checkout atual.

## Problemas encontrados

- O exemplo de configuração continha valores previsíveis para `AUTH_SECRET`, `IP_HASH_SECRET`, senha FTP e um administrador padrão (`admin@admin.com`). Uma instalação copiada sem ajuste podia ter segredo conhecido ou privilégio administrativo indevido.
- A expiração era lida no import, aceitava configuração inválida de forma pouco controlada e aceitava token no exato segundo de expiração.
- O logout apenas removia o token do navegador: o token assinado continuava aceito pelo backend até expirar.
- Login distinguia e-mail inexistente de senha errada; hash de senha malformado podia retornar erro 500; não havia limite de tentativas.
- Um proxy reverso poderia fazer todos os usuários parecerem o mesmo IP para um novo limitador, se a origem de `X-Forwarded-For` não fosse tratada explicitamente.

## Correções implementadas

- `AUTH_SECRET` passou a ser obrigatório, com mínimo de 32 caracteres, sem segredo de exemplo versionado. Valores inválidos falham fechados com HTTP 503. O exemplo agora deixa também `FTP_PASSWORD`, `IP_HASH_SECRET` e `ADMIN_EMAILS` vazios. A rotação do segredo invalida assinaturas anteriores e exige novo login.
- O TTL de token é lido e validado na emissão: padrão de 8 horas, mínimo de 60 segundos e máximo de 24 horas. A validação usa `exp <= agora` e rejeita token malformado, adulterado, sem versão, não ASCII ou expirado como 401.
- `POST /auth/logout` incrementa `Student.auth_token_version`, invalidando no servidor todos os tokens ativos daquela conta. A interface chama esse endpoint antes de limpar o armazenamento local; se a rede falhar, ainda remove a sessão apenas do navegador.
- Credenciais inexistentes, incorretas ou com hash corrompido recebem a mesma resposta 401. Uma derivação PBKDF2 fictícia reduz a diferença de tempo entre e-mail existente e inexistente.
- Foi adicionado limite persistente de login com a tabela existente `AccessEvent`, sem mudança de esquema: por conta sempre, e também por IP anonimizado somente quando `TRUST_PROXY_HEADERS=true` e há `X-Forwarded-For` confiável. O padrão é 5 falhas em 15 minutos e a resposta é 429 com `Retry-After`.
- A revisão de rotas confirmou o padrão existente: operações administrativas usam `require_admin`; dados de pessoa/aluno usam `require_self_or_admin` ou verificações equivalentes. Foram mantidas as rotas públicas intencionais de autenticação, catálogo e consulta de slug de evento.

## Configuração operacional

Antes de qualquer deploy, o operador deve preencher o `.env` privado, nunca o versionado:

```env
AUTH_SECRET=<valor aleatório com 32+ caracteres>
IP_HASH_SECRET=<outro valor aleatório com 32+ caracteres>
ADMIN_EMAILS=admin1@dominio.com,admin2@dominio.com
AUTH_TOKEN_TTL_SECONDS=28800
AUTH_LOGIN_MAX_ATTEMPTS=5
AUTH_LOGIN_WINDOW_SECONDS=900
TRUST_PROXY_HEADERS=false
```

Use `TRUST_PROXY_HEADERS=true` somente se o proxy reverso remover cabeçalhos `X-Forwarded-For` recebidos da internet e inserir o IP real do cliente. Sem isso, o limite por conta continua ativo e o componente por IP fica desabilitado para evitar bloqueio coletivo atrás de proxy. Um valor pode ser gerado com `python -c "import secrets; print(secrets.token_urlsafe(48))"`.

Para rotacionar `AUTH_SECRET`, substitua somente o valor no `.env` privado e reinicie todos os workers de API. Tokens emitidos com o segredo anterior passam a retornar 401; esse comportamento foi testado e exige novo login, sem alteração de banco.

## Arquivos modificados

- `backend/.env.example`
- `backend/auth_utils.py`
- `backend/privacy.py`
- `backend/routes/auth.py`
- `backend/security.py`
- `backend/tests/test_auth_security.py`
- `src/App.jsx`
- `docs/evidencias/FECHAMENTO_C003.md`

Não foram alterados modelos, banco, migrações, pacotes SCORM, regras pedagógicas ou fluxos C1.

## Testes e resultados

Os testes novos usam SQLite em diretório temporário, dados fictícios e `TestClient`; não acessam `scorm_monitor.db`, VPS, FTP ou produção.

```powershell
cd backend
python -m unittest discover -s tests -p test_auth_security.py -v
```

Resultado: **11 executados, 11 aprovados, 0 falhas, 0 erros**. A cobertura demonstra:

1. login válido e token utilizável;
2. login inválido, e-mail inexistente e hash malformado;
3. token expirado;
4. logout, reutilização bloqueada e novo login;
5. rotação de `AUTH_SECRET` e rejeição do token anterior;
6. ausência, adulteração e formato inválido de token;
7. 401, 403 por papel e 403 entre alunos;
8. limite sequencial de tentativas e recuperação após a janela;
9. uso de IP apenas com proxy explicitamente confiado;
10. ausência de segredo utilizável no exemplo e falha fechada sem `AUTH_SECRET`;
11. ausência de administrador implícito.

Também foram aprovados `npm run lint` e `npm run build`. O build concluiu com o aviso preexistente de chunk JavaScript acima de 500 KiB, sem erro.

Foi tentada a suíte completa de backend. Os testes SCORM de publicação não podem concluir neste computador porque o único Python funcional local é 3.10.6, enquanto `scorm_publication.py` usa `hashlib.file_digest`, disponível a partir do Python 3.11; o `backend/venv` de Python 3.12 está quebrado e não foi alterado. Isso não é regressão da C0-03: os 11 testes desta tarefa passaram e as fontes SCORM não foram modificadas. A reexecução integral dos 66 testes históricos deve ocorrer em Python 3.11+ antes de um release geral.

## Critérios de pronto e status

| Critério | Evidência | Situação |
|---|---|---|
| Segredos fora do repositório | `.env` ignorado; exemplo sem valores utilizáveis; varredura de arquivos rastreados | Atendido |
| Rotação de segredo | troca de `AUTH_SECRET` invalida token anterior no teste | Atendido |
| Expiração verificável | teste de token vencido e validação de TTL | Atendido |
| Logout verificável | endpoint revoga versão; token reutilizado retorna 401 | Atendido |
| Credenciais/sessões inválidas rejeitadas | testes 401 e tratamento de hash/token malformado | Atendido |
| Permissões protegidas | teste admin, aluno titular e outro aluno | Atendido |
| Tentativas repetidas limitadas | teste 429, janela e recuperação | Atendido |

**Status recomendado: C0-03 = Concluído.** O critério oficial foi atendido com evidência reproduzível em ambiente isolado.

## Limitações remanescentes

- A revogação é por conta, não por dispositivo: logout invalida todos os tokens daquela pessoa. Sessões individuais exigiriam um registro de sessão próprio, fora do escopo atual.
- O token continua em `localStorage`; uma migração para cookie `HttpOnly` exigiria desenho de CSRF e mudança arquitetural deliberada.
- A contagem e o registro de tentativa não formam uma transação distribuída/atômica entre múltiplos workers; o limite é robusto para tentativas sequenciais e melhor esforço sob rajadas simultâneas. Um coordenador de rate limit seria evolução posterior.
- O operador ainda precisa configurar segredos, administradores e confiança de proxy no `.env` privado antes de publicar. Nenhuma configuração de produção foi lida ou alterada.
- A suíte SCORM completa aguarda um interpretador Python 3.11+ funcional para nova prova de regressão global.

## Resumo para atualização da planilha

**C0-03 — Concluído.** Segredos retirados de exemplos versionados e obrigatórios por configuração; rotação de segredo invalida tokens anteriores; administrador sem fallback; tokens com expiração validada; logout revoga tokens no servidor; credenciais inválidas e tokens malformados retornam 401; rotas administrativas e de titularidade foram verificadas; login tem limite persistente de 5 falhas/15 min com 429. Onze testes isolados aprovados. Não houve deploy, migração, dados reais, commit, push, Excel ou C1. Ressalvas: validar a suíte SCORM completa em Python 3.11+ e configurar o `.env` privado antes de publicar.
