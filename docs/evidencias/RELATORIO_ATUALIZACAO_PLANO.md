# Relatório vigente para atualização do plano C0/C1

04/11/2026, America/Sao_Paulo. Continuidade limitada a AUD-01, AUD-02, C0-01, C0-09 e C0-10. main/fa3fbaba77df92a121c42c98da6968bb9d4c9a8d; alterações locais de código, testes, README e docs já presentes e preservadas. Não foi feito fetch, deploy, commit ou push; estado de infraestrutura externa não inferido do Git. Branch c0-01-scorm-upload-security não aparece nas referências locais inspecionadas anteriormente. Os resultados históricos de 38 testes não descrevem a suíte atual.

Este relatório sucede a consolidação inicial, preservada byte a byte em `docs/evidencias/RELATORIO_ATUALIZACAO_PLANO_SNAPSHOT_INICIAL.md`. Estados anteriores abaixo distinguem registro da planilha v3 (extrato já existente em auditoria-v3/PLANILHA_REFERENCIA.json) do fechamento recente FECHAMENTO_AUD01_C001.md. Nenhum Excel foi consultado novamente ou alterado nesta rodada.

## AUD-01

- **Estado anterior:** planilha v3 Não iniciado; fechamento recente Concluído.
- **Estado técnico e status recomendado:** README/arquitetura/mapa de 47 caminhos da API e comandos locais verificados; **Concluído**, mantendo o critério original “README de arquitetura com comandos reproduzíveis e mapa das rotas”.
- **Já existia:** README atualizado, docs/ARQUITETURA_EXECUCAO_LOCAL.md, prova de instalação, migração CLI em BD descartável, start Uvicorn/HTTP, build, Vite e preview.
- **Agora:** conferidos os documentos e vínculos com as evidências; consolidação vigente sem refazer o mapeamento nem alterar a aplicação.
- **Testes/evidências:** nova suíte backend 66/66 em `docs/evidencias/consolidacao-atual/EV-01-testes.txt`. Reprodutibilidade anterior preservada em `docs/evidencias/fechamento-aud01-c001/`: INSTALACAO-NPM.txt, DEPENDENCIAS.txt, ROTAS.json, API-http.json, BUILD.txt, VITE-http.json, PREVIEW-http.json, MIGRACAO*.txt e BANCO_VERIFICADO.txt. Esses comandos de startup/build não foram repetidos nesta rodada.
- **Pendências/bloqueios:** nenhuma do critério AUD-01. Lint de fontes próprios mantém 21 erros/11 avisos, registrado no fechamento, sem alteração do frontend; dívida separada, não apresentada como aprovação. Nome do serviço/backup externo compete à operação C0-04/C0-09.
- **Próxima ação/justificativa:** manter documentação junto a futuras alterações; não reabrir a tarefa somente por indisponibilidade de homologação. Critério já cumprido e evidências mantidas.

## AUD-02

- **Estado anterior:** planilha v3 Não iniciado; auditoria/fechamento recentes Concluído.
- **Estado técnico e status recomendado:** rotas/validador/manifesto/FTP/journal revisados, com matriz vigente de casos aprovados e pendentes; **Concluído**.
- **Já existia:** implementação compartilhada, documentação de protocolo e matriz histórica anterior às correções.
- **Agora:** criada `docs/evidencias/consolidacao-atual/MATRIZ_SCORM.md`, com fluxo atual, ordem das verificações, limites, erros e falhas parciais. Distingue auditoria concluída de homologação pendente.
- **Testes/evidências:** 66 testes aprovados novamente e demonstrações HTTP locais novas, em EV-01-testes.txt e EV-03-04-local.json no mesmo diretório.
- **Pendências/bloqueios:** nenhum item documental do critério de matriz e exemplos; cenários reais do servidor externo pertencem à validação C0-01/C0-09.
- **Próxima ação/justificativa:** usar a matriz no aceite em homologação. A atualização acompanha o código atual e mantém a conclusão da auditoria sem atestar produção.

## C0-01

