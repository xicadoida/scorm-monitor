# Fechamento C0-07 — permissões de acesso e comprovação de e-mail

Data: 17/11/2026
Escopo: autorização no backend, vínculo conta-evento e confirmação de posse de
e-mail. Não houve deploy, acesso à produção, migração em banco real, commit,
push, alteração de Excel ou implementação C1.

## Vulnerabilidade corrigida

O modelo anterior usava EventEmail como se fosse autorização: conhecer um
endereço presente na lista de um evento bastava para criar uma conta e receber
aquele escopo. Além de permitir apropriação de dados por e-mail conhecido, a
seleção implícita do primeiro evento era ambígua para endereços em mais de um
evento.

EventEmail agora representa somente um convite. A autorização exige, em todas
as rotas protegidas, uma conta com e-mail confirmado e um EventMembership
confirmado, ativo, específico para o evento e associado ao e-mail atual da
conta. O token de sessão também carrega o contexto de evento assinado, que é
revalidado no banco a cada requisição.

## Fluxo implementado

1. Cadastro e reenvio respondem com mensagem genérica, sem revelar se a conta,
   convite ou evento existem.
2. Uma conta nova fica pendente: não pode autenticar nem usar rotas protegidas
   antes de provar a posse do e-mail.
3. O link enviado contém token aleatório de uso único e expiração configurável.
   Somente o HMAC do token é persistido; o token não vai em resposta de API,
   auditoria ou URL de query. O link usa fragmento de URL.
4. O destinatário define a senha ao confirmar o primeiro cadastro. Assim, quem
   informou e-mail alheio não conserva a senha escolhida antes da prova.
5. A confirmação de um convite cria ou reativa somente a membership daquele
   evento. Um e-mail em dois eventos exige uma confirmação em cada um.
6. A remoção do convite revoga o vínculo ativo. A mudança de e-mail exige senha
   atual, confirmação do novo endereço, invalida sessões e revoga memberships;
   o acesso a evento só volta após nova prova daquele convite.
7. Pedidos e tentativas de confirmação são limitados por janela configurável.
   Tentativas inválidas, vencidas, reutilizadas ou válidas sem senha também
   consomem a cota. A auditoria guarda identificadores HMAC, nunca o token puro.

Recuperação de senha continua com resposta genérica. Ela só é emitida para uma
conta já verificada no contexto permitido e não cria membership de evento por
coincidência de e-mail.

## Dados e migração

Foram adicionados:

- Student.email_verified_at;
- EmailVerificationToken, para token hash, finalidade, evento, expiração e uso;
- EventMembership, com unicidade por aluno/evento, e-mail comprovado, status e
  revogação;
- índice único em LOWER(TRIM(students.email)).

A migração backend/migrate_add_email_verification.py é aditiva e idempotente.
Antes de qualquer DDL, ela detecta duplicidade lógica de e-mail por caixa ou
espaços. Havendo duplicidade, interrompe sem alterar o banco. Ela não marca
contas antigas como verificadas e não cria memberships retroativas.

Para rollout futuro, após backup e correção manual de duplicidades:

    cd backend
    python migrate_add_email_verification.py

Esse comando não foi executado contra produção nesta tarefa.

## Matriz de autorização efetiva

| Perfil | Autenticação e dados próprios | Cursos e frequência | Administração |
|---|---|---|---|
| Visitante | Apenas rotas públicas de login, cadastro, recuperação, catálogo e branding | Não acessa dados pessoais, matrículas, sessões ou frequência | Não |
| Conta pendente/não verificada | Não recebe sessão; confirmação/reenvio apenas | Não | Não |
| Aluno padrão verificado | Apenas própria conta, senha, matrículas, sessões e progresso | Somente cursos padrão ativos; frequência de evento não é exposta | Não |
| Participante de evento confirmado | Apenas própria conta no ambiente cujo evento está no token | Somente cursos, matrículas, sessões e frequência do evento atual; não acessa plataforma padrão nem outro evento | Não |
| Administrador global verificado | Acesso administrativo previsto nas rotas | Auditoria e operação global | Sim |

Um administrador também precisa ter uma conta confirmada; estar listado em
ADMIN_EMAILS não permite apropriar uma conta pública. Alterar student_code,
course_code, session_id, parâmetros ou o slug não concede acesso de outro
aluno ou outro evento. Não existem, no modelo atual, papéis de professor ou
gestor limitado a evento; PF/PJ e convite não são papéis.

## Arquivos alterados

- backend/models.py e backend/migrate_add_email_verification.py;
- backend/auth_utils.py e backend/event_utils.py;
- backend/routes/auth.py, courses.py, enrollments.py, sessions.py,
  attendance.py, students.py e events.py;
- backend/.env.example;
- backend/tests/test_auth_security.py,
  backend/tests/test_authorization_c007.py e
  backend/tests/test_email_verification_c007.py;
