# Fechamento C0-06 — Integridade durante exclusões e desativações

Data: 18/11/2026
Escopo: preservação de histórico e integridade referencial lógica no backend.
Não houve deploy, acesso a VPS/produção, execução de migração em banco real,
commit, push, alteração de Excel ou implementação de C1.

## Problemas encontrados

O esquema legado usa identificadores lógicos (`student_code`, `course_code`,
`event_id` e `part_id`) sem chaves estrangeiras. As exclusões existentes
apagavam em cascata sessões, matrículas, presenças, perfis e memberships, ou
removiam cursos e arquivos FTP diretamente. Isso podia destruir histórico,
deixar relações inválidas e permitir reutilização perigosa de identificadores.

Também havia caminhos de criação ou alteração que aceitavam referências a
alunos, cursos, eventos, turmas, módulos ou partes inexistentes/inativos. Um
administrador ainda podia lançar presença de evento para pessoa sem vínculo
confirmado com aquele evento. Por fim, um evento podia ser arquivado enquanto
uma publicação SCORM estava em andamento.

## Política adotada

| Registro | Comportamento C0-06 |
|---|---|
| Aluno | `DELETE` passa a desativar a conta. Histórico, perfil, sessões, frequência e auditoria permanecem; matrículas e memberships são revogados, tokens consumidos e a versão de sessão é incrementada. O `student_code` continua reservado. |
| Curso | A exclusão administrativa arquiva o curso (`active=false`, `archived_at`) e nunca apaga sessões, matrículas, partes de frequência ou FTP diretamente. |
| Evento | A exclusão arquiva o evento, preserva contexto histórico, revoga memberships e invalida tokens pendentes. Convites do evento arquivado continuam marcando o escopo da conta para que ela não migre silenciosamente ao catálogo padrão. |
| Convite | A remoção revoga o convite de forma lógica, a membership correspondente sem diferenciar maiúsculas/minúsculas e quaisquer tokens pendentes daquele e-mail/evento. Readicionar exige nova confirmação. |
| Módulo/parte de frequência | Parte com presença ou curso com sessões é arquivada. Módulo com partes é arquivado junto delas. A exclusão física fica limitada a módulo realmente vazio e sem dependências. |

Partes com histórico não podem mais trocar curso ou data. Isso evita alterar
retrospectivamente o contexto e a data exibida da presença. Cursos, módulos e
partes também não podem ser movidos para outro escopo depois de receberem
vínculos acadêmicos.

## Correções implementadas

- Adicionados estados de atividade/arquivamento para aluno, evento, convite,
  módulo e parte; curso recebeu `archived_at`.
- Criada a migração aditiva e idempotente
  `backend/migrate_add_integrity_states.py`. Ela preserva dados existentes e
  normaliza apenas `active=NULL` para ativo.
- Validadas referências antes de criar matrícula, incluir aluno em turma,
  matricular turma, iniciar sessão, criar parte ou lançar frequência.
- Exigido `EventMembership` confirmado e ativo para lançar presença em módulo
  de evento.
- Relatórios administrativos preservam ex-participantes confirmados e itens
  arquivados, identificando seus estados ativos/inativos em vez de apagar o
  histórico.
- Exclusão de evento bloqueia publicação SCORM pendente de curso já associado.
  O journal de publicação também revalida curso e evento imediatamente antes
  do commit final, revertendo a publicação se eles tiverem sido arquivados
  durante o staging.
- Mantidas as verificações de C0-07: conta desativada não autentica, não usa
  token anterior, não confirma e-mail nem redefine senha.

## Arquivos modificados

- `backend/models.py` e `backend/migrate_add_integrity_states.py`;
- `backend/auth_utils.py` e `backend/event_utils.py`;
- `backend/routes/auth.py`, `students.py`, `events.py`, `courses.py`,
  `catalog.py`, `enrollments.py`, `classes.py`, `sessions.py` e
  `attendance.py`;
- `backend/scorm_publication.py`;
- `backend/tests/test_integrity_c006.py`,
  `backend/tests/test_scorm_publication.py` e
  `backend/tests/test_email_verification_c007.py`.

## Evidências de teste

Todos os testes usam SQLite temporário, `TestClient`, FTP simulado ou servidor
FTP local em loopback e arquivos temporários. Não acessam dados reais, VPS ou
serviços externos.

