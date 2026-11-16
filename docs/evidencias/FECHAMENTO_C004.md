# Fechamento C0-04 — guia operacional

14/11/2026, America/Sao_Paulo. Critério: **“Guia executável por outra pessoa, sem expor credenciais.”** Escopo restrito a instalação/operação/backup/restauração e preparo C0-05/C0-09. Nenhum deploy, commit, push, Excel ou funcionalidade C1.

## Estado inicial confirmado

Checkout limpo em `main/d066988`. Ao contrário do contexto do pedido, C0-03 já está commitada nesse HEAD e foi recebida no último pull; não havia alterações locais a sobrescrever. Confirmados auth_utils, /auth/logout, limite de login e testes C0-03; também os validadores, staging/backup/journal, migração e recuperação C0-01. Fontes da aplicação foram preservados nesta rodada.

## Entrega e critérios atendidos

Criado **docs/GUIA_OPERACIONAL_LMS.md**, reaproveitando AUD-01 e o procedimento C0-01. Cobre:

- arquitetura desenvolvimento/homologação/produção e fronteira entre API, banco, frontend e FTP;
- dependências, instalação, inicialização e configuração privada, incluindo requisitos atuais C0-03;
- migração explícita, limites dos scripts legados e distinção de schema novo/upgrade;
- backup pareado de BD/SCORM/logos, incluindo journal e diretórios ocultos; custódia, agenda/retenção e responsáveis;
- restauração em destino novo, inventário/SHA-256/SQLite/contagens e conferência funcional pelo operador;
- recuperação offline SCORM, escritores parados, destino/fingerprint e rotinas de aceite;
- roteiro condicional MySQL, referenciado em documentação oficial, sem inventar engine/servidor real.

Adicionado **tools/lms_snapshot.py**, utilitário operacional independente da aplicação: backup SQLite pela API apropriada, cópia de espelho SCORM/logos, manifesto de integridade e verificação/restauração sem sobrescrita. Não lê .env, não conecta rede, não agenda/cifra backups e não reconfigura a aplicação. Requer Python 3.11+ e caminhos explícitos; limitações/ACL/coleta FTP/custódia estão no guia. Não é funcionalidade C1 nem substituto do backup gerenciado pelo operador.

## Verificações reais

Ambiente `.venv-c001`: **Python 3.12.14** funcional, com hashlib.file_digest. Nenhuma reinstalação global ou alteração do sistema foi necessária; a pendência de interpretador registrada na C0-03 está resolvida para este checkout.

Execução na raiz:

```powershell
& ./.venv-c001/Scripts/python.exe docs/evidencias/c004/validar.py
```

O procedimento executou, em backend/, os comandos equivalentes com esse mesmo Python:

```powershell
python -m unittest discover -s tests -p test_scorm_*.py -v
python -m unittest discover -s tests -p test_auth_security.py -v
```

| Verificação | Resultado | Evidência em docs/evidencias/c004/ |
|---|---|---|
| Python/runtime e pip check | Python 3.12.14; exit 0, sem dependências quebradas | AMBIENTE.txt, DEPENDENCIAS.txt |
| Suíte SCORM | **66 aprovados, 0 falhas, 0 erros, 0 ignorados**, exit 0 | SCORM.txt |
| Autenticação C0-03 | **11 aprovados, 0 falhas, 0 erros, 0 ignorados**, exit 0 | AUTENTICACAO.txt |
| Backup/verify/restore de fixture | exit 0; BD, conteúdo SCORM, logo e marcador oculto preservados | BACKUP.txt, VERIFICAR.txt, RESTAURAR_FIXTURE.txt |
| Destino existente | Recusado, exit 1 esperado | RECUSAR_SOBRESCRITA.txt |
| Corrupção de conteúdo | Detectada, exit 1 esperado | DETECTAR_CORRUPCAO.txt |
| Restore de cópia corrompida | Recusado antes de criar destino, exit 1 esperado | RECUSAR_RESTORE_CORROMPIDO.txt |