- src/App.jsx, src/pages/LoginPage.jsx, RegisterPage.jsx e AdminPage.jsx;
- este fechamento.

As alterações de frontend apenas expõem confirmação/reenvio e passam a mostrar
participantes confirmados, sem substituir as verificações do servidor.

## Evidências de teste

Todos os testes usam SQLite temporário, TestClient, outbox de e-mail em memória
e mocks locais. Não consultam VPS, banco real, Gmail ou produção.

    cd backend
    py -3.12 -m unittest discover -s tests -p test_authorization_c007.py -v
    py -3.12 -m unittest discover -s tests -p test_auth_security.py -v
    py -3.12 -m unittest discover -s tests -p test_email_verification_c007.py -v
    py -3.12 -m unittest discover -s tests -v

| Execução | Resultado |
|---|---|
| Matriz de autorização C0-07 | 11 aprovados |
| Segurança de autenticação C0-03 | 11 aprovados |
| Confirmação e vínculo de e-mail C0-07 | 9 aprovados |
| Suíte completa do backend com Python 3.12 | 97 aprovados, 0 falhas, 0 erros |
| Lint focal de LoginPage | aprovado |
| Build Vite de produção | aprovado; apenas aviso de bundle acima de 500 kB |

A cobertura positiva e negativa comprova confirmação válida; token inválido,
vencido, reutilizado e limitado; cadastro usando e-mail de participante sem
posse; associação por evento somente após confirmação; aluno em outro evento;
e-mail compartilhado por vários eventos; convites duplicados; conta legada;
mudança de e-mail; migração idempotente; e abortamento da migração antes de DDL
quando existem e-mails ambíguos; além de exclusão de conta seguida de
reutilização de student_code sem herdar membership ou dados protegidos.

O lint completo do frontend ainda aponta problemas fora deste escopo em arquivos
existentes da interface. Não foi feita uma refatoração ampla apenas para
silenciá-los; o arquivo alterado pela nova tela de confirmação foi validado
isoladamente e o build de produção concluiu.

## Critérios de pronto

| Critério | Evidência | Situação |
|---|---|---|
| Todos os perfis autorizam somente o previsto | Matriz e guards de servidor revalidados | Atendido |
| Posse de e-mail antes de vínculo protegido | Conta pendente, token de uso único e EventMembership explícita | Atendido |
| Eventos não se associam por coincidência de e-mail | Confirmação específica por evento e testes de múltiplos/duplicados | Atendido |
| Sessões, matrículas, frequência e IDs protegidos | Testes C0-03/C0-07 e revalidação de contexto | Atendido |
| Compatibilidade segura com contas existentes | Sem backfill; confirmação exigida; migração testada | Atendido |
| Regressão do backend | 97 testes aprovados | Atendido |

**Status recomendado: C0-07 = Concluído**, no escopo de código e testes
isolados desta entrega.

## Requisitos operacionais e limitações remanescentes

- Antes de deploy, configurar PUBLIC_APP_URL e o envio transacional real
  (EMAIL_PROVIDER, EMAIL_SENDER, GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET e
  GMAIL_REFRESH_TOKEN, quando Gmail API for o provedor). Sem entrega de e-mail,
  contas e memberships permanecem pendentes por segurança.
- Executar backup e a migração somente depois de resolver duplicidades
  normalizadas. Contas antigas ficarão bloqueadas até confirmarem o endereço;
  isso é intencional, não um backfill automático.
- A exposição estática de pacotes em /scorm/... não foi alterada. Ela pertence
  à C0-02 e exige solução de infraestrutura como proxy autenticado, gateway ou
  URL assinada.
- Módulos de frequência com event_id nulo continuam globais por regra atual e
  podem aparecer para o participante apenas com os próprios registros. Isso
  não expõe dados de outro evento, mas, se a política for isolar também esses
  módulos visualmente, todos devem receber event_id explícito em tarefa futura.
- Os avisos de datetime.utcnow() do Python 3.12 são dívida técnica preexistente
  de datas sem fuso e não causaram falhas nesta entrega.

## Resumo para a planilha

**C0-07 — Concluído (código e testes).** A lista de e-mails de evento deixou
de conceder acesso. Cadastro fica pendente até confirmação de posse, e cada
evento exige EventMembership explícita e revalidada. Foram incluídos tokens
HMAC de uso único, expiração, limites de tentativas, troca segura de e-mail,
migração sem backfill e testes para cenários de apropriação, múltiplos eventos,
contas legadas, exclusão/reutilização de identificadores e alteração de
identificadores. A regressão completa executou 97 testes aprovados. Para
produção restam somente os passos operacionais:
backup, resolução de e-mails duplicados, migração e configuração/validação do
envio de mensagens.