```powershell
cd backend
py -3.12 -W ignore::DeprecationWarning -m unittest discover -s tests -p test_integrity_c006.py -v
py -3.12 -W ignore::DeprecationWarning -m unittest discover -s tests -p test_scorm_publication.py -v
py -3.12 -W ignore::DeprecationWarning -m unittest discover -s tests -p test_email_verification_c007.py -v
py -3.12 -W ignore::DeprecationWarning -m unittest discover -s tests -q
py -3.12 -m compileall -q .
```

| Execução | Resultado |
|---|---|
| Integridade C0-06 | 10 aprovados |
| Publicação SCORM, incluindo corrida com evento arquivado | 25 aprovados |
| Confirmação/vínculos C0-07 compatíveis | 9 aprovados |
| Regressão completa com Python 3.12.10 | 108 aprovados, 0 falhas, 0 erros |
| Compilação de módulos Python | aprovada |

Os cenários C0-06 demonstram exclusão sem dependência, arquivamento de aluno,
curso, evento e frequência com preservação, bloqueio de referências inválidas,
tentativa de reutilização de `student_code`, presença entre eventos, mudança de
vínculos históricos, convite/token revogado, publicação SCORM pendente,
rollback de transação e ausência de relações lógicas órfãs nos registros de
teste.

## Critério de pronto

Critério oficial: **“Excluir ou desativar sem perda indevida e sem registros
órfãos.”**

| Critério | Evidência | Situação |
|---|---|---|
| Histórico acadêmico preservado | Arquivamento e testes de sessão, matrícula, frequência e perfil | Atendido |
| Acesso revogado após desativação | Tokens, memberships, login e matrículas revalidados | Atendido |
| Novos vínculos inválidos bloqueados | Guards de referência e testes negativos | Atendido |
| Alterações de escopo não reescrevem histórico | Bloqueios de curso/evento/data com histórico | Atendido |
| Publicação SCORM compatível com arquivamento | Journal revalidado, bloqueio e teste de corrida | Atendido |
| Regressão com C0-07 | Suíte completa Python 3.12 | Atendido |

**Status recomendado: C0-06 = Concluído**, no escopo de código e testes
isolados desta entrega.

## Limitações e decisões pendentes

- Não foram adicionadas chaves estrangeiras ao banco legado. Os guards cobrem
  os fluxos da API, mas escrita direta no banco, registros órfãos anteriores ou
  corridas entre processos ainda exigem uma futura migração estrutural com
  saneamento de dados e decisão institucional.
- Não há rota de restauração para contas, eventos, cursos, módulos ou partes
  arquivados. A restauração deve ser um procedimento administrativo controlado,
  para não reativar vínculos automaticamente.
- A conta associada somente a evento arquivado continua isolada do catálogo
  padrão. A liberação ou restauração do evento requer procedimento
  administrativo; não foi criada uma regra nova de negócio para isso.
- Pacotes SCORM estáticos permanecem no FTP após arquivamento. A remoção foi
  evitada para não quebrar recuperação e histórico; o controle de acesso a
  `/scorm/` segue como questão de infraestrutura da C0-02.
- Não foi criada unicidade retroativa para `Enrollment`, `ClassStudent` ou
  `AttendanceRecord`, pois isso exige tratar duplicidades legadas antes de
  impor restrições no banco.

## Passo operacional futuro

Antes de iniciar esta versão do backend em um banco existente, realizar backup
e executar explicitamente:

```powershell
cd backend
py -3.12 migrate_add_integrity_states.py
```

Em Linux, utilizar o interpretador Python 3.12 equivalente. A migração não foi
executada fora do ambiente de testes nesta tarefa.

## Resumo para a planilha

**C0-06 — Concluído (código e testes).** Exclusões administrativas passaram a
preservar o histórico por desativação/arquivamento; vínculos inválidos e
mudanças de escopo com histórico são bloqueados; a frequência exige
participação confirmada no evento; convites revogados invalidam tokens; e a
publicação SCORM é coordenada com o arquivamento. Foram incluídos estados
aditivos, migração idempotente e 10 testes específicos. A regressão completa
com Python 3.12.10 aprovou 108 testes. Para produção restam backup e execução
controlada da migração, sem deploy realizado nesta entrega.