No primeiro ensaio, a limpeza Windows encontrou conexão SQLite ainda aberta. Corrigido o fechamento explícito no utilitário/validador. A execução completa posterior terminou corretamente. Após reforçar a rejeição de junctions/confinamento de arquivos, repetido somente o ensaio operacional com `validar.py --only-operations`, novamente com resultados esperados. Resumos em RESULTADOS.json/RESULTADOS-OPERACAO.json; o segundo identifica o hash final do utilitário. O banco de origem fictício permaneceu com o mesmo hash.

São duas execuções de suíte separadas (66 SCORM + 11 autenticação), não uma alegação de teste único com 77 casos. Os testes incluem dependências simuladas e integrações reais locais já definidas nas fixtures; nenhum servidor externo. Instalação/build/start do frontend não foram repetidos, pois não houve mudança de frontend/dependências; comandos e evidências AUD-01 foram reaproveitados. MySQL/mysqldump não estavam disponíveis no terminal consultado e não foram executados.

## Pendências operacionais e avaliação de encerramento

O operador deve fornecer host/OS, pasta da release e unidade/supervisor real, caminhos/engine/versões do banco, destinos FTP/logos, acessos privados, armazenamento cifrado/externo, agenda/retenção/RPO/RTO, responsáveis e janela de manutenção. Esses parâmetros **não foram inventados nem configurados**. O guia indica exatamente onde são necessários e como agir quando ausentes; o roteiro local é executável sem eles. Não impedem o critério documental C0-04, mas são pré-condições de qualquer execução real.

O ensaio com fixture valida a executabilidade dos comandos, **não conclui C0-05**: não houve escolha/restauração de backup operacional do LMS, medição de RTO ou aceite funcional em ambiente representativo. C0-05 mantém seu estado anterior e exige entrega própria. C0-09 permanece Em análise: infraestrutura externa segregada não comprovada. C0-01 continua Aguardando validação em homologação; passar na suíte local não é aceite externo.

**Status recomendado: C0-04 = Concluído.** Guia reproduzível, compatível com o código e com alternativas claramente condicionadas ao engine/destino; sem credenciais. Próximo passo: preencher o inventário privado com o operador, disponibilizar C0-09 e planejar a prova independente C0-05 com backup pareado, integridade funcional, duração e aceite.

## Arquivos desta entrega

Criados: docs/GUIA_OPERACIONAL_LMS.md; tools/lms_snapshot.py; este relatório; docs/evidencias/c004/validar.py e logs/resumos/FONTES_SHA256.json. Atualizados somente README.md, docs/ARQUITETURA_EXECUCAO_LOCAL.md, docs/SCORM_PUBLICACAO_RECUPERACAO.md e referências de plano/checklist. Sem mudança de autenticação, schema, pacotes SCORM ou regras de negócio. Snapshots de dados de teste permaneceram temporários e foram removidos pelo ensaio; não estão versionados.

## RESUMO PARA ATUALIZAÇÃO DA PLANILHA

**C0-04 — Concluído, 14/11/2026.** Entregue docs/GUIA_OPERACIONAL_LMS.md com instalação, configuração sem segredos, migrações, backup pareado SQLite/SCORM/logos e orientação MySQL, restauração em destino novo, integridade, responsabilidades e recuperação do journal SCORM. Utilitário tools/lms_snapshot.py validado com dados fictícios: backup/verify/restore aprovados, sobrescrita e corrupção recusadas. Python 3.12.14 funcional; 66 testes SCORM e 11 C0-03 aprovados em execuções separadas, sem falhas/erros/ignorados. Evidências em docs/evidencias/c004/; relatório docs/evidencias/FECHAMENTO_C004.md.

Pendências de operação real: inventário privado, serviço/destinos/credenciais, política de backup e ambiente segregado. Não se declarou C0-05 concluída; C0-09 continua Em análise e C0-01 aguarda homologação. Próximo passo: operador preencher parâmetros e preparar prova de restauração C0-05 e recursos C0-09. Sem deploy, commit, push, Excel, dados reais ou C1.
