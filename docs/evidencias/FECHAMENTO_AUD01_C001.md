# Fechamento AUD-01 e revisão local C0-01

04/11/2026 — main/fa3fbab, com alterações locais anteriores preservadas. Sem nova auditoria das 23 tarefas. Sem deploy, commit, push, edição do Excel, dados reais ou funções C1.

## 1. AUD-01: critérios atendidos

Critério original consultado: “README de arquitetura com comandos reproduzíveis e mapa das rotas”, Execução técnica!H2, preservado em `docs/evidencias/auditoria-v3/PLANILHA_REFERENCIA.json`. Não foi criado requisito adicional de acesso à produção.

- README substituiu o template Vite por instalação/start/testes/migração e referências do LMS.
- `docs/ARQUITETURA_EXECUCAO_LOCAL.md` consolida componentes, fluxos, dados, rotas, dependências, variáveis por nome e configuração isolada, sem valores privados. Retiradas afirmações preliminares já superadas sobre API não executável/testes sem dependências.
- Instalação frontend pelo package-lock (`npm ci`, exit 0), pip check, CLI da migração, API/Uvicorn, consultas HTTP, build, Vite dev e preview foram verificados localmente. Versões: Python 3.12.14, Node 24.22.1, npm 11.6.2.
- Mapa exato extraído de /openapi.json em execução: `fechamento-aud01-c001/ROTAS.json`. GET /, /docs, /openapi.json e /catalog retornaram 200; Vite respondeu /, /src/main.jsx e /src/App.jsx; preview respondeu /.

**Pendências do critério AUD-01: nenhuma. Recomendação formal: Concluído.** A confirmação de nome do serviço/supervisor e infraestrutura externa cabe ao operador em C0-04/C0-09 e está explicitamente delimitada no guia; não foi inventado procedimento de deploy.

## 2. C0-01: revisão técnica local encerrada

Revisado o protocolo existente: intenção pending persistida antes do FTP; staging com lista/hash; teste de rename em staging; backup preservado; decisão Course/CatalogState/committed na mesma transação; reconciliação por conexões novas; limpeza não reverte commit confirmado. Marcadores e destino conferidos; falha desconhecida preserva journal/arquivos. Não houve necessidade de alterar código de produção nesta rodada.

Quatro regressões focadas acrescentadas em `backend/tests/test_scorm_publication.py`:

1. Duas publicações simultâneas reais em threads/sessões SQL distintas para o mesmo código: a segunda recebe PublicationBusy antes de alterar FTP; a primeira conclui.
2. Três tentativas sucessivas de restauração falham sem apagar backup/journal ou modificar registro anterior; recuperação final e repetição são idempotentes.
3. Três falhas sucessivas de limpeza preservam versão nova/committed; recuperação posterior finaliza, sem rollback indevido.
4. Resposta de restauração perdida após efeito remoto: nova tentativa reconhece o anterior restaurado e conclui de modo idempotente.

As 62 regressões anteriores permanecem, incluindo FTP loopback real, SQLite real, HTTP ASGI e encerramento abrupto de subprocesso após rename. Total atual: **66 executados, 66 aprovados, 0 falhas, 0 erros, 0 ignorados; exit 0**. Testes novos usam FTP simulado e SQLite real; não são ensaios de múltiplos VPS nem de produção.

Condições confirmadas para consistência: mesmo banco compartilhado entre escritores cooperantes, journal/backup duráveis, destino correspondente, nenhuma manutenção FTP externa ou edição/exclusão legada concorrente, e escritores parados antes da recuperação offline. A PK serializa publicação gerenciada por curso, não toda ferramenta externa. Janelas entre renames e decisão SQL continuam documentadas; não há alegação de transação distribuída.

Não foram encontrados defeitos locais adicionais nos cenários revisados. Limites conhecidos foram tratados como condições de operação e aceite, sem reimplementar a solução. **Recomendação: C0-01 = Aguardando validação em homologação**, pois a revisão técnica local passou e resta a validação/aceite no ambiente real segregado.

## 3. Dependências, migração e compatibilidade

- defusedxml==0.7.1 consta em requirements.txt e está instalado; pip check aprovou. requirements-test declara httpx/pyftpdlib. Venv e ferramentas temporárias estão ignorados; nenhuma instalação global.
- Via subprocessos CLI, criado banco SQLite descartável com estrutura anterior compatível, sem scorm_publications e com Course sintético; executado `migrate_add_scorm_publications.py` duas vezes; conferidos tabela nova e curso preservado. Em seguida, API iniciou com AUTO_CREATE_SCHEMA=false. Sem migração de banco real.
- Consulta CLI de recuperação sem --apply retornou nothing_pending no banco descartável; restauração com efeitos já está coberta pelos testes isolados.
- Os **10 manifestos locais continuam aceitos**: seis SCORM 1.2 e quatro 2004, com hashes preservados. É verificação de manifesto/referências, não nova execução completa dos cursos.

## 4. Comandos, resultados e evidências

Diretório: `docs/evidencias/fechamento-aud01-c001/`. `validar.py` registra comandos completos e configura banco temporário/loopback. Execução: `.venv-c001/Scripts/python.exe docs/evidencias/fechamento-aud01-c001/validar.py`, a partir da raiz. O script usa os caminhos locais do Node/npm descritos nos logs; os comandos equivalentes usuais estão no README.