- **Estado anterior:** v3 Aguardando validação em homologação com relato antigo de 38 testes; revisão posterior Em revisão; último fechamento Aguardando validação em homologação.
- **Estado técnico e status recomendado:** ZIP/XML/referências e publicação staging/hash/backup/journal presentes e testados; **Aguardando validação em homologação**.
- **Já existia:** scorm_package.py/scorm_manifest.py compartilhados, scorm_publication.py, tabela/migração ScormPublication, recuperação offline, tratamento de ambiguidade e 66 testes. Revisão técnica local estava encerrada.
- **Agora:** nenhuma correção funcional necessária nos cenários examinados. Nova execução da suíte, hashes de fontes/manifests, matriz atual e demonstração autenticada via HTTP socket com SQLite/FTP reais locais, sem mocks das dependências.
- **Testes reais:** `python -m unittest discover -s tests -v`, cwd backend, executado com `.venv-c001/Scripts/python.exe`; Windows 11, Python 3.12.14. **66 executados/aprovados, 0 falhas, 0 erros, 0 ignorados; exit 0**. Módulos: package 16, manifest 14, publication 24, API 9, FTP local 3. Os dois cenários adicionais de demonstração NÃO aumentam esse total. Dez manifestos continuam aceitos, seis SCORM 1.2/quatro 2004, sem modificação.
- **Evidências:** EV-01-testes.txt, VERIFICACAO.json, EV-03-04-local.json e scripts em `docs/evidencias/consolidacao-atual/`; código identificado por hashes no JSON; garantias/limites em docs/SCORM_PUBLICACAO_RECUPERACAO.md. Resultados anteriores continuam nos diretórios correcoes-c001 e fechamento-aud01-c001.
- **Pendências:** homologar servidor/permissões/MLSD/rename/TLS, falhas reais, reinício/recuperação e política de escritores, com aceite técnico/conteúdo. Não há transação distribuída nem disponibilidade contínua: existem janelas entre FTP e SQL. Edição/exclusão legadas ou FTP externo concorrentes devem ser impedidos; recuperação offline exige escritores parados. Journal/backup/destino precisam permanecer íntegros.
- **Bloqueios/dependências:** C0-09 segregada, configuração/credenciais privadas e operação/backup C0-04. Sem acesso externo identificado/autorizado; não foi usada produção. A migração scorm_publications precisa ser aplicada no destino autorizado antes de usar o backend atualizado; só foi testada localmente.
- **Próxima ação/justificativa:** executar checklist no ambiente real de teste e obter aceite. Resultados novos confirmam prontidão local; não justificam Concluído nem retorno a diagnóstico inicial de implementação ausente.

## C0-09

- **Estado anterior:** v3 Não iniciado; fechamento recente Em análise.
- **Estado técnico e status recomendado:** preparação/checklist/procedimento prontos, ambiente externo não comprovado; **Em análise**.
- **Já existia:** requisitos detalhados em docs/evidencias/C0-09-CHECKLIST.md, migração e recuperação offline.
- **Agora:** confirmação de que a demonstração usa exclusivamente banco/arquivos/credenciais efêmeros e loopback. Isso é ambiente de teste automatizado local, não ambiente disponibilizado à equipe.
- **Testes/evidências:** EV-03-04-local.json e suíte usam recursos sintéticos; nenhum ensaio em homologação.
- **Pendências/bloqueios:** operador deve identificar URL/servidor, DATABASE_URL, raiz/URL FTP, credencial exclusiva, transporte e janela de teste; aplicar migração, conferir permissões e separar logs/e-mail/segredos. Exclusão legada e logos têm configuração própria a conferir separadamente. Falhas externas exigem autorização e isolamento demonstrados.
- **Evidências/próxima ação/justificativa:** checklist citado e docs/SCORM_PUBLICACAO_RECUPERACAO.md. Fornecer/configurar os recursos e executar o aceite. Preparação documental não significa ambiente disponível; mantém-se Em análise, sem bloquear AUD-01 já concluída.

## C0-10

- **Estado anterior:** v3 Não iniciado; consolidação local anterior Em andamento.
- **Estado técnico e status recomendado:** suíte unittest cobre pacote/manifesto, publicação, HTTP de upload/replace, persistência e migração; **Em andamento**.
- **Já existia:** 66 regressões, fixtures temporárias, SQLite real, FTP simulado/loopback e subprocesso interrompido. Há teste de ausência de autenticação na rota de upload; não uma suíte completa de autenticação.
- **Agora:** cobertura classificada sem acrescentar testes de funcionalidades fora de C0-01. Demonstração adicional usa autenticação real por Bearer, mas não substitui regressões específicas de emissão/expiração/revogação.
- **Testes/evidências:** 66/66 novamente, EV-01-testes.txt e contagem por módulo em VERIFICACAO.json; fonte em backend/tests/test_scorm_*.py.
- **Pendências:** assinatura/token inválido/expiração/revogação/admin por papel; criação/duplicação/permissões de matrícula; ownership e start/update/finish de sessões; regra pedagógica de conclusão/nota e persistência fim a fim. Testes de preservação de Enrollment/CourseSession não exercitam todos esses endpoints. Integração contínua não comprovada.
- **Bloqueios/dependências:** contrato C0-08 para a regra de nota/conclusão e fixtures adicionais isoladas. Unittest permanece o padrão do repositório; não se migrou para pytest pela menção antiga na planilha.
- **Próxima ação/justificativa:** ampliar regressões críticas em etapa autorizada após o contrato pertinente; a cobertura já realizada é progresso efetivo, mas upload não conclui C0-10.

## Evidências EV-01 a EV-06 e classificação

| Código | Evidência atual | Classificação |
|---|---|---|
| EV-01 | docs/evidencias/consolidacao-atual/EV-01-testes.txt | Execução automatizada verificada: testes unitários, mocks FTP, integrações SQLite/ASGI e FTP loopback; não homologação |
| EV-02 | Fontes/hashes em VERIFICACAO.json; scorm_package.py, scorm_manifest.py e scorm_publication.py | Código verificável da validação e recuperação atuais; não relato histórico de branch |
| EV-03 | docs/evidencias/consolidacao-atual/EV-03-04-local.json | Upload válido por HTTP socket, autenticação, BD/FTP reais locais, com curso/arquivo/journal conferidos |
| EV-04 | Mesmo JSON | ZIP inválido rejeitado por HTTP; zero cursos, arquivos publicados e journal; integração real local |
| EV-05 | Testes local FTP de rollback/interrupção em EV-01 | Prova local real disponível; evidência de recuperação FTP EM HOMOLOGAÇÃO continua pendente |
| EV-06 | docs/SCORM_PUBLICACAO_RECUPERACAO.md, docs/ARQUITETURA_EXECUCAO_LOCAL.md e este relatório | Documentação verificável, sem substituir aceite operacional |

Não houve teste manual de interface ou screenshot. EV-03/04 foram demonstrações automatizadas locais, não capturas de tela ou homologação. Não se registraram credenciais/tokens/.env/dados de alunos; valores de acesso sintéticos ficaram apenas na memória do processo.

## Entregas desta rodada, limitações e prioridades

Criados scripts e artefatos em docs/evidencias/consolidacao-atual/ (verificar.py, demonstrar_http.py, EV-01-testes.txt, VERIFICACAO.json, EV-03-04-local.json e MATRIZ_SCORM.md). Atualizado este relatório, preservando sua versão inicial, e acrescentadas referências vigentes no plano/índice de evidências. Nenhuma alteração de código funcional/testes existentes foi necessária. A suíte aprovada não comprova segurança absoluta, toda compatibilidade SCORM ou infraestrutura real. Lint anterior permanece uma dívida documentada, fora desta rodada.

Ordem proposta: operacionalizar C0-04/C0-09 para homologar C0-01 → executar matriz e aceite → ampliar C0-10 conforme contrato C0-08 → priorizar demais riscos C0 em planejamento próprio. M1-01/dicionário e decisões pedagógicas devem preceder a expansão C1. Não se iniciou C0-02 ou C1 automaticamente e não se exige recuperar a branch histórica para usar a implementação atual já revisada.

Para professores: as verificações automáticas passaram novamente e há demonstração real local de envio aceito e arquivo inválido recusado. Isso reduz erros na publicação; os registros explicam o que foi observado. Falta repetir a validação no espaço de homologação separado dos alunos reais. O acompanhamento das demais ações de matrícula e conclusão ainda precisa de testes próprios.

## RESUMO PARA ATUALIZAÇÃO DA PLANILHA

Em 04/11/2026, main/fa3fbab com trabalhos locais preservados: AUD-01 Concluído; AUD-02 Concluído; C0-01 Aguardando validação em homologação; C0-09 Em análise; C0-10 Em andamento. Nova suíte executada: 66 aprovados, 0 falhas/erros/ignorados; dez manifestos aceitos. Não reutilizar a contagem histórica de 38 testes.

EV-03/04 agora incluem HTTP socket com autenticação, SQLite e FTP reais locais, dados sintéticos e conferência de persistência/arquivos. Não são interface manual nem homologação. EV-05 em homologação permanece pendente. Logs atuais: docs/evidencias/consolidacao-atual/EV-01-testes.txt, VERIFICACAO.json e EV-03-04-local.json; matriz em MATRIZ_SCORM.md no mesmo diretório. Relatório vigente: docs/evidencias/RELATORIO_ATUALIZACAO_PLANO.md.

Próxima ação: disponibilizar C0-09 segregada, aplicar migração autorizada e executar matriz/aceite real da C0-01. C0-10 ainda carece de regressões amplas de autenticação, matrícula, sessão e conclusão, com contrato pedagógico definido. Sem deploy, commit, push, edição do Excel, uso de alunos reais ou funcionalidades C1.