| Verificação | Resultado | Artefato |
|---|---|---|
| npm ci, ferramentas | exit 0; 137 pacotes instalados | INSTALACAO-NPM.txt, NODE.txt, NPM.txt |
| python -m pip check | exit 0 | DEPENDENCIAS.txt |
| python -m unittest discover -s tests -v, cwd backend | 66/66; exit 0 | TESTES.txt |
| Migração CLI e repetição | exit 0, registro preservado | BANCO_ANTERIOR.txt, MIGRACAO.txt, MIGRACAO_REPETIDA.txt, BANCO_VERIFICADO.txt |
| Uvicorn e HTTP | 200 nos quatro recursos consultados | API-servidor.txt, API-http.json, ROTAS.json |
| npm run build | exit 0; aviso de chunk >500 kB | BUILD.txt |
| Vite dev e preview | HTTP 200; processos encerrados após prova | VITE-http.json, PREVIEW-http.json e logs dos servidores |
| Compatibilidade/preservação | 10 manifestos aceitos; frontend/C0-08/.htaccess intactos | MANIFESTOS.json, PRESERVACAO.json |
| npm run lint | exit 1, inclui venv/terceiros/SCORM | LINT.txt (extrato com hash/local da saída integral) |
| Lint somente de fontes próprios, excluindo diretórios citados | exit 1: 21 erros e 11 avisos preexistentes | LINT-FONTES.txt |

O lint é uma dívida de qualidade preexistente do frontend preservado; não impediu build/start e não é falha do protocolo C0-01. Não foi apresentado como aprovado nem usado para bloquear artificialmente o critério de mapeamento/reprodutibilidade AUD-01. Sua correção ampla permanece fora desta entrega. Não houve teste visual de navegador nem aceite de todas as funções do frontend.

## 5. C0-09 e pendências exclusivamente de homologação

**C0-09 = Em análise.** Preparação documental pronta; ambiente externo segregado ainda não fornecido/identificado/autorizado. Não foi usada produção como substituto. Checklist atualizado em `docs/evidencias/C0-09-CHECKLIST.md`.

O operador deve fornecer banco/URL exclusivos, host/porta/raiz/URL FTP de teste e credencial limitada própria; configurar transporte/certificado e e-mail isolado; aplicar a migração; conferir MLSD/MKD/STOR/RETR/RNFR/RNTO/DELE/RMD e a política de escritores. Exclusão legada/logos exigem conferência separada de destino.

No servidor real de teste, com dados fictícios: upload/rejeição/substituição mantendo vínculos; pasta anterior ausente; falha durante staging/swap/commit; perda de resposta; interrupção/reinício e recuperação offline; falhas sucessivas de restauração/limpeza; publicação simultânea do mesmo código; permissões, TLS e janelas de leitura. Guardar logs sanitizados e aceite técnico/conteúdo. Procedimento de recuperação existente: parar escritores → consultar journal com recover_scorm_publication.py → aplicar --apply após conferir destino → validar BD/arquivos antes de reabrir. Nenhuma etapa externa foi simulada como concluída.

## 6. Arquivos alterados nesta rodada

README.md; docs/ARQUITETURA_EXECUCAO_LOCAL.md; docs/evidencias/C0-09-CHECKLIST.md; backend/tests/test_scorm_publication.py (quatro testes); .gitignore (ferramentas temporárias). Criados este relatório e os artefatos em docs/evidencias/fechamento-aud01-c001/. Ferramentas/cache em tmp/fechamento-aud01, node_modules e dist são locais/ignorados. Implementação de produção C0-01, fontes do frontend, C0-08, pacotes SCORM e evidências históricas foram preservados.

## RESUMO PARA ATUALIZAÇÃO DA PLANILHA

Em 04/11/2026, main/fa3fbab com mudanças locais preservadas: **AUD-01 = Concluído**, pelo critério original de README de arquitetura com mapa de API e comandos reproduzíveis. Instalação, migração descartável, Uvicorn/HTTP, build, Vite dev e preview confirmados. Lint executa, mas mantém dívida preexistente de frontend, registrada sem alteração funcional.

**C0-01 = Aguardando validação em homologação**: revisão local concluída; 66 testes aprovados, zero falhas/erros/ignorados, incluindo quatro regressões novas de concorrência e falhas sucessivas/idempotência. Migração CLI aplicada duas vezes em banco anterior compatível descartável, sem perda de Course; dependências verificadas; dez manifestos continuam aceitos. Condições de consistência/limitações FTP+SQL documentadas, sem defeito local adicional identificado no escopo.

**C0-09 = Em análise**: checklist/preparação concluídos, ambiente externo não comprovado. Próxima ação: disponibilizar banco/FTP/credenciais segregados, aplicar migração e repetir cenários de aceite no servidor real de teste. C0-01 não está Concluído antes desse aceite. Relatório: docs/evidencias/FECHAMENTO_AUD01_C001.md; evidências: docs/evidencias/fechamento-aud01-c001/. Sem deploy, commit, push, alteração do Excel, dados reais ou C1.
